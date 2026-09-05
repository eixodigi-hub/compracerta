-- Nenhum coletor mapeia uma categoria bruta "bebês" além das fraldas do
-- Tauste — mamadeira, chupeta e lenço/toalha umedecida de bebê chegaram
-- pela categoria genérica de higiene/perfumaria de cada loja e ficaram
-- presos em "Higiene pessoal". Corrige o que já foi coletado. Fica de
-- fora fralda geriátrica/adulto (usa o mesmo termo "fralda", mas não é
-- produto de bebê) e lenço umedecido feminino/íntimo/antisséptico
-- genérico (mesmo termo "lenço umedecido", mas não é de bebê).
UPDATE public.canonical_products cp
SET category_id = (SELECT id FROM public.categories WHERE slug = 'bebes')
WHERE cp.active = true
  AND cp.category_id IS DISTINCT FROM (SELECT id FROM public.categories WHERE slug = 'bebes')
  AND (
    public.immutable_unaccent(cp.name) ILIKE '%mamadeira%'
    OR public.immutable_unaccent(cp.name) ILIKE '%chupeta%'
    OR public.immutable_unaccent(cp.name) ILIKE '%toalha%umedecid%'
    OR (
      public.immutable_unaccent(cp.name) ILIKE '%lenco%umedecid%'
      AND (
        public.immutable_unaccent(cp.name) ILIKE '%baby%'
        OR public.immutable_unaccent(cp.name) ILIKE '%bebe%'
        OR public.immutable_unaccent(cp.name) ILIKE '%infantil%'
        OR public.immutable_unaccent(cp.name) ILIKE '%nascido%'
        OR public.immutable_unaccent(cp.name) ILIKE '%johnson%'
        OR public.immutable_unaccent(cp.name) ILIKE '%pampers%'
        OR public.immutable_unaccent(cp.name) ILIKE '%huggies%'
        OR public.immutable_unaccent(cp.name) ILIKE '%cotondela%'
      )
      AND public.immutable_unaccent(cp.name) NOT ILIKE '%feminin%'
      AND public.immutable_unaccent(cp.name) NOT ILIKE '%intimo%'
      AND public.immutable_unaccent(cp.name) NOT ILIKE '%intima%'
      AND public.immutable_unaccent(cp.name) NOT ILIKE '%antissept%'
    )
  );
