-- =============================================================
-- Casador de produtos canônicos mais inteligente.
--
-- Diagnóstico: produtos claramente iguais entre lojas não estavam
-- casando porque:
--   1) Tauste/Spani gravam quantidade em unidade "crua" (300 = 300g),
--      enquanto o Confiança grava sempre em quilos/litros decimais
--      (0.3 = 300g). A comparação de quantidade era numérica direta,
--      então "300" nunca era igual a "0.3" mesmo sendo o mesmo
--      produto — bloqueava quase todo cruzamento com o Confiança.
--   2) O limiar de similaridade de nome (0.82) era alto demais pra
--      nomes com convenções de escrita diferentes por loja (marca no
--      início vs no meio, abreviações, etc.), e a marca do Confiança
--      nunca é coletada (sempre null), então não tinha um segundo
--      sinal pra compensar um nome um pouco diferente.
--
-- Correção: normaliza quantidade pra uma unidade base (peso em
-- gramas, volume em ml, contagem em unidades) antes de comparar, e
-- usa dois níveis de confiança: nome muito parecido (>=0.82) aceita
-- sozinho como antes; nome moderadamente parecido (>=0.55) só aceita
-- se as marcas também forem compatíveis (ou desconhecidas). Também
-- limpa números/unidades do texto antes de comparar nomes, pra não
-- penalizar a similaridade por causa da própria quantidade escrita
-- diferente ("300g" vs "300 gramas").
-- =============================================================

DROP TYPE IF EXISTS public.qty_normalized CASCADE;
CREATE TYPE public.qty_normalized AS (norm_value numeric, norm_kind text);

CREATE OR REPLACE FUNCTION public.normalize_qty(qty numeric, unit text)
RETURNS public.qty_normalized
LANGUAGE sql
IMMUTABLE PARALLEL SAFE
AS $$
  SELECT
    (CASE lower(trim(coalesce(unit, '')))
      WHEN 'g' THEN qty WHEN 'gr' THEN qty WHEN 'grama' THEN qty WHEN 'gramas' THEN qty
      WHEN 'kg' THEN qty * 1000 WHEN 'quilo' THEN qty * 1000 WHEN 'quilos' THEN qty * 1000
      WHEN 'mg' THEN qty / 1000
      WHEN 'ml' THEN qty WHEN 'mililitro' THEN qty WHEN 'mililitros' THEN qty
      WHEN 'l' THEN qty * 1000 WHEN 'lo' THEN qty * 1000 WHEN 'lt' THEN qty * 1000
      WHEN 'litro' THEN qty * 1000 WHEN 'litros' THEN qty * 1000
      WHEN 'un' THEN qty WHEN 'und' THEN qty WHEN 'unid' THEN qty
      WHEN 'unidade' THEN qty WHEN 'unidades' THEN qty
      ELSE NULL
    END)::numeric AS norm_value,
    (CASE lower(trim(coalesce(unit, '')))
      WHEN 'g' THEN 'mass' WHEN 'gr' THEN 'mass' WHEN 'grama' THEN 'mass' WHEN 'gramas' THEN 'mass'
      WHEN 'kg' THEN 'mass' WHEN 'quilo' THEN 'mass' WHEN 'quilos' THEN 'mass' WHEN 'mg' THEN 'mass'
      WHEN 'ml' THEN 'volume' WHEN 'mililitro' THEN 'volume' WHEN 'mililitros' THEN 'volume'
      WHEN 'l' THEN 'volume' WHEN 'lo' THEN 'volume' WHEN 'lt' THEN 'volume'
      WHEN 'litro' THEN 'volume' WHEN 'litros' THEN 'volume'
      WHEN 'un' THEN 'count' WHEN 'und' THEN 'count' WHEN 'unid' THEN 'count'
      WHEN 'unidade' THEN 'count' WHEN 'unidades' THEN 'count'
      ELSE NULL
    END)::text AS norm_kind;
$$;

-- Duas quantidades normalizadas são compatíveis quando: alguma das
-- duas é desconhecida (não bloqueia — mesmo comportamento permissivo
-- de antes), ou quando o tipo bate (peso com peso, volume com
-- volume, contagem com contagem) e o valor é igual dentro de uma
-- margem pequena (rótulos arredondam: "44g" vs "45g").
CREATE OR REPLACE FUNCTION public.qty_compatible(
  qty_a numeric, unit_a text, qty_b numeric, unit_b text
)
RETURNS boolean
LANGUAGE sql
IMMUTABLE PARALLEL SAFE
AS $$
  SELECT
    qty_a IS NULL OR qty_b IS NULL OR (
      (public.normalize_qty(qty_a, unit_a)).norm_kind IS NULL
      OR (public.normalize_qty(qty_b, unit_b)).norm_kind IS NULL
      OR (
        (public.normalize_qty(qty_a, unit_a)).norm_kind = (public.normalize_qty(qty_b, unit_b)).norm_kind
        AND abs((public.normalize_qty(qty_a, unit_a)).norm_value - (public.normalize_qty(qty_b, unit_b)).norm_value)
            <= greatest((public.normalize_qty(qty_a, unit_a)).norm_value, (public.normalize_qty(qty_b, unit_b)).norm_value, 1) * 0.03
      )
    );
$$;

-- Remove número+unidade do texto antes de comparar nomes, pra não
-- penalizar a similaridade por causa só da quantidade escrita
-- diferente entre lojas.
CREATE OR REPLACE FUNCTION public.match_name_key(raw text)
RETURNS text
LANGUAGE sql
IMMUTABLE PARALLEL SAFE
AS $$
  SELECT trim(regexp_replace(
    regexp_replace(
      coalesce(raw, ''),
      '\d+([.,]\d+)?\s*(kgs?|gramas?|grs?|g|mg|mls?|litros?|lts?|l|un|und|unid(ade)?s?|pacotes?|pcts?|caixas?|cxs?|c\s*/\s*\d+)\y',
      ' ', 'gi'
    ),
    '\s+', ' ', 'g'
  ));
$$;

-- Duas marcas são compatíveis quando: alguma é desconhecida (o
-- Confiança nunca coleta marca hoje, então isso é o caso comum), são
-- iguais, uma contém a outra, ou são bem parecidas.
CREATE OR REPLACE FUNCTION public.brand_compatible(brand_a text, brand_b text)
RETURNS boolean
LANGUAGE sql
IMMUTABLE PARALLEL SAFE
SET search_path = public, extensions
AS $$
  SELECT
    brand_a IS NULL OR brand_b IS NULL OR btrim(brand_a) = '' OR btrim(brand_b) = '' OR (
      public.immutable_unaccent(brand_a) = public.immutable_unaccent(brand_b)
      OR public.immutable_unaccent(brand_a) ILIKE '%' || public.immutable_unaccent(brand_b) || '%'
      OR public.immutable_unaccent(brand_b) ILIKE '%' || public.immutable_unaccent(brand_a) || '%'
      OR similarity(public.immutable_unaccent(brand_a), public.immutable_unaccent(brand_b)) >= 0.5
    );
$$;

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
  -- Considera os melhores candidatos e aceita o primeiro que:
  --   a) tem nome muito parecido (>=0.82), independente da marca; ou
  --   b) tem nome moderadamente parecido (>=0.55) E marca compatível
  --      (ou desconhecida — caso comum do Confiança).
  -- Nunca casa com ficha do MESMO mercado (isso não é comparação de
  -- preço de verdade).
  FOR cand IN
    SELECT cp.id,
           cp.brand,
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
    IF cand.score >= 0.82 OR (cand.score >= 0.55 AND public.brand_compatible(sp.brand_raw, cand.brand)) THEN
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
