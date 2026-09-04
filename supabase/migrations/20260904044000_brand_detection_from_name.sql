-- Testando com dados reais, o nível de confiança moderado ainda
-- deixava passar alguns pares errados quando o nome é curto e
-- genérico e a marca é o único diferencial de verdade — ex.:
-- "Refrigerante Pet Frutuba 2l Laranja" vs "Refrigerante Fanta
-- Laranja Pet 2000ml" (marcas diferentes!), ou "Leite Longa Vida
-- Tirol..." vs "...Lider...". Como o Confiança nunca coleta marca
-- (campo sempre nulo) e mesmo Tauste/Spani às vezes deixam em
-- branco, não dava pra confiar só no campo `brand`.
--
-- Adiciona detecção de marca a partir do próprio nome do produto,
-- usando uma lista das marcas mais comuns nos mercados de Marília.
-- Não é (nem tenta ser) uma lista completa — é uma rede de segurança
-- adicional: quando o campo `brand` está vazio, tenta achar uma
-- marca conhecida dentro do nome antes de considerar "desconhecida e
-- não bloqueia".
CREATE OR REPLACE FUNCTION public.detect_brand_token(name text)
RETURNS text
LANGUAGE sql
IMMUTABLE PARALLEL SAFE
SET search_path = public, extensions
AS $$
  SELECT b.brand
  FROM (VALUES
    ('nescafe'), ('3 coracoes'), ('melitta'), ('pilao'), ('iguacu'), ('caboclo'), ('start cafe'),
    ('jaguari'), ('lor'), ('dolce gusto'), ('baggio'), ('illy'),
    ('colgate'), ('sorriso'), ('sensodyne'), ('oral-b'), ('oral b'), ('close-up'), ('close up'),
    ('nivea'), ('rexona'), ('dove'), ('giovanna baby'), ('above'), ('monange'), ('eucerin'),
    ('fanta'), ('coca-cola'), ('coca cola'), ('sprite'), ('pepsi'), ('antarctica'), ('guarana antarctica'),
    ('h2oh'), ('schweppes'), ('sukita'), ('frutuba'), ('fys'), ('conti'), ('itubaina'), ('dolly'),
    ('itambe'), ('italac'), ('piracanjuba'), ('ninho'), ('molico'), ('parmalat'), ('tirol'), ('lider'), ('quata'),
    ('danone'), ('danoninho'), ('vigor'), ('nestle'), ('betania'),
    ('lux'), ('protex'), ('palmolive'), ('phebo'), ('granado'),
    ('trakinas'), ('negresco'), ('marilan'), ('bauducco'), ('passatempo'), ('club social'), ('richester'), ('adria'),
    ('liza'), ('soya'), ('mazola'), ('cocamar'), ('vitaliv'),
    ('uniao'), ('santa isabel'), ('caravelas'), ('da barra'), ('alto alegre'),
    ('lebre'), ('cisne'), ('cisne parrilla'),
    ('pampers'), ('babysec'), ('pom pom'), ('huggies'), ('turma da monica'), ('personal baby'),
    ('yodel'), ('yakult'), ('activia'),
    ('kelloggs'), ('nesfit'), ('mais vita'), ('quaker'),
    ('elseve'), ('tresemme'), ('seda'), ('pantene'), ('novex'), ('haskell'),
    ('listerine'), ('cepacol'), ('plax'),
    ('quero'), ('predilecta'), ('gomes da costa'), ('coqueiro'), ('fugini'), ('cica'), ('heinz'), ('etti'),
    ('seara'), ('sadia'), ('perdigao'), ('friboi'), ('swift'), ('aurora'),
    ('del valle'), ('maguary'), ('sufresh'), ('cutrale'),
    ('tio joao'), ('camil'), ('kicaldo'), ('prato fino'), ('urbano'), ('namorado'),
    ('nivea men'), ('gillette'), ('bic')
  ) AS b(brand)
  WHERE public.immutable_unaccent(coalesce(name, '')) ILIKE '%' || b.brand || '%'
  ORDER BY length(b.brand) DESC
  LIMIT 1;
$$;

-- Marca "efetiva": o campo já coletado, ou (se vazio) a marca
-- detectada no próprio nome do produto.
CREATE OR REPLACE FUNCTION public.effective_brand(brand_raw text, name text)
RETURNS text
LANGUAGE sql
IMMUTABLE PARALLEL SAFE
AS $$
  SELECT COALESCE(NULLIF(btrim(brand_raw), ''), public.detect_brand_token(name));
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
  v_sp_kind := (public.normalize_qty(qty, u)).norm_kind;
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

  -- 2) Similaridade de nome com quantidade normalizada e marca
  -- (coletada ou detectada no nome) como sinal de reforço.
  --   a) nome muito parecido (>=0.82): aceita mesmo sem quantidade
  --      ou marca resolvidas — o nome sozinho já é confiável.
  --   b) nome moderadamente parecido (>=0.60): só aceita se a
  --      quantidade normalizada resolveu dos DOIS lados e é
  --      compatível, E a marca (efetiva) é compatível ou
  --      desconhecida dos dois lados.
  -- Nunca casa com ficha do MESMO mercado.
  FOR cand IN
    SELECT cp.id,
           cp.brand,
           cp.name,
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
