-- =========================================================
-- Suporte ao job de envio de e-mail dos alertas de promoção.
-- Só o service_role chama estas funções (nenhum GRANT para
-- authenticated/anon) — get_promo_alerts_to_notify() expõe
-- e-mail de todos os usuários com alerta pendente, não pode
-- ficar acessível ao cliente.
-- =========================================================

-- Produtos com alerta ativo que entraram em promoção e ainda não
-- foram notificados (notified_at IS NULL). Uma linha por alerta.
CREATE OR REPLACE FUNCTION public.get_promo_alerts_to_notify()
RETURNS TABLE (
  alert_id uuid,
  user_id uuid,
  user_email text,
  canonical_product_id uuid,
  product_name text,
  brand text,
  quantity numeric,
  unit text,
  image_url text,
  price numeric,
  regular_price numeric,
  store_name text
)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  WITH best AS (
    SELECT
      sp.canonical_product_id AS cpid,
      CASE
        WHEN cur.promotional_price IS NOT NULL
         AND (cur.promotion_end_at IS NULL OR cur.promotion_end_at > now())
          THEN cur.promotional_price
        ELSE cur.regular_price
      END AS eff_price,
      cur.regular_price AS reg_price,
      s.name AS store_name,
      row_number() OVER (
        PARTITION BY sp.canonical_product_id
        ORDER BY
          (CASE
             WHEN cur.promotional_price IS NOT NULL
              AND (cur.promotion_end_at IS NULL OR cur.promotion_end_at > now())
               THEN cur.promotional_price
             ELSE cur.regular_price
           END) ASC
      ) AS rn
    FROM public.store_products sp
    JOIN public.current_prices cur ON cur.store_product_id = sp.id
    JOIN public.stores s ON s.id = sp.store_id
    WHERE sp.active = true AND sp.available = true AND s.active = true AND cur.in_stock = true
      AND cur.promotional_price IS NOT NULL
      AND cur.promotional_price < cur.regular_price
      AND (cur.promotion_end_at IS NULL OR cur.promotion_end_at > now())
  )
  SELECT
    pa.id,
    pa.user_id,
    u.email,
    cp.id,
    cp.name,
    cp.brand,
    cp.quantity,
    cp.unit,
    cp.image_url,
    b.eff_price,
    b.reg_price,
    b.store_name
  FROM public.promo_alerts pa
  JOIN public.canonical_products cp ON cp.id = pa.canonical_product_id
  JOIN best b ON b.cpid = cp.id AND b.rn = 1
  JOIN auth.users u ON u.id = pa.user_id
  WHERE pa.notified_at IS NULL;
$$;

-- Chamado depois de enviar o e-mail, para não notificar de novo
-- enquanto a mesma promoção continuar ativa.
CREATE OR REPLACE FUNCTION public.mark_promo_alerts_notified(p_alert_ids uuid[])
RETURNS void
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
  UPDATE public.promo_alerts
  SET notified_at = now()
  WHERE id = ANY(p_alert_ids);
$$;

-- Roda antes da busca por pendentes: libera de novo (notified_at =
-- NULL) qualquer alerta cuja promoção já não está mais ativa, para
-- que a próxima promoção do mesmo produto volte a notificar.
CREATE OR REPLACE FUNCTION public.reset_expired_promo_alerts()
RETURNS void
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
  UPDATE public.promo_alerts pa
  SET notified_at = NULL
  WHERE pa.notified_at IS NOT NULL
    AND NOT EXISTS (
      SELECT 1
      FROM public.store_products sp
      JOIN public.current_prices cur ON cur.store_product_id = sp.id
      JOIN public.stores s ON s.id = sp.store_id
      WHERE sp.canonical_product_id = pa.canonical_product_id
        AND sp.active = true AND sp.available = true AND s.active = true AND cur.in_stock = true
        AND cur.promotional_price IS NOT NULL
        AND cur.promotional_price < cur.regular_price
        AND (cur.promotion_end_at IS NULL OR cur.promotion_end_at > now())
    );
$$;
