-- Falso positivo real encontrado em produção: "Arroz Solito Tipo 1
-- Pacote 2000g" (Tauste) casou com "Arroz Tipo 1 Solito 5kg" (Spani)
-- — tamanhos bem diferentes. Causa: o Tauste grava esse produto com
-- quantidade ESTRUTURADA "1 pacote" (não captura os 2000g como
-- número em separado), e "pacote" não é uma unidade reconhecida —
-- então a checagem de quantidade virava "desconhecida, não bloqueia"
-- pros dois lados. Pra piorar, o texto do nome usado na comparação
-- de similaridade já teve a quantidade removida (isso ajuda a achar
-- nomes parecidos entre lojas, mas também apaga a única pista que
-- sobrava pra perceber que os tamanhos são diferentes).
--
-- Correção: quando o campo estruturado de quantidade não resolve um
-- tipo (peso/volume/contagem), tenta extrair um número+unidade
-- direto do texto do nome do produto como plano B, antes de
-- desistir e tratar como "desconhecida".
CREATE OR REPLACE FUNCTION public.extract_qty_from_name(name text)
RETURNS public.qty_normalized
LANGUAGE sql
IMMUTABLE PARALLEL SAFE
SET search_path = public, extensions
AS $$
  WITH m AS (
    SELECT regexp_match(
      coalesce(name, ''),
      '(\d+(?:[.,]\d+)?)\s*(kgs?|gramas?|grs?|g|mg|mls?|litros?|lts?|l)\y',
      'i'
    ) AS g
  )
  SELECT public.normalize_qty(
    NULLIF(replace(m.g[1], ',', '.'), '')::numeric,
    lower(m.g[2])
  )
  FROM m;
$$;

-- Quantidade "resolvida": usa o campo estruturado quando ele já
-- indica peso/volume/contagem reconhecível; senão tenta achar no
-- texto do nome (plano B); senão fica desconhecida mesmo.
CREATE OR REPLACE FUNCTION public.resolve_qty(qty numeric, unit text, name text)
RETURNS public.qty_normalized
LANGUAGE sql
IMMUTABLE PARALLEL SAFE
AS $$
  SELECT CASE
    WHEN (public.normalize_qty(qty, unit)).norm_kind IS NOT NULL THEN public.normalize_qty(qty, unit)
    ELSE public.extract_qty_from_name(name)
  END;
$$;

-- Agora recebe o nome de cada lado também, pra poder cair no plano B
-- de extrair a quantidade do texto quando o campo estruturado falha.
CREATE OR REPLACE FUNCTION public.qty_compatible(
  qty_a numeric, unit_a text, name_a text,
  qty_b numeric, unit_b text, name_b text
)
RETURNS boolean
LANGUAGE sql
IMMUTABLE PARALLEL SAFE
AS $$
  SELECT
    (public.resolve_qty(qty_a, unit_a, name_a)).norm_kind IS NULL
    OR (public.resolve_qty(qty_b, unit_b, name_b)).norm_kind IS NULL
    OR (
      (public.resolve_qty(qty_a, unit_a, name_a)).norm_kind = (public.resolve_qty(qty_b, unit_b, name_b)).norm_kind
      AND abs((public.resolve_qty(qty_a, unit_a, name_a)).norm_value - (public.resolve_qty(qty_b, unit_b, name_b)).norm_value)
          <= greatest((public.resolve_qty(qty_a, unit_a, name_a)).norm_value, (public.resolve_qty(qty_b, unit_b, name_b)).norm_value, 1) * 0.03
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
  v_sp_kind text;
  v_sp_brand text;
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
  v_sp_kind := (public.resolve_qty(qty, u, sp.external_name)).norm_kind;
  v_sp_brand := public.effective_brand(sp.brand_raw, sp.external_name);

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

  -- 2) Similaridade de nome com quantidade normalizada (estrutura
  -- ou, se não resolver, extraída do próprio texto do nome como
  -- plano B) e marca (coletada ou detectada no nome) como reforço.
  --   a) nome muito parecido (>=0.82): aceita mesmo sem quantidade
  --      ou marca resolvidas — o nome sozinho já é confiável.
  --   b) nome moderadamente parecido (>=0.60): só aceita se a
  --      quantidade resolveu dos DOIS lados e é compatível, E a
  --      marca é compatível (ou desconhecida).
  -- Em ambos os casos, a quantidade — quando resolvida dos dois
  -- lados, mesmo pelo plano B — precisa ser compatível; do
  -- contrário o candidato nem aparece (filtro do WHERE).
  -- Nunca casa com ficha do MESMO mercado.
  FOR cand IN
    SELECT cp.id,
           cp.brand,
           cp.name,
           (public.resolve_qty(cp.quantity, cp.unit, cp.name)).norm_kind AS cand_kind,
           similarity(public.immutable_unaccent(public.match_name_key(cp.name || ' ' || COALESCE(cp.brand, ''))), public.immutable_unaccent(q)) AS score
    FROM public.canonical_products cp
    WHERE cp.active = true
      AND public.qty_compatible(qty, u, sp.external_name, cp.quantity, cp.unit, cp.name)
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
           AND public.brand_compatible(v_sp_brand, public.effective_brand(cand.brand, cand.name)))
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
