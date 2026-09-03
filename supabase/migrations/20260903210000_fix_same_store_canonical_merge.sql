-- =============================================================
-- Corrige auto_link_or_create_canonical: casamento por similaridade
-- de nome estava juntando produtos DIFERENTES do MESMO mercado no
-- mesmo canônico (ex.: "Tauste vs Tauste" na comparação de preços,
-- ou 3 linhas do Spani repetidas no mesmo card).
--
-- Um canônico serve pra comparar o MESMO item entre mercados
-- DIFERENTES. Duas fichas de produto do mesmo mercado com nomes
-- parecidos (variações de sabor/tamanho) nunca deveriam entrar no
-- mesmo canônico só por similaridade de texto — isso não é uma
-- comparação de preço de verdade, é o mercado "competindo consigo
-- mesmo". Código de barras continua podendo unir duas fichas do
-- mesmo mercado (é identidade real, não estimativa).
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

  v_barcode := NULLIF(btrim(sp.barcode_raw), '');
  q := COALESCE(sp.external_name, '') || ' ' || COALESCE(sp.brand_raw, '');

  BEGIN
    qty := NULLIF(regexp_replace(COALESCE(sp.quantity_raw, ''), '[^0-9,\.]', '', 'g'), '')::numeric;
  EXCEPTION WHEN others THEN
    qty := NULL;
  END;
  u := NULLIF(lower(trim(COALESCE(sp.unit_raw, ''))), '');

  -- 1) Código de barras: identidade real, pode unir fichas até do
  -- mesmo mercado (ex.: SKU duplicado por engano na origem).
  IF v_barcode IS NOT NULL THEN
    SELECT cp.id INTO v_match_id
    FROM public.canonical_products cp
    WHERE cp.barcode = v_barcode AND cp.active = true
    LIMIT 1;

    IF v_match_id IS NOT NULL THEN
      UPDATE public.store_products
         SET canonical_product_id = v_match_id, updated_at = now()
       WHERE id = p_store_product_id;
      RETURN QUERY SELECT v_match_id, 'barcode_exact'::text, 1.0::real;
      RETURN;
    END IF;
  END IF;

  -- 2) Similaridade de nome: só considera canônicos que ainda não têm
  -- nenhuma ficha vinculada do MESMO mercado — evita "mercado vs
  -- mercado" na comparação.
  SELECT cp.id AS id,
         similarity(public.immutable_unaccent(cp.name), public.immutable_unaccent(q)) AS score
    INTO v_best
  FROM public.canonical_products cp
  WHERE cp.active = true
    AND (u IS NULL OR cp.unit IS NULL OR lower(cp.unit) = u)
    AND (qty IS NULL OR cp.quantity IS NULL OR cp.quantity = qty)
    AND public.immutable_unaccent(cp.name) % public.immutable_unaccent(q)
    AND NOT EXISTS (
      SELECT 1 FROM public.store_products other
      WHERE other.canonical_product_id = cp.id
        AND other.store_id = sp.store_id
    )
  ORDER BY similarity(public.immutable_unaccent(cp.name), public.immutable_unaccent(q)) DESC
  LIMIT 1;

  IF v_best.id IS NOT NULL AND v_best.score >= 0.82 THEN
    UPDATE public.store_products
       SET canonical_product_id = v_best.id, updated_at = now()
     WHERE id = p_store_product_id;
    RETURN QUERY SELECT v_best.id, 'name_similarity'::text, v_best.score;
    RETURN;
  END IF;

  -- 3) Nenhum candidato confiável: cria um canônico novo.
  BEGIN
    INSERT INTO public.canonical_products (name, brand, quantity, unit, barcode, image_url, active)
    VALUES (sp.external_name, sp.brand_raw, qty, u, v_barcode, sp.image_url, true)
    RETURNING id INTO v_new_id;
  EXCEPTION WHEN unique_violation THEN
    SELECT cp.id INTO v_new_id FROM public.canonical_products cp WHERE cp.barcode = v_barcode;
  END;

  UPDATE public.store_products
     SET canonical_product_id = v_new_id, updated_at = now()
   WHERE id = p_store_product_id;

  RETURN QUERY SELECT v_new_id, 'auto_created'::text, 0.0::real;
END;
$$;

REVOKE ALL ON FUNCTION public.auto_link_or_create_canonical(uuid) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.auto_link_or_create_canonical(uuid) TO service_role;

-- =============================================================
-- Repara os dados já afetados: para cada canônico com mais de uma
-- ficha do mesmo mercado vinculada, mantém a mais antiga e desvincula
-- as demais. Em seguida, roda o casador (já corrigido) de novo nelas
-- — cada uma vira seu próprio canônico ou casa com um mercado
-- diferente de verdade, nunca mais com o próprio mercado de origem.
-- =============================================================
WITH dup AS (
  SELECT sp.id,
         row_number() OVER (
           PARTITION BY sp.canonical_product_id, sp.store_id
           ORDER BY sp.created_at ASC
         ) AS rn
  FROM public.store_products sp
  WHERE sp.canonical_product_id IS NOT NULL
)
UPDATE public.store_products sp
   SET canonical_product_id = NULL, updated_at = now()
  FROM dup
 WHERE sp.id = dup.id
   AND dup.rn > 1;

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
      RAISE NOTICE 'reparo mesmo-mercado: % produtos reprocessados', processed;
    END IF;
  END LOOP;

  RAISE NOTICE 'reparo mesmo-mercado concluído: % produtos reprocessados', processed;
END $$;
