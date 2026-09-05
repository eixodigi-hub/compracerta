-- A tela inicial estava sempre trazendo várias variações do mesmo tipo de
-- produto no topo de cada categoria (ex.: "Alimentos" cheio de cafés),
-- porque o ranking anterior só olhava promoção/desconto/loja, sem
-- considerar que produtos diferentes ("Arroz", "Feijão", "Café", "Milho"…)
-- deveriam se revezar. Esta versão:
--   1) agrupa por "tipo" (primeira palavra do nome, sem acento — a
--      convenção de nomenclatura do catálogo já começa pelo produto:
--      "Arroz Famil 5kg", "Café Pilão 500g", "Feijão Jalo Camil 500g");
--   2) faz round-robin por tipo — pega o melhor de cada tipo antes de
--      repetir qualquer tipo, então a categoria mostra vários produtos
--      diferentes em vez de 10 variações do mesmo;
--   3) embaralha com random() a cada chamada, pra não travar sempre na
--      mesma ordem entre tipos empatados.
CREATE OR REPLACE FUNCTION public.home_category_feed(
  products_per_category integer DEFAULT 10
)
RETURNS TABLE(
  category_id uuid,
  category_slug text,
  category_name text,
  category_icon text,
  id uuid,
  name text,
  brand text,
  quantity numeric,
  unit text,
  image_url text,
  barcode text,
  min_price numeric,
  reference_price numeric,
  max_discount_pct numeric,
  market_count integer,
  last_updated timestamp with time zone,
  has_promotion boolean,
  offers jsonb
)
LANGUAGE sql
VOLATILE
SET search_path TO 'public'
AS $function$
  WITH rows AS (
    SELECT
      cp.id AS product_id,
      cp.name,
      cp.brand,
      cp.quantity,
      cp.unit,
      COALESCE(cp.image_url, sp.image_url) AS image_url,
      cp.barcode,
      cp.category_id,
      c.slug AS category_slug,
      c.name AS category_name,
      c.icon AS category_icon,
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
        ELSE cur.regular_price
      END AS effective_price,
      cur.promotion_text,
      cur.promotion_end_at,
      cur.collected_at
    FROM public.canonical_products cp
    JOIN public.categories c ON c.id = cp.category_id
    JOIN public.store_products sp ON sp.canonical_product_id = cp.id
    JOIN public.current_prices cur ON cur.store_product_id = sp.id
    JOIN public.stores s ON s.id = sp.store_id
    WHERE cp.active = true
      AND sp.active = true
      AND sp.available = true
      AND s.active = true
      AND cur.in_stock = true
  ),
  grouped AS (
    SELECT
      product_id AS id,
      name,
      brand,
      quantity,
      unit,
      MAX(image_url) FILTER (WHERE image_url IS NOT NULL) AS image_url,
      barcode,
      category_id,
      category_slug,
      category_name,
      category_icon,
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
      ) AS raw_offers
    FROM rows
    GROUP BY product_id, name, brand, quantity, unit, barcode, category_id, category_slug, category_name, category_icon
  ),
  marked AS (
    SELECT
      g.id, g.name, g.brand, g.quantity, g.unit, g.image_url, g.barcode,
      g.category_id, g.category_slug, g.category_name, g.category_icon,
      g.min_price, g.reference_price, g.max_discount_pct, g.market_count,
      g.last_updated, g.has_promotion,
      -- "Tipo" do produto: primeira palavra do nome, sem acento (Arroz,
      -- Feijão, Café, Milho…). É o que separa um carrossel monótono de um
      -- variado.
      split_part(public.immutable_unaccent(g.name), ' ', 1) AS name_bucket,
      (
        SELECT jsonb_agg(
          CASE
            WHEN (offer->>'effective_price')::numeric = g.min_price
              THEN jsonb_set(offer, '{is_lowest}', 'true'::jsonb, false)
            ELSE offer
          END
          ORDER BY (offer->>'effective_price')::numeric ASC NULLS LAST, offer->>'store_name' ASC
        )
        FROM jsonb_array_elements(g.raw_offers) AS offer
      ) AS offers
    FROM grouped g
  ),
  bucket_ranked AS (
    SELECT
      m.*,
      ROW_NUMBER() OVER (
        PARTITION BY m.category_id, m.name_bucket
        ORDER BY (m.market_count > 1) DESC, m.has_promotion DESC, m.max_discount_pct DESC, random()
      ) AS bucket_rank
    FROM marked m
  ),
  final_ranked AS (
    SELECT
      br.*,
      -- Escolhe QUAIS tipos entram só por rodízio + sorteio — se também
      -- olhasse promoção/mercados aqui, tipo sem oferta no momento (ex.:
      -- arroz, feijão) sempre perderia pra tipo com oferta (ex.: café),
      -- voltando ao problema original. Esses critérios já decidiram QUEM
      -- representa cada tipo lá em cima, no bucket_rank.
      ROW_NUMBER() OVER (
        PARTITION BY br.category_id
        ORDER BY br.bucket_rank ASC, random()
      ) AS rn
    FROM bucket_ranked br
  )
  SELECT
    category_id, category_slug, category_name, category_icon,
    id, name, brand, quantity, unit, image_url, barcode,
    min_price, reference_price, max_discount_pct, market_count,
    last_updated, has_promotion, offers
  FROM final_ranked
  WHERE rn <= GREATEST(products_per_category, 1)
  ORDER BY category_name ASC, rn ASC;
$function$;

GRANT EXECUTE ON FUNCTION public.home_category_feed(integer) TO anon, authenticated, service_role;
