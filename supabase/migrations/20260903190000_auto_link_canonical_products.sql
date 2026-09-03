-- =============================================================
-- Auto-associação de store_products a canonical_products.
--
-- Até aqui, toda associação de um produto coletado a um produto
-- canônico exigia um clique manual em /admin/pendentes. Com 3
-- coletores rodando diariamente, isso virou um gargalo (milhares
-- de produtos por dia, backlog de dezenas de milhares). Esta
-- função automatiza a associação, chamada pelo endpoint de
-- ingestão (service_role) logo após cada upsert de store_product.
--
-- Estratégia, em ordem de confiança — nunca funde produtos
-- diferentes por engano; na pior hipótese cria um canônico
-- duplicado (revisável depois em /admin/produtos-canonicos), mas
-- nunca mistura o preço de itens distintos numa mesma comparação:
--   1) Código de barras já existente em outro canônico -> vincula.
--   2) Similaridade de nome/marca acima de um limiar alto, com
--      unidade/quantidade compatíveis (mesma regra do
--      admin_suggest_canonical) -> vincula ao existente.
--   3) Nenhum candidato confiável -> cria um canônico novo a
--      partir dos dados coletados e vincula.
-- =============================================================
CREATE OR REPLACE FUNCTION public.auto_link_or_create_canonical(p_store_product_id uuid)
RETURNS TABLE (canonical_product_id uuid, match_type text, score real)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, extensions
AS $$
DECLARE
  sp record;
  q text;
  qty numeric;
  u text;
  v_barcode text;
  v_match_id uuid;
  v_best record;
  v_new_id uuid;
BEGIN
  SELECT id, external_name, brand_raw, barcode_raw, quantity_raw, unit_raw,
         image_url, canonical_product_id
    INTO sp
  FROM public.store_products
  WHERE store_products.id = p_store_product_id;

  IF sp IS NULL THEN
    RETURN;
  END IF;

  IF sp.canonical_product_id IS NOT NULL THEN
    RETURN QUERY SELECT sp.canonical_product_id, 'already_linked'::text, 1.0::real;
    RETURN;
  END IF;

  v_barcode := NULLIF(btrim(sp.barcode_raw), '');
  q := COALESCE(sp.external_name, '') || ' ' || COALESCE(sp.brand_raw, '');

  BEGIN
    qty := NULLIF(regexp_replace(COALESCE(sp.quantity_raw, ''), '[^0-9,\.]', '', 'g'), '')::numeric;
  EXCEPTION WHEN others THEN
    qty := NULL;
  END;
  u := NULLIF(lower(trim(COALESCE(sp.unit_raw, ''))), '');

  -- 1) Código de barras: sinal mais forte que existe, quando presente.
  IF v_barcode IS NOT NULL THEN
    SELECT id INTO v_match_id
    FROM public.canonical_products
    WHERE barcode = v_barcode AND active = true
    LIMIT 1;

    IF v_match_id IS NOT NULL THEN
      UPDATE public.store_products
         SET canonical_product_id = v_match_id, updated_at = now()
       WHERE id = p_store_product_id;
      RETURN QUERY SELECT v_match_id, 'barcode_exact'::text, 1.0::real;
      RETURN;
    END IF;
  END IF;

  -- 2) Melhor candidato por nome/marca, respeitando a mesma regra de
  -- compatibilidade de unidade/quantidade do admin_suggest_canonical.
  SELECT cp.id AS id,
         similarity(public.immutable_unaccent(cp.name), public.immutable_unaccent(q)) AS score
    INTO v_best
  FROM public.canonical_products cp
  WHERE cp.active = true
    AND (u IS NULL OR cp.unit IS NULL OR lower(cp.unit) = u)
    AND (qty IS NULL OR cp.quantity IS NULL OR cp.quantity = qty)
  ORDER BY similarity(public.immutable_unaccent(cp.name), public.immutable_unaccent(q)) DESC
  LIMIT 1;

  IF v_best.id IS NOT NULL AND v_best.score >= 0.82 THEN
    UPDATE public.store_products
       SET canonical_product_id = v_best.id, updated_at = now()
     WHERE id = p_store_product_id;
    RETURN QUERY SELECT v_best.id, 'name_similarity'::text, v_best.score;
    RETURN;
  END IF;

  -- 3) Nenhum candidato confiável: cria um canônico novo a partir do
  -- produto coletado.
  BEGIN
    INSERT INTO public.canonical_products (name, brand, quantity, unit, barcode, image_url, active)
    VALUES (sp.external_name, sp.brand_raw, qty, u, v_barcode, sp.image_url, true)
    RETURNING id INTO v_new_id;
  EXCEPTION WHEN unique_violation THEN
    -- Concorrência: outro processo criou um canônico com o mesmo
    -- código de barras entre nossa checagem e este insert.
    SELECT id INTO v_new_id FROM public.canonical_products WHERE barcode = v_barcode;
  END;

  UPDATE public.store_products
     SET canonical_product_id = v_new_id, updated_at = now()
   WHERE id = p_store_product_id;

  RETURN QUERY SELECT v_new_id, 'auto_created'::text, 0.0::real;
END;
$$;

REVOKE ALL ON FUNCTION public.auto_link_or_create_canonical(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.auto_link_or_create_canonical(uuid) TO service_role;

-- =============================================================
-- Backfill: associa automaticamente os store_products já
-- coletados que ainda não têm canônico (aplicado uma vez, na
-- migração). Processa em lotes para não segurar uma transação
-- gigante nem estourar o tempo de statement.
-- =============================================================
DO $$
DECLARE
  r record;
  processed integer := 0;
BEGIN
  FOR r IN
    SELECT id FROM public.store_products
    WHERE canonical_product_id IS NULL AND active = true
  LOOP
    PERFORM public.auto_link_or_create_canonical(r.id);
    processed := processed + 1;
    IF processed % 500 = 0 THEN
      RAISE NOTICE 'auto_link_or_create_canonical backfill: % produtos processados', processed;
    END IF;
  END LOOP;

  RAISE NOTICE 'auto_link_or_create_canonical backfill concluído: % produtos processados', processed;
END $$;
