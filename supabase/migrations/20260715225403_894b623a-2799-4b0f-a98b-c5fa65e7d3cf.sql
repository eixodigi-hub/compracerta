
CREATE OR REPLACE FUNCTION public.list_current_offers(
  store_id_filter uuid    DEFAULT NULL,
  category_slug   text    DEFAULT NULL,
  brand_filter    text    DEFAULT NULL,
  min_discount    numeric DEFAULT 0,
  max_age_hours   integer DEFAULT 72,
  limit_count     integer DEFAULT 60
)
RETURNS TABLE(
  store_product_id uuid,
  product_id       uuid,
  product_name     text,
  brand            text,
  quantity         numeric,
  unit             text,
  image_url        text,
  category_name    text,
  category_slug    text,
  store_id         uuid,
  store_name       text,
  store_slug       text,
  product_url      text,
  regular_price    numeric,
  promotional_price numeric,
  discount_pct     numeric,
  promotion_end_at timestamptz,
  collected_at     timestamptz
)
LANGUAGE sql
STABLE
SET search_path = public
AS $$
  SELECT
    sp.id  AS store_product_id,
    cp.id  AS product_id,
    cp.name AS product_name,
    cp.brand,
    cp.quantity,
    cp.unit,
    COALESCE(cp.image_url, sp.image_url) AS image_url,
    c.name AS category_name,
    c.slug AS category_slug,
    s.id   AS store_id,
    s.name AS store_name,
    s.slug AS store_slug,
    sp.product_url,
    cur.regular_price,
    cur.promotional_price,
    ROUND(((cur.regular_price - cur.promotional_price) / cur.regular_price * 100)::numeric, 1) AS discount_pct,
    cur.promotion_end_at,
    cur.collected_at
  FROM public.current_prices cur
  JOIN public.store_products sp ON sp.id = cur.store_product_id
  JOIN public.stores s          ON s.id  = sp.store_id
  JOIN public.canonical_products cp ON cp.id = sp.canonical_product_id
  LEFT JOIN public.categories c ON c.id = cp.category_id
  WHERE sp.active = true
    AND sp.available = true
    AND cp.active = true
    AND s.active = true
    AND cur.in_stock = true
    AND cur.promotional_price IS NOT NULL
    AND cur.regular_price IS NOT NULL
    AND cur.regular_price > cur.promotional_price
    AND (cur.promotion_end_at IS NULL OR cur.promotion_end_at > now())
    AND cur.collected_at >= now() - make_interval(hours => max_age_hours)
    AND (store_id_filter IS NULL OR s.id = store_id_filter)
    AND (category_slug   IS NULL OR c.slug = category_slug)
    AND (brand_filter    IS NULL OR brand_filter = '' OR cp.brand ILIKE brand_filter)
    AND ((cur.regular_price - cur.promotional_price) / cur.regular_price * 100) >= COALESCE(min_discount, 0)
  ORDER BY discount_pct DESC NULLS LAST, cur.collected_at DESC
  LIMIT LEAST(limit_count, 200);
$$;

GRANT EXECUTE ON FUNCTION public.list_current_offers(uuid, text, text, numeric, integer, integer) TO anon, authenticated;
