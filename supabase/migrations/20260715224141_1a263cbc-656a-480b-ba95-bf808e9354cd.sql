
CREATE OR REPLACE FUNCTION public.search_products(
  q text DEFAULT NULL,
  category_slug text DEFAULT NULL,
  brand_filter text DEFAULT NULL,
  store_id_filter uuid DEFAULT NULL,
  only_available boolean DEFAULT false,
  only_offers boolean DEFAULT false,
  min_price numeric DEFAULT NULL,
  max_price numeric DEFAULT NULL,
  sort_by text DEFAULT 'price_asc',
  limit_count int DEFAULT 30,
  offset_count int DEFAULT 0
)
RETURNS TABLE (
  id uuid,
  name text,
  brand text,
  quantity numeric,
  unit text,
  image_url text,
  barcode text,
  category_id uuid,
  category_name text,
  category_slug text,
  min_price numeric,
  reference_price numeric,
  max_discount_pct numeric,
  market_count int,
  last_updated timestamptz,
  has_promotion boolean
)
LANGUAGE sql
STABLE
SET search_path = public, extensions
AS $$
  WITH filtered_prices AS (
    SELECT
      sp.canonical_product_id,
      sp.store_id,
      cp.effective_price,
      cp.regular_price,
      cp.promotional_price,
      cp.collected_at,
      sp.available
    FROM public.store_products sp
    JOIN public.current_prices cp ON cp.store_product_id = sp.id
    WHERE sp.active = true
      AND sp.canonical_product_id IS NOT NULL
      AND (NOT only_available OR (sp.available = true AND cp.in_stock = true))
      AND (store_id_filter IS NULL OR sp.store_id = store_id_filter)
      AND (NOT only_offers OR cp.promotional_price IS NOT NULL)
      AND (min_price IS NULL OR cp.effective_price >= min_price)
      AND (max_price IS NULL OR cp.effective_price <= max_price)
  ),
  agg AS (
    SELECT
      canonical_product_id,
      MIN(effective_price) AS min_price,
      MAX(regular_price)   AS reference_price,
      MAX(CASE
            WHEN promotional_price IS NOT NULL AND regular_price > 0
            THEN ((regular_price - promotional_price) / regular_price) * 100
            ELSE 0
          END) AS max_discount_pct,
      COUNT(DISTINCT store_id)::int AS market_count,
      MAX(collected_at) AS last_updated,
      bool_or(promotional_price IS NOT NULL) AS has_promotion
    FROM filtered_prices
    GROUP BY canonical_product_id
  )
  SELECT
    p.id, p.name, p.brand, p.quantity, p.unit, p.image_url, p.barcode,
    p.category_id, c.name AS category_name, c.slug AS category_slug,
    a.min_price, a.reference_price, a.max_discount_pct,
    a.market_count, a.last_updated, a.has_promotion
  FROM public.canonical_products p
  JOIN agg a ON a.canonical_product_id = p.id
  LEFT JOIN public.categories c ON c.id = p.category_id
  WHERE p.active = true
    AND (category_slug IS NULL OR c.slug = category_slug)
    AND (brand_filter IS NULL OR brand_filter = '' OR p.brand ILIKE brand_filter)
    AND (
      q IS NULL OR q = '' OR
      p.barcode = q OR
      NOT EXISTS (
        SELECT 1
        FROM unnest(
          string_to_array(
            regexp_replace(trim(public.immutable_unaccent(q)), '\s+', ' ', 'g'),
            ' '
          )
        ) AS tok
        WHERE tok <> ''
          AND public.immutable_unaccent(
                p.name || ' ' ||
                COALESCE(p.brand, '') || ' ' ||
                COALESCE(p.quantity::text, '') || ' ' ||
                COALESCE(p.unit, '') || ' ' ||
                COALESCE(p.description, '')
              ) NOT ILIKE '%' || tok || '%'
      )
    )
  ORDER BY
    CASE WHEN sort_by = 'price_asc'     THEN a.min_price          END ASC  NULLS LAST,
    CASE WHEN sort_by = 'discount_desc' THEN a.max_discount_pct   END DESC NULLS LAST,
    CASE WHEN sort_by = 'name_asc'      THEN p.name               END ASC  NULLS LAST,
    CASE WHEN sort_by = 'recent'        THEN a.last_updated       END DESC NULLS LAST
  LIMIT LEAST(limit_count, 100)
  OFFSET GREATEST(offset_count, 0);
$$;

GRANT EXECUTE ON FUNCTION public.search_products(
  text, text, text, uuid, boolean, boolean, numeric, numeric, text, int, int
) TO anon, authenticated;

-- Distinct brand list (used to populate the brand filter).
CREATE OR REPLACE FUNCTION public.list_search_brands()
RETURNS TABLE (brand text)
LANGUAGE sql
STABLE
SET search_path = public
AS $$
  SELECT DISTINCT p.brand
  FROM public.canonical_products p
  WHERE p.active = true AND p.brand IS NOT NULL AND p.brand <> ''
  ORDER BY p.brand;
$$;

GRANT EXECUTE ON FUNCTION public.list_search_brands() TO anon, authenticated;
