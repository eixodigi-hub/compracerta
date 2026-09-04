-- =========================================================
-- promo_alerts: cliente escolhe produtos para acompanhar e
-- receber aviso por e-mail quando entrarem em promoção.
-- O envio de e-mail em si é um job separado (ainda não
-- implementado); esta migração só cria a estrutura de dados
-- e a leitura para a UI.
-- =========================================================
CREATE TABLE public.promo_alerts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  canonical_product_id uuid NOT NULL REFERENCES public.canonical_products(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  -- Preenchido pelo futuro job de envio, para não notificar de novo
  -- enquanto a mesma promoção ainda está ativa.
  notified_at timestamptz,
  UNIQUE (user_id, canonical_product_id)
);
CREATE INDEX idx_promo_alerts_user_id ON public.promo_alerts(user_id);
CREATE INDEX idx_promo_alerts_canonical_product_id ON public.promo_alerts(canonical_product_id);

GRANT SELECT, INSERT, DELETE ON public.promo_alerts TO authenticated;
GRANT ALL ON public.promo_alerts TO service_role;
ALTER TABLE public.promo_alerts ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users manage own promo alerts"
  ON public.promo_alerts FOR ALL TO authenticated
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

-- =========================================================
-- get_my_promo_alerts: produtos que o usuário está acompanhando,
-- já com o melhor preço/mercado atual e se está em promoção
-- agora — para a tela "Alertas de promoção".
-- =========================================================
CREATE OR REPLACE FUNCTION public.get_my_promo_alerts()
RETURNS TABLE (
  alert_id uuid,
  canonical_product_id uuid,
  name text,
  brand text,
  quantity numeric,
  unit text,
  image_url text,
  min_price numeric,
  reference_price numeric,
  has_promotion boolean,
  best_store_name text,
  created_at timestamptz
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
      (cur.promotional_price IS NOT NULL
        AND cur.promotional_price < cur.regular_price
        AND (cur.promotion_end_at IS NULL OR cur.promotion_end_at > now())) AS in_promo,
      s.name AS store_name,
      row_number() OVER (
        PARTITION BY sp.canonical_product_id
        ORDER BY
          (cur.promotional_price IS NOT NULL
            AND cur.promotional_price < cur.regular_price
            AND (cur.promotion_end_at IS NULL OR cur.promotion_end_at > now())) DESC,
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
    WHERE sp.canonical_product_id IN (
      SELECT pa.canonical_product_id FROM public.promo_alerts pa WHERE pa.user_id = auth.uid()
    )
    AND sp.active = true AND sp.available = true AND s.active = true AND cur.in_stock = true
  )
  SELECT
    pa.id,
    cp.id,
    cp.name,
    cp.brand,
    cp.quantity,
    cp.unit,
    cp.image_url,
    b.eff_price,
    b.reg_price,
    COALESCE(b.in_promo, false),
    b.store_name,
    pa.created_at
  FROM public.promo_alerts pa
  JOIN public.canonical_products cp ON cp.id = pa.canonical_product_id
  LEFT JOIN best b ON b.cpid = cp.id AND b.rn = 1
  WHERE pa.user_id = auth.uid()
  ORDER BY pa.created_at DESC;
$$;
GRANT EXECUTE ON FUNCTION public.get_my_promo_alerts() TO authenticated;
