import { createFileRoute } from "@tanstack/react-router";
import { z } from "zod";
import { timingSafeEqual } from "crypto";

const productSchema = z.object({
  external_id: z.string().min(1).max(200),
  external_name: z.string().min(1).max(500),
  product_url: z.string().url().max(2000).nullable().optional(),
  image_url: z.string().url().max(2000).nullable().optional(),
  brand_raw: z.string().max(200).nullable().optional(),
  quantity_raw: z.string().max(50).nullable().optional(),
  unit_raw: z.string().max(50).nullable().optional(),
  barcode_raw: z.string().max(50).nullable().optional(),
  regular_price: z.number().finite().nonnegative(),
  promotional_price: z.number().finite().nonnegative().nullable().optional(),
  effective_price: z.number().finite().nonnegative().optional(),
  promotion_text: z.string().max(500).nullable().optional(),
  promotion_end_at: z.string().datetime({ offset: true }).nullable().optional(),
  available: z.boolean(),
  collected_at: z.string().datetime({ offset: true }),
});

const bodySchema = z.object({
  store_id: z.string().uuid(),
  products: z.array(productSchema).min(1).max(5000),
});

function safeEqual(a: string, b: string): boolean {
  const ab = Buffer.from(a);
  const bb = Buffer.from(b);
  if (ab.length !== bb.length) return false;
  return timingSafeEqual(ab, bb);
}

export const Route = createFileRoute("/api/public/ingest-products")({
  server: {
    handlers: {
      POST: async ({ request }) => {
        const secret = process.env.INGEST_SECRET;
        if (!secret) {
          return json({ error: "Server not configured" }, 500);
        }

        const provided =
          request.headers.get("x-ingest-secret") ??
          (request.headers.get("authorization") ?? "").replace(/^Bearer\s+/i, "");
        if (!provided || !safeEqual(provided, secret)) {
          return json({ error: "Unauthorized" }, 401);
        }

        let raw: unknown;
        try {
          raw = await request.json();
        } catch {
          return json({ error: "Invalid JSON body" }, 400);
        }

        const parsed = bodySchema.safeParse(raw);
        if (!parsed.success) {
          return json(
            {
              error: "Validation failed",
              issues: parsed.error.issues.map((i) => ({
                path: i.path.join("."),
                message: i.message,
              })),
            },
            400,
          );
        }

        const { store_id, products } = parsed.data;
        const { supabaseAdmin } = await import("@/integrations/supabase/client.server");

        const { data: store, error: storeErr } = await supabaseAdmin
          .from("stores")
          .select("id")
          .eq("id", store_id)
          .maybeSingle();
        if (storeErr || !store) {
          return json({ error: "Unknown store" }, 404);
        }

        const { data: run, error: runErr } = await supabaseAdmin
          .from("ingestion_runs")
          .insert({ store_id, status: "running", products_found: products.length })
          .select("id")
          .single();
        if (runErr || !run) {
          return json({ error: "Failed to start ingestion" }, 500);
        }

        const counts = { created: 0, updated: 0, skipped: 0, errors: 0 };
        const errorSamples: Array<{ external_id: string; message: string }> = [];

        for (const p of products) {
          try {
            // Validate price logic
            if (
              p.promotional_price != null &&
              p.promotional_price > p.regular_price
            ) {
              throw new Error("promotional_price must be <= regular_price");
            }
            const promoActive =
              p.promotional_price != null &&
              (!p.promotion_end_at || new Date(p.promotion_end_at) > new Date());
            const effective =
              p.effective_price ??
              (promoActive ? (p.promotional_price as number) : p.regular_price);
            if (effective < 0) throw new Error("effective_price invalid");

            // Upsert store_product by (store_id, external_id)
            const { data: existing } = await supabaseAdmin
              .from("store_products")
              .select("id")
              .eq("store_id", store_id)
              .eq("external_id", p.external_id)
              .maybeSingle();

            const spPayload = {
              store_id,
              external_id: p.external_id,
              external_name: p.external_name,
              product_url: p.product_url ?? null,
              image_url: p.image_url ?? null,
              brand_raw: p.brand_raw ?? null,
              quantity_raw: p.quantity_raw ?? null,
              unit_raw: p.unit_raw ?? null,
              barcode_raw: p.barcode_raw ?? null,
              available: p.available,
              active: true,
              last_seen_at: p.collected_at,
            };

            let storeProductId: string;
            if (existing) {
              const { error } = await supabaseAdmin
                .from("store_products")
                .update(spPayload)
                .eq("id", existing.id);
              if (error) throw error;
              storeProductId = existing.id;
              counts.updated++;
            } else {
              const { data: inserted, error } = await supabaseAdmin
                .from("store_products")
                .insert(spPayload)
                .select("id")
                .single();
              if (error || !inserted) throw error ?? new Error("insert failed");
              storeProductId = inserted.id;
              counts.created++;
            }

            // Fetch previous current_prices
            const { data: prev } = await supabaseAdmin
              .from("current_prices")
              .select("regular_price, promotional_price, effective_price, in_stock, promotion_end_at")
              .eq("store_product_id", storeProductId)
              .maybeSingle();

            const newRow = {
              store_product_id: storeProductId,
              regular_price: p.regular_price,
              promotional_price: p.promotional_price ?? null,
              effective_price: effective,
              promotion_text: p.promotion_text ?? null,
              promotion_end_at: p.promotion_end_at ?? null,
              in_stock: p.available,
              collected_at: p.collected_at,
            };

            const changed =
              !prev ||
              Number(prev.regular_price) !== p.regular_price ||
              Number(prev.promotional_price ?? -1) !== Number(p.promotional_price ?? -1) ||
              Number(prev.effective_price) !== effective ||
              prev.in_stock !== p.available;

            const { error: cpErr } = await supabaseAdmin
              .from("current_prices")
              .upsert(newRow, { onConflict: "store_product_id" });
            if (cpErr) throw cpErr;

            if (changed) {
              const { error: phErr } = await supabaseAdmin
                .from("price_history")
                .insert({
                  store_product_id: storeProductId,
                  regular_price: p.regular_price,
                  promotional_price: p.promotional_price ?? null,
                  effective_price: effective,
                  in_stock: p.available,
                  collected_at: p.collected_at,
                });
              if (phErr) throw phErr;
            } else {
              counts.skipped++;
            }
          } catch (e) {
            counts.errors++;
            if (errorSamples.length < 10) {
              errorSamples.push({
                external_id: p.external_id,
                message: e instanceof Error ? e.message : "unknown error",
              });
            }
          }
        }

        const anySuccess = counts.errors < products.length;
        const finalStatus =
          counts.errors === 0 ? "success" : anySuccess ? "partial" : "failed";

        await supabaseAdmin
          .from("ingestion_runs")
          .update({
            status: finalStatus,
            products_updated: counts.created + counts.updated,
            finished_at: new Date().toISOString(),
            error_message: counts.errors > 0 ? `${counts.errors} product(s) failed` : null,
          })
          .eq("id", run.id);

        if (finalStatus === "success" || finalStatus === "partial") {
          await supabaseAdmin
            .from("stores")
            .update({ last_successful_sync_at: new Date().toISOString() })
            .eq("id", store_id);
        }

        return json({
          run_id: run.id,
          status: finalStatus,
          counts,
          errors: errorSamples,
        });
      },
    },
  },
});

function json(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}
