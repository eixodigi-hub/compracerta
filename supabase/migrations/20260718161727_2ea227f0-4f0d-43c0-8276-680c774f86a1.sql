DROP FUNCTION IF EXISTS public.search_products(
  text, text, text, uuid, boolean, boolean, numeric, numeric, text, integer, integer
);

CREATE FUNCTION public.search_products(
  q text DEFAULT NULL::text,
  category_slug text DEFAULT NULL::text,
  brand_filter text DEFAULT NULL::text,
  store_id_filter uuid DEFAULT NULL::uuid,
  only_available boolean DEFAULT false,
  only_offers boolean DEFAULT false,
  min_price numeric DEFAULT NULL::numeric,
  max_price numeric DEFAULT NULL::numeric,
  sort_by text DEFAULT 'price_asc'::text,
  limit_count integer DEFAULT 30,
  offset_count integer DEFAULT 0
)
RETURNS TABLE(
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
  market_count integer,
  last_updated timestamp with time zone,
  has_promotion boolean,
  offers jsonb,
  is_canonical boolean
)
LANGUAGE sql
STABLE
SET search_path TO 'public', 'extensions'
AS $function$
  WITH normalized AS (
    SELECT
      trim(COALESCE(q, '')) AS raw_q,
      public.immutable_unaccent(trim(COALESCE(q, ''))) AS norm_q
  ),
  tokens AS (
    SELECT array_remove(string_to_array(regexp_replace(norm_q, '\s+', ' ', 'g'), ' '), '') AS toks
    FROM normalized
  ),
  canonical_price_rows AS (
    SELECT
      cp.id AS product_id,
      cp.name,
      cp.brand,
      cp.quantity,
      cp.unit,
      COALESCE(cp.image_url, sp.image_url) AS image_url,
      cp.barcode,
      cp.category_id,
      c.name AS category_name,
      c.slug AS category_slug,
      s.id AS store_id,
      s.name AS store_name,
      s.slug AS store_slug,
      s.logo_url AS store_logo_url,
      sp.id AS store_product_id,
      sp.external_name,
      sp.product_url,
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
        ELSE cur.effective_price
      END AS effective_price,
      cur.promotion_text,
      cur.promotion_end_at,
      cur.collected_at
    FROM public.canonical_products cp
    JOIN public.store_products sp ON sp.canonical_product_id = cp.id
    JOIN public.current_prices cur ON cur.store_product_id = sp.id
    JOIN public.stores s ON s.id = sp.store_id
    LEFT JOIN public.categories c ON c.id = cp.category_id
    CROSS JOIN normalized n
    WHERE cp.active = true
      AND sp.active = true
      AND sp.available = true
      AND s.active = true
      AND cur.in_stock = true
      AND (store_id_filter IS NULL OR sp.store_id = store_id_filter)
      AND (category_slug IS NULL OR c.slug = category_slug)
      AND (brand_filter IS NULL OR brand_filter = '' OR cp.brand ILIKE brand_filter)
      AND (NOT only_offers OR (cur.promotional_price IS NOT NULL AND cur.promotional_price < cur.regular_price AND (cur.promotion_end_at IS NULL OR cur.promotion_end_at > now())))
      AND (min_price IS NULL OR cur.effective_price >= min_price)
      AND (max_price IS NULL OR cur.effective_price <= max_price)
      AND (
        n.raw_q = '' OR
        cp.barcode = n.raw_q OR
        NOT EXISTS (
          SELECT 1 FROM unnest((SELECT toks FROM tokens)) AS tok
          WHERE tok <> ''
            AND public.immutable_unaccent(
              cp.name || ' ' || COALESCE(cp.brand, '') || ' ' || COALESCE(cp.barcode, '') || ' ' ||
              COALESCE(cp.quantity::text, '') || ' ' || COALESCE(cp.unit, '') || ' ' || COALESCE(cp.description, '') || ' ' ||
              COALESCE(sp.external_name, '')
            ) NOT ILIKE '%' || tok || '%'
        )
      )
  ),
  canonical_rows AS (
    SELECT
      product_id AS id,
      name,
      brand,
      quantity,
      unit,
      MAX(image_url) FILTER (WHERE image_url IS NOT NULL) AS image_url,
      barcode,
      category_id,
      category_name,
      category_slug,
      MIN(effective_price) AS min_price,
      MAX(regular_price) AS reference_price,
      MAX(CASE WHEN promotional_price IS NOT NULL AND regular_price > 0
               THEN ((regular_price - promotional_price) / regular_price) * 100
               ELSE 0 END)::numeric AS max_discount_pct,
      COUNT(DISTINCT store_id)::int AS market_count,
      MAX(collected_at) AS last_updated,
      bool_or(promotional_price IS NOT NULL) AS has_promotion,
      jsonb_agg(
        jsonb_build_object(
          'store_id', store_id,
          'store_name', store_name,
          'store_slug', store_slug,
          'store_logo_url', store_logo_url,
          'store_product_id', store_product_id,
          'external_name', external_name,
          'product_url', product_url,
          'regular_price', regular_price,
          'promotional_price', promotional_price,
          'effective_price', effective_price,
          'promotion_text', promotion_text,
          'promotion_end_at', promotion_end_at,
          'collected_at', collected_at,
          'is_lowest', false
        ) ORDER BY effective_price ASC NULLS LAST, store_name ASC
      ) AS raw_offers,
      true AS is_canonical
    FROM canonical_price_rows
    GROUP BY product_id, name, brand, quantity, unit, barcode, category_id, category_name, category_slug
  ),
  canonical_rows_marked AS (
    SELECT
      cr.id, cr.name, cr.brand, cr.quantity, cr.unit, cr.image_url, cr.barcode,
      cr.category_id, cr.category_name, cr.category_slug,
      cr.min_price, cr.reference_price, cr.max_discount_pct, cr.market_count,
      cr.last_updated, cr.has_promotion,
      (
        SELECT jsonb_agg(
          CASE
            WHEN (offer->>'effective_price')::numeric = cr.min_price
              THEN jsonb_set(offer, '{is_lowest}', 'true'::jsonb, false)
            ELSE offer
          END
          ORDER BY (offer->>'effective_price')::numeric ASC NULLS LAST, offer->>'store_name' ASC
        )
        FROM jsonb_array_elements(cr.raw_offers) AS offer
      ) AS offers,
      cr.is_canonical
    FROM canonical_rows cr
  ),
  unlinked_rows AS (
    SELECT
      sp.id AS id,
      COALESCE(NULLIF(sp.external_name, ''), 'Produto') AS name,
      sp.brand_raw AS brand,
      NULL::numeric AS quantity,
      sp.unit_raw AS unit,
      sp.image_url,
      sp.barcode_raw AS barcode,
      NULL::uuid AS category_id,
      NULL::text AS category_name,
      NULL::text AS category_slug,
      cur.effective_price AS min_price,
      cur.regular_price AS reference_price,
      (CASE WHEN cur.promotional_price IS NOT NULL
             AND cur.promotional_price < cur.regular_price
             AND (cur.promotion_end_at IS NULL OR cur.promotion_end_at > now())
            THEN ((cur.regular_price - cur.promotional_price) / cur.regular_price) * 100
            ELSE 0 END)::numeric AS max_discount_pct,
      1 AS market_count,
      cur.collected_at AS last_updated,
      (cur.promotional_price IS NOT NULL AND cur.promotional_price < cur.regular_price AND (cur.promotion_end_at IS NULL OR cur.promotion_end_at > now())) AS has_promotion,
      jsonb_build_array(jsonb_build_object(
        'store_id', s.id,
        'store_name', s.name,
        'store_slug', s.slug,
        'store_logo_url', s.logo_url,
        'store_product_id', sp.id,
        'external_name', sp.external_name,
        'product_url', sp.product_url,
        'regular_price', cur.regular_price,
        'promotional_price', CASE
          WHEN cur.promotional_price IS NOT NULL
           AND (cur.promotion_end_at IS NULL OR cur.promotion_end_at > now())
            THEN cur.promotional_price
          ELSE NULL
        END,
        'effective_price', cur.effective_price,
        'promotion_text', cur.promotion_text,
        'promotion_end_at', cur.promotion_end_at,
        'collected_at', cur.collected_at,
        'is_lowest', true
      )) AS offers,
      false AS is_canonical
    FROM public.store_products sp
    JOIN public.current_prices cur ON cur.store_product_id = sp.id
    JOIN public.stores s ON s.id = sp.store_id
    CROSS JOIN normalized n
    WHERE sp.canonical_product_id IS NULL
      AND sp.active = true
      AND sp.available = true
      AND s.active = true
      AND cur.in_stock = true
      AND (store_id_filter IS NULL OR sp.store_id = store_id_filter)
      AND (NOT only_offers OR (cur.promotional_price IS NOT NULL AND cur.promotional_price < cur.regular_price AND (cur.promotion_end_at IS NULL OR cur.promotion_end_at > now())))
      AND (min_price IS NULL OR cur.effective_price >= min_price)
      AND (max_price IS NULL OR cur.effective_price <= max_price)
      AND (category_slug IS NULL)
      AND (brand_filter IS NULL OR brand_filter = '' OR sp.brand_raw ILIKE brand_filter)
      AND (
        n.raw_q = '' OR
        sp.barcode_raw = n.raw_q OR
        NOT EXISTS (
          SELECT 1 FROM unnest((SELECT toks FROM tokens)) AS tok
          WHERE tok <> ''
            AND public.immutable_unaccent(
              COALESCE(sp.external_name, '') || ' ' || COALESCE(sp.brand_raw, '') || ' ' ||
              COALESCE(sp.barcode_raw, '') || ' ' || COALESCE(sp.quantity_raw, '') || ' ' || COALESCE(sp.unit_raw, '')
            ) NOT ILIKE '%' || tok || '%'
        )
      )
  ),
  combined AS (
    SELECT * FROM canonical_rows_marked
    UNION ALL
    SELECT * FROM unlinked_rows
  )
  SELECT *
  FROM combined
  ORDER BY
    CASE WHEN sort_by = 'price_asc'     THEN min_price        END ASC NULLS LAST,
    CASE WHEN sort_by = 'discount_desc' THEN max_discount_pct END DESC NULLS LAST,
    CASE WHEN sort_by = 'name_asc'      THEN name             END ASC NULLS LAST,
    CASE WHEN sort_by = 'recent'        THEN last_updated     END DESC NULLS LAST,
    min_price ASC NULLS LAST,
    name ASC NULLS LAST
  LIMIT LEAST(limit_count, 100)
  OFFSET GREATEST(offset_count, 0);
$function$;

GRANT EXECUTE ON FUNCTION public.search_products(
  text, text, text, uuid, boolean, boolean, numeric, numeric, text, integer, integer
) TO anon, authenticated, service_role;