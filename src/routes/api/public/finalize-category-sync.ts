import { createFileRoute } from "@tanstack/react-router";
import { z } from "zod";
import { timingSafeEqual } from "crypto";

const bodySchema = z.object({
  store_id: z.string().uuid(),
  category_key: z.string().min(1).max(100),
  seen_external_ids: z.array(z.string().min(1).max(200)).max(50000),
  sync_token: z.string().min(1).max(200),
  collected_at: z.string().datetime({ offset: true }),
});

function safeEqual(a: string, b: string): boolean {
  const ab = Buffer.from(a);
  const bb = Buffer.from(b);
  if (ab.length !== bb.length) return false;
  return timingSafeEqual(ab, bb);
}

function json(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}

export const Route = createFileRoute("/api/public/finalize-category-sync")({
  server: {
    handlers: {
      POST: async ({ request }) => {
        const secret = process.env.INGEST_SECRET;
        if (!secret) return json({ error: "Server not configured" }, 500);

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

        const { store_id, category_key, seen_external_ids, sync_token, collected_at } = parsed.data;
        const { supabaseAdmin } = await import("@/integrations/supabase/client.server");

        // Verify store exists
        const { data: store, error: storeErr } = await supabaseAdmin
          .from("stores")
          .select("id")
          .eq("id", store_id)
          .maybeSingle();
        if (storeErr || !store) {
          return json({ error: "Unknown store" }, 404);
        }

        const { data, error } = await supabaseAdmin.rpc("finalize_category_sync", {
          p_store_id: store_id,
          p_category_key: category_key,
          p_sync_token: sync_token,
          p_seen_external_ids: seen_external_ids,
          p_collected_at: collected_at,
        });

        if (error) {
          return json({ error: "Finalization failed", message: error.message }, 500);
        }

        return json(data);
      },
    },
  },
});
