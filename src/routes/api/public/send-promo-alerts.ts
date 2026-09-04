import { createFileRoute } from "@tanstack/react-router";
import { timingSafeEqual } from "crypto";

function safeEqual(a: string, b: string): boolean {
  const ab = Buffer.from(a);
  const bb = Buffer.from(b);
  if (ab.length !== bb.length) return false;
  return timingSafeEqual(ab, bb);
}

type NotifyRow = {
  alert_id: string;
  user_id: string;
  user_email: string;
  canonical_product_id: string;
  product_name: string;
  brand: string | null;
  quantity: number | null;
  unit: string | null;
  image_url: string | null;
  price: number | null;
  regular_price: number | null;
  store_name: string | null;
};

function brl(v: number | null): string {
  if (v == null) return "—";
  return v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function escapeHtml(s: string): string {
  const map: Record<string, string> = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  };
  return s.replace(/[&<>"']/g, (c) => map[c]);
}

function buildEmailHtml(products: NotifyRow[]): string {
  const items = products
    .map((p) => {
      const discount =
        p.regular_price && p.price && p.regular_price > p.price
          ? Math.round(((p.regular_price - p.price) / p.regular_price) * 100)
          : null;
      return `
        <tr>
          <td style="padding:12px 0;border-bottom:1px solid #e5e7eb;">
            <div style="font-weight:600;color:#111827;">${escapeHtml(p.product_name)}</div>
            <div style="font-size:13px;color:#6b7280;">
              ${p.brand ? escapeHtml(p.brand) + " &middot; " : ""}${p.store_name ? escapeHtml(p.store_name) : ""}
            </div>
          </td>
          <td style="padding:12px 0;border-bottom:1px solid #e5e7eb;text-align:right;white-space:nowrap;">
            ${
              p.regular_price != null && discount
                ? `<div style="font-size:12px;color:#9ca3af;text-decoration:line-through;">${brl(p.regular_price)}</div>`
                : ""
            }
            <div style="font-weight:700;color:#16a34a;">${brl(p.price)}</div>
            ${discount ? `<div style="font-size:12px;color:#16a34a;">-${discount}%</div>` : ""}
          </td>
        </tr>`;
    })
    .join("");

  return `
    <div style="font-family:Arial,sans-serif;max-width:520px;margin:0 auto;">
      <h2 style="color:#15803d;">Promoção nos seus produtos favoritos</h2>
      <p style="color:#374151;">
        Encontramos ${products.length} produto${products.length > 1 ? "s" : ""} da sua lista de
        acompanhamento em promoção agora:
      </p>
      <table style="width:100%;border-collapse:collapse;">${items}</table>
      <p style="margin-top:24px;font-size:13px;color:#9ca3af;">
        Você está recebendo este e-mail porque marcou esses produtos para acompanhar no
        <a href="https://compracerta-five.vercel.app" style="color:#16a34a;">Compra Certa</a>.
        Preços podem mudar a qualquer momento — confirme no site do mercado antes de comprar.
      </p>
    </div>`;
}

export const Route = createFileRoute("/api/public/send-promo-alerts")({
  server: {
    handlers: {
      POST: async ({ request }) => {
        const secret = process.env.PROMO_ALERTS_SECRET;
        const resendKey = process.env.RESEND_API_KEY;
        if (!secret || !resendKey) {
          return json({ error: "Server not configured" }, 500);
        }

        const provided =
          request.headers.get("x-promo-alerts-secret") ??
          (request.headers.get("authorization") ?? "").replace(/^Bearer\s+/i, "");
        if (!provided || !safeEqual(provided, secret)) {
          return json({ error: "Unauthorized" }, 401);
        }

        const { supabaseAdmin } = await import("@/integrations/supabase/client.server");

        // Libera de novo os alertas cuja promoção já acabou, para
        // poderem notificar de novo na próxima vez que entrarem em oferta.
        await supabaseAdmin.rpc("reset_expired_promo_alerts");

        const { data, error } = await supabaseAdmin.rpc("get_promo_alerts_to_notify");
        if (error) {
          return json({ error: error.message }, 500);
        }

        const rows = (data ?? []) as NotifyRow[];
        if (rows.length === 0) {
          return json({ sent: 0, users: 0, message: "Nada para notificar" });
        }

        const byUser = new Map<string, { email: string; products: NotifyRow[]; alertIds: string[] }>();
        for (const row of rows) {
          const entry = byUser.get(row.user_id) ?? { email: row.user_email, products: [], alertIds: [] };
          entry.products.push(row);
          entry.alertIds.push(row.alert_id);
          byUser.set(row.user_id, entry);
        }

        const fromAddress = process.env.PROMO_ALERTS_FROM || "Compra Certa <onboarding@resend.dev>";
        let sent = 0;
        const errors: Array<{ email: string; message: string }> = [];
        const allNotifiedIds: string[] = [];

        for (const entry of byUser.values()) {
          try {
            const res = await fetch("https://api.resend.com/emails", {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${resendKey}`,
              },
              body: JSON.stringify({
                from: fromAddress,
                to: entry.email,
                subject:
                  entry.products.length === 1
                    ? `${entry.products[0].product_name} entrou em promoção!`
                    : `${entry.products.length} produtos da sua lista entraram em promoção!`,
                html: buildEmailHtml(entry.products),
              }),
            });
            if (!res.ok) {
              const body = await res.text();
              throw new Error(`Resend ${res.status}: ${body}`);
            }
            sent++;
            allNotifiedIds.push(...entry.alertIds);
          } catch (e) {
            errors.push({
              email: entry.email,
              message: e instanceof Error ? e.message : "erro desconhecido",
            });
          }
        }

        if (allNotifiedIds.length > 0) {
          await supabaseAdmin.rpc("mark_promo_alerts_notified", { p_alert_ids: allNotifiedIds });
        }

        return json({ sent, users: byUser.size, errors });
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
