
CREATE OR REPLACE FUNCTION public.compute_list_comparison(p_list_id uuid)
RETURNS jsonb
LANGUAGE sql
STABLE
SET search_path = public
AS $$
WITH items AS (
  SELECT
    sli.canonical_product_id AS product_id,
    cp.name  AS product_name,
    cp.brand AS product_brand,
    cp.image_url,
    sli.quantity,
    sli.allow_similar_products
  FROM public.shopping_list_items sli
  JOIN public.canonical_products cp ON cp.id = sli.canonical_product_id
  WHERE sli.shopping_list_id = p_list_id
),
store_offers AS (
  SELECT
    s.id   AS store_id,
    s.name AS store_name,
    s.slug AS store_slug,
    s.logo_url,
    i.product_id,
    i.product_name,
    i.quantity,
    MIN(
      CASE
        WHEN cur.promotional_price IS NOT NULL
             AND (cur.promotion_end_at IS NULL OR cur.promotion_end_at > now())
          THEN cur.promotional_price
        ELSE cur.regular_price
      END
    ) AS unit_price
  FROM items i
  CROSS JOIN public.stores s
  LEFT JOIN public.store_products sp
    ON sp.canonical_product_id = i.product_id
   AND sp.store_id = s.id
   AND sp.active = true
   AND sp.available = true
  LEFT JOIN public.current_prices cur
    ON cur.store_product_id = sp.id
   AND cur.in_stock = true
  WHERE s.active = true
  GROUP BY s.id, s.name, s.slug, s.logo_url, i.product_id, i.product_name, i.quantity
),
store_lines AS (
  SELECT
    store_id, store_name, store_slug, logo_url,
    product_id, product_name, quantity,
    unit_price,
    CASE WHEN unit_price IS NULL THEN NULL ELSE unit_price * quantity END AS line_total,
    (unit_price IS NULL) AS missing
  FROM store_offers
),
stores_summary AS (
  SELECT
    store_id, store_name, store_slug, logo_url,
    bool_or(missing) AS has_missing,
    SUM(line_total) AS total_all,
    jsonb_agg(jsonb_build_object(
      'product_id',  product_id,
      'product_name', product_name,
      'quantity',    quantity,
      'unit_price',  unit_price,
      'line_total',  line_total,
      'missing',     missing
    ) ORDER BY product_name) AS lines,
    jsonb_agg(product_name) FILTER (WHERE missing) AS missing_names
  FROM store_lines
  GROUP BY store_id, store_name, store_slug, logo_url
),
best_per_item AS (
  SELECT DISTINCT ON (product_id)
    product_id, product_name, quantity, store_id, store_name, unit_price, line_total
  FROM store_lines
  WHERE NOT missing
  ORDER BY product_id, unit_price ASC
),
per_item_summary AS (
  SELECT
    SUM(line_total) AS total,
    COUNT(DISTINCT store_id) AS stores_needed,
    jsonb_agg(jsonb_build_object(
      'product_id',  product_id,
      'product_name', product_name,
      'quantity',    quantity,
      'store_id',    store_id,
      'store_name',  store_name,
      'unit_price',  unit_price,
      'line_total',  line_total
    ) ORDER BY product_name) AS breakdown,
    (SELECT jsonb_agg(i.product_name)
       FROM items i
       WHERE NOT EXISTS (SELECT 1 FROM best_per_item b WHERE b.product_id = i.product_id)
    ) AS missing_names
  FROM best_per_item
),
best_complete AS (
  SELECT store_id, store_name, total_all
  FROM stores_summary
  WHERE NOT has_missing
  ORDER BY total_all ASC
  LIMIT 1
)
SELECT jsonb_build_object(
  'items',
    COALESCE((SELECT jsonb_agg(to_jsonb(i2) ORDER BY i2.product_name) FROM items i2), '[]'::jsonb),
  'stores',
    COALESCE((SELECT jsonb_agg(to_jsonb(ss) ORDER BY ss.has_missing ASC, ss.total_all ASC NULLS LAST) FROM stores_summary ss), '[]'::jsonb),
  'best_complete',
    (SELECT to_jsonb(bc) FROM best_complete bc),
  'per_item',
    (SELECT to_jsonb(pis) FROM per_item_summary pis),
  'savings',
    CASE
      WHEN (SELECT total_all FROM best_complete) IS NULL
           OR (SELECT total FROM per_item_summary) IS NULL
        THEN NULL
      ELSE (SELECT total_all FROM best_complete) - (SELECT total FROM per_item_summary)
    END
);
$$;

GRANT EXECUTE ON FUNCTION public.compute_list_comparison(uuid) TO authenticated;
