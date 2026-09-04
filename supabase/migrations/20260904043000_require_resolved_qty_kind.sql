-- Mais um caso encontrado testando com dados reais: a checagem
-- "quantidade conhecida dos dois lados" olhava só o número bruto, mas
-- a UNIDADE pode estar nula mesmo com o número presente (ex.:
-- "Refrigerado.1,3l" sem espaço — o coletor pegou "1.3" mas não
-- achou a unidade). Nesse caso normalize_qty não resolve tipo
-- (peso/volume/contagem) e a checagem antiga deixava passar mesmo
-- assim. Agora exige que a normalização tenha resolvido (norm_kind
-- não nulo) dos dois lados pro nível de confiança moderado.
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
  v_barcode_norm text;
  v_match_id uuid;
  v_new_id uuid;
  v_sp_kind text;
  cand record;
BEGIN
  SELECT store_products.id, store_products.store_id, store_products.external_name,
         store_products.brand_raw, store_products.barcode_raw, store_products.quantity_raw,
         store_products.unit_raw, store_products.image_url, store_products.canonical_product_id
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

  v_barcode_norm := NULLIF(regexp_replace(coalesce(sp.barcode_raw, ''), '\D', '', 'g'), '');
  q := public.match_name_key(coalesce(sp.external_name, '') || ' ' || coalesce(sp.brand_raw, ''));

  BEGIN
    qty := NULLIF(regexp_replace(COALESCE(sp.quantity_raw, ''), '[^0-9,\.]', '', 'g'), '')::numeric;
  EXCEPTION WHEN others THEN
    qty := NULL;
  END;
  u := NULLIF(lower(trim(COALESCE(sp.unit_raw, ''))), '');
  v_sp_kind := (public.normalize_qty(qty, u)).norm_kind;

  -- 1) Código de barras (normalizado: só dígitos, aceita a variação
  -- com/sem zero à esquerda entre EAN-13 e UPC-A). Identidade real,
  -- pode unir fichas até do mesmo mercado.
  IF v_barcode_norm IS NOT NULL AND length(v_barcode_norm) >= 8 THEN
    SELECT cp.id INTO v_match_id
    FROM public.canonical_products cp
    WHERE cp.active = true
      AND cp.barcode IS NOT NULL
      AND (
        regexp_replace(cp.barcode, '\D', '', 'g') = v_barcode_norm
        OR regexp_replace(cp.barcode, '\D', '', 'g') = ('0' || v_barcode_norm)
        OR ('0' || regexp_replace(cp.barcode, '\D', '', 'g')) = v_barcode_norm
      )
    LIMIT 1;

    IF v_match_id IS NOT NULL THEN
      UPDATE public.store_products
         SET canonical_product_id = v_match_id, updated_at = now()
       WHERE id = p_store_product_id;
      RETURN QUERY SELECT v_match_id, 'barcode_exact'::text, 1.0::real;
      RETURN;
    END IF;
  END IF;

  -- 2) Similaridade de nome com quantidade normalizada (peso/volume
  -- convertidos pra base comum) e marca como sinal de reforço.
  --   a) nome muito parecido (>=0.82): aceita mesmo se a quantidade
  --      de um dos lados não foi interpretada — o nome sozinho já é
  --      confiável nesse patamar.
  --   b) nome moderadamente parecido (>=0.60): só aceita se a
  --      normalização de quantidade resolveu um tipo (peso/volume/
  --      contagem) dos DOIS lados e os valores são compatíveis, E a
  --      marca é compatível (ou desconhecida).
  -- Nunca casa com ficha do MESMO mercado.
  FOR cand IN
    SELECT cp.id,
           cp.brand,
           (public.normalize_qty(cp.quantity, cp.unit)).norm_kind AS cand_kind,
           similarity(public.immutable_unaccent(public.match_name_key(cp.name || ' ' || COALESCE(cp.brand, ''))), public.immutable_unaccent(q)) AS score
    FROM public.canonical_products cp
    WHERE cp.active = true
      AND public.qty_compatible(qty, u, cp.quantity, cp.unit)
      AND public.immutable_unaccent(cp.name) % public.immutable_unaccent(q)
      AND NOT EXISTS (
        SELECT 1 FROM public.store_products other
        WHERE other.canonical_product_id = cp.id
          AND other.store_id = sp.store_id
      )
    ORDER BY score DESC
    LIMIT 5
  LOOP
    IF cand.score >= 0.82
       OR (cand.score >= 0.60 AND v_sp_kind IS NOT NULL AND cand.cand_kind IS NOT NULL
           AND public.brand_compatible(sp.brand_raw, cand.brand))
    THEN
      UPDATE public.store_products
         SET canonical_product_id = cand.id, updated_at = now()
       WHERE id = p_store_product_id;
      RETURN QUERY SELECT cand.id, 'name_similarity'::text, cand.score;
      RETURN;
    END IF;
  END LOOP;

  -- 3) Nenhum candidato confiável: cria um canônico novo.
  BEGIN
    INSERT INTO public.canonical_products (name, brand, quantity, unit, barcode, image_url, active)
    VALUES (sp.external_name, sp.brand_raw, qty, u, v_barcode_norm, sp.image_url, true)
    RETURNING id INTO v_new_id;
  EXCEPTION WHEN unique_violation THEN
    SELECT cp.id INTO v_new_id FROM public.canonical_products cp WHERE cp.barcode = v_barcode_norm;
  END;

  UPDATE public.store_products
     SET canonical_product_id = v_new_id, updated_at = now()
   WHERE id = p_store_product_id;

  RETURN QUERY SELECT v_new_id, 'auto_created'::text, 0.0::real;
END;
$$;

REVOKE ALL ON FUNCTION public.auto_link_or_create_canonical(uuid) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.auto_link_or_create_canonical(uuid) TO service_role;
