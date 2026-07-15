
-- Product detail with per-store comparison (expired promotions ignored)
CREATE OR REPLACE FUNCTION public.get_product_detail(p_product_id uuid)
RETURNS jsonb
LANGUAGE sql
STABLE
SET search_path = public
AS $$
  WITH prod AS (
    SELECT cp.*, c.name AS category_name, c.slug AS category_slug
    FROM public.canonical_products cp
    LEFT JOIN public.categories c ON c.id = cp.category_id
    WHERE cp.id = p_product_id AND cp.active = true
  ),
  offers AS (
    SELECT
      s.id   AS store_id,
      s.name AS store_name,
      s.slug AS store_slug,
      s.logo_url,
      s.website_url,
      sp.product_url,
      sp.external_name,
      sp.available,
      cur.regular_price,
      CASE
        WHEN cur.promotional_price IS NOT NULL
             AND (cur.promotion_end_at IS NULL OR cur.promotion_end_at > now())
          THEN cur.promotional_price
        ELSE NULL
      END AS promotional_price,
      CASE
        WHEN cur.promotional_price IS NOT NULL
             AND (cur.promotion_end_at IS NULL OR cur.promotion_end_at > now())
          THEN cur.promotional_price
        ELSE cur.regular_price
      END AS effective_price,
      cur.in_stock,
      cur.promotion_text,
      cur.promotion_end_at,
      cur.collected_at
    FROM public.store_products sp
    JOIN public.stores s ON s.id = sp.store_id AND s.active = true
    JOIN public.current_prices cur ON cur.store_product_id = sp.id
    WHERE sp.canonical_product_id = p_product_id AND sp.active = true
    ORDER BY effective_price ASC NULLS LAST
  )
  SELECT jsonb_build_object(
    'product', (SELECT to_jsonb(prod.*) FROM prod),
    'offers', COALESCE((SELECT jsonb_agg(to_jsonb(offers.*)) FROM offers), '[]'::jsonb),
    'last_updated', (SELECT MAX(collected_at) FROM offers)
  );
$$;

GRANT EXECUTE ON FUNCTION public.get_product_detail(uuid) TO anon, authenticated;

-- Daily aggregated price history for the last N days
CREATE OR REPLACE FUNCTION public.get_price_history(p_product_id uuid, p_days integer DEFAULT 30)
RETURNS TABLE(day date, min_price numeric, avg_price numeric, max_price numeric)
LANGUAGE sql
STABLE
SET search_path = public
AS $$
  WITH src AS (
    SELECT
      (ph.collected_at AT TIME ZONE 'UTC')::date AS day,
      CASE
        WHEN ph.promotional_price IS NOT NULL
          THEN ph.promotional_price
        ELSE ph.regular_price
      END AS eff
    FROM public.price_history ph
    JOIN public.store_products sp ON sp.id = ph.store_product_id
    WHERE sp.canonical_product_id = p_product_id
      AND ph.collected_at >= now() - make_interval(days => p_days)
  )
  SELECT day,
         MIN(eff)::numeric AS min_price,
         ROUND(AVG(eff)::numeric, 2) AS avg_price,
         MAX(eff)::numeric AS max_price
  FROM src
  WHERE eff IS NOT NULL
  GROUP BY day
  ORDER BY day ASC;
$$;

GRANT EXECUTE ON FUNCTION public.get_price_history(uuid, integer) TO anon, authenticated;

-- Aggregate stats for the last N days
CREATE OR REPLACE FUNCTION public.get_price_stats(p_product_id uuid, p_days integer DEFAULT 30)
RETURNS jsonb
LANGUAGE sql
STABLE
SET search_path = public
AS $$
  WITH src AS (
    SELECT
      CASE
        WHEN ph.promotional_price IS NOT NULL
          THEN ph.promotional_price
        ELSE ph.regular_price
      END AS eff
    FROM public.price_history ph
    JOIN public.store_products sp ON sp.id = ph.store_product_id
    WHERE sp.canonical_product_id = p_product_id
      AND ph.collected_at >= now() - make_interval(days => p_days)
  ),
  cur AS (
    SELECT MIN(
      CASE
        WHEN cur.promotional_price IS NOT NULL
             AND (cur.promotion_end_at IS NULL OR cur.promotion_end_at > now())
          THEN cur.promotional_price
        ELSE cur.regular_price
      END
    ) AS current_min
    FROM public.store_products sp
    JOIN public.current_prices cur ON cur.store_product_id = sp.id
    WHERE sp.canonical_product_id = p_product_id AND sp.active = true
  )
  SELECT jsonb_build_object(
    'min',      (SELECT MIN(eff) FROM src),
    'max',      (SELECT MAX(eff) FROM src),
    'avg',      (SELECT ROUND(AVG(eff)::numeric, 2) FROM src),
    'sample',   (SELECT COUNT(*) FROM src),
    'current',  (SELECT current_min FROM cur),
    'variation_pct',
      CASE
        WHEN (SELECT AVG(eff) FROM src) IS NULL OR (SELECT AVG(eff) FROM src) = 0
             OR (SELECT current_min FROM cur) IS NULL
          THEN NULL
        ELSE ROUND((((SELECT current_min FROM cur) - (SELECT AVG(eff) FROM src)) / (SELECT AVG(eff) FROM src) * 100)::numeric, 2)
      END
  );
$$;

GRANT EXECUTE ON FUNCTION public.get_price_stats(uuid, integer) TO anon, authenticated;
