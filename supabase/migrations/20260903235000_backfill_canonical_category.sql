-- Preenche canonical_products.category_id retroativamente para produtos já
-- coletados antes da correção do pipeline de ingestão, usando a categoria
-- bruta que cada coletor grava em store_product_collection_scopes.scope_key.
-- Mesmo mapeamento usado em src/lib/source-category-map.ts.
with mapping (scope_key, slug) as (
  values
    ('arroz', 'alimentos'), ('feijao', 'alimentos'), ('cafe', 'alimentos'),
    ('leite', 'alimentos'), ('oleo', 'alimentos'), ('acucar', 'alimentos'),
    ('macarrao', 'alimentos'), ('refrigerante', 'bebidas'),
    ('papel_higienico', 'higiene-pessoal'), ('detergente', 'limpeza'),
    ('farinha', 'alimentos'), ('sal', 'alimentos'), ('biscoitos', 'alimentos'),
    ('conservas_enlatados', 'alimentos'), ('creme_de_leite', 'alimentos'),
    ('leite_condensado', 'alimentos'), ('azeite_vinagre', 'alimentos'),
    ('creme_dental', 'higiene-pessoal'), ('fraldas', 'bebes'), ('iogurtes', 'alimentos'),
    ('alimentos_basicos', 'alimentos'), ('matinais', 'alimentos'), ('padaria', 'padaria'),
    ('hortifruti', 'alimentos'), ('acougue', 'alimentos'), ('emporium', 'alimentos'),
    ('bebidas', 'bebidas'), ('higiene_beleza', 'higiene-pessoal'), ('pet_shop', 'pet'),
    ('pet', 'pet'), ('biscoitos_chocolates', 'alimentos'), ('carnes', 'alimentos'),
    ('cereais_farinaceos', 'alimentos'), ('congelados', 'congelados'),
    ('frios_laticinios', 'alimentos'), ('matinais_sobremesas', 'alimentos'),
    ('mercearia', 'alimentos'), ('perfumaria_higiene', 'higiene-pessoal')
),
resolved as (
  select distinct on (sp.canonical_product_id)
    sp.canonical_product_id,
    c.id as category_id
  from public.store_product_collection_scopes s
  join public.store_products sp on sp.id = s.store_product_id
  join mapping m on m.scope_key = s.scope_key
  join public.categories c on c.slug = m.slug
  where sp.canonical_product_id is not null
  order by sp.canonical_product_id, s.last_seen_at desc
)
update public.canonical_products cp
set category_id = resolved.category_id
from resolved
where cp.id = resolved.canonical_product_id
  and cp.category_id is null;
