
-- =============================================================
-- Admin overview stats
-- =============================================================
CREATE OR REPLACE FUNCTION public.admin_overview_stats()
RETURNS jsonb
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  result jsonb;
BEGIN
  IF NOT public.has_role(auth.uid(), 'admin') THEN
    RAISE EXCEPTION 'not authorized';
  END IF;

  SELECT jsonb_build_object(
    'active_products', (SELECT count(*) FROM public.canonical_products WHERE active = true),
    'active_stores',   (SELECT count(*) FROM public.stores WHERE active = true),
    'unmatched_store_products',
      (SELECT count(*) FROM public.store_products WHERE canonical_product_id IS NULL AND active = true),
    'prices_updated_24h',
      (SELECT count(*) FROM public.current_prices WHERE collected_at >= now() - interval '24 hours'),
    'prices_stale',
      (SELECT count(*) FROM public.current_prices WHERE collected_at < now() - interval '72 hours'),
    'recent_errors',
      COALESCE((
        SELECT jsonb_agg(jsonb_build_object(
          'id', ir.id,
          'store_id', ir.store_id,
          'store_name', s.name,
          'status', ir.status,
          'error_message', ir.error_message,
          'started_at', ir.started_at,
          'finished_at', ir.finished_at
        ) ORDER BY ir.started_at DESC)
        FROM public.ingestion_runs ir
        LEFT JOIN public.stores s ON s.id = ir.store_id
        WHERE ir.status::text IN ('failed','error')
           OR ir.error_message IS NOT NULL
        LIMIT 20
      ), '[]'::jsonb),
    'last_run_by_store',
      COALESCE((
        SELECT jsonb_agg(jsonb_build_object(
          'store_id', s.id,
          'store_name', s.name,
          'last_started_at', lr.started_at,
          'last_finished_at', lr.finished_at,
          'last_status', lr.status,
          'products_found', lr.products_found,
          'products_updated', lr.products_updated
        ) ORDER BY s.name)
        FROM public.stores s
        LEFT JOIN LATERAL (
          SELECT ir.*
          FROM public.ingestion_runs ir
          WHERE ir.store_id = s.id
          ORDER BY ir.started_at DESC NULLS LAST
          LIMIT 1
        ) lr ON true
        WHERE s.active = true
      ), '[]'::jsonb)
  ) INTO result;

  RETURN result;
END;
$$;

GRANT EXECUTE ON FUNCTION public.admin_overview_stats() TO authenticated;

-- =============================================================
-- Suggest canonical matches for an unmatched store_product.
-- Compatibility rule: same unit AND same quantity (when both known).
-- =============================================================
CREATE OR REPLACE FUNCTION public.admin_suggest_canonical(p_store_product_id uuid)
RETURNS TABLE (
  id uuid,
  name text,
  brand text,
  quantity numeric,
  unit text,
  barcode text,
  image_url text,
  category_name text,
  score real
)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public, extensions
AS $$
DECLARE
  sp record;
  q text;
  qty numeric;
  u text;
BEGIN
  IF NOT public.has_role(auth.uid(), 'admin') THEN
    RAISE EXCEPTION 'not authorized';
  END IF;

  SELECT external_name, brand_raw, barcode_raw, quantity_raw, unit_raw
    INTO sp
  FROM public.store_products
  WHERE store_products.id = p_store_product_id;

  IF sp IS NULL THEN
    RETURN;
  END IF;

  q := COALESCE(sp.external_name, '') || ' ' || COALESCE(sp.brand_raw, '');
  BEGIN
    qty := NULLIF(regexp_replace(COALESCE(sp.quantity_raw, ''), '[^0-9,\.]', '', 'g'), '')::numeric;
  EXCEPTION WHEN others THEN
    qty := NULL;
  END;
  u := NULLIF(lower(trim(COALESCE(sp.unit_raw, ''))), '');

  RETURN QUERY
  SELECT cp.id, cp.name, cp.brand, cp.quantity, cp.unit, cp.barcode, cp.image_url,
         c.name AS category_name,
         GREATEST(
           similarity(public.immutable_unaccent(cp.name), public.immutable_unaccent(q)),
           CASE WHEN sp.barcode_raw IS NOT NULL AND cp.barcode = sp.barcode_raw THEN 1.0 ELSE 0.0 END
         )::real AS score
  FROM public.canonical_products cp
  LEFT JOIN public.categories c ON c.id = cp.category_id
  WHERE cp.active = true
    -- Never suggest incompatible units/quantities
    AND (u IS NULL OR cp.unit IS NULL OR lower(cp.unit) = u)
    AND (qty IS NULL OR cp.quantity IS NULL OR cp.quantity = qty)
    AND (
      cp.barcode IS NOT NULL AND cp.barcode = sp.barcode_raw
      OR public.immutable_unaccent(cp.name) ILIKE '%' || public.immutable_unaccent(COALESCE(sp.external_name, '')) || '%'
      OR similarity(public.immutable_unaccent(cp.name), public.immutable_unaccent(q)) > 0.15
    )
  ORDER BY score DESC
  LIMIT 15;
END;
$$;

GRANT EXECUTE ON FUNCTION public.admin_suggest_canonical(uuid) TO authenticated;

-- =============================================================
-- Admin: link or unlink a store_product to a canonical.
-- Enforces unit/quantity compatibility when linking.
-- =============================================================
CREATE OR REPLACE FUNCTION public.admin_link_store_product(
  p_store_product_id uuid,
  p_canonical_id uuid
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  sp record;
  cp record;
  sp_qty numeric;
  sp_unit text;
BEGIN
  IF NOT public.has_role(auth.uid(), 'admin') THEN
    RAISE EXCEPTION 'not authorized';
  END IF;

  IF p_canonical_id IS NULL THEN
    UPDATE public.store_products SET canonical_product_id = NULL, updated_at = now()
    WHERE id = p_store_product_id;
    RETURN;
  END IF;

  SELECT quantity_raw, unit_raw INTO sp
  FROM public.store_products WHERE id = p_store_product_id;

  SELECT quantity, unit INTO cp
  FROM public.canonical_products WHERE id = p_canonical_id AND active = true;

  IF cp IS NULL THEN
    RAISE EXCEPTION 'canonical product not found';
  END IF;

  BEGIN
    sp_qty := NULLIF(regexp_replace(COALESCE(sp.quantity_raw, ''), '[^0-9,\.]', '', 'g'), '')::numeric;
  EXCEPTION WHEN others THEN
    sp_qty := NULL;
  END;
  sp_unit := NULLIF(lower(trim(COALESCE(sp.unit_raw, ''))), '');

  IF sp_qty IS NOT NULL AND cp.quantity IS NOT NULL AND cp.quantity <> sp_qty THEN
    RAISE EXCEPTION 'incompatible quantity (% vs %)', sp_qty, cp.quantity;
  END IF;
  IF sp_unit IS NOT NULL AND cp.unit IS NOT NULL AND lower(cp.unit) <> sp_unit THEN
    RAISE EXCEPTION 'incompatible unit (% vs %)', sp_unit, cp.unit;
  END IF;

  UPDATE public.store_products
     SET canonical_product_id = p_canonical_id, updated_at = now()
   WHERE id = p_store_product_id;
END;
$$;

GRANT EXECUTE ON FUNCTION public.admin_link_store_product(uuid, uuid) TO authenticated;
