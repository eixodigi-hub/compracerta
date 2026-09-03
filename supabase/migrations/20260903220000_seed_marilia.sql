-- =============================================================
-- Dados iniciais: cidade Marília (a base já semeia isso, então só
-- garante que existe) + os 3 mercados coletados hoje. Busca o
-- city_id pelo slug em vez de fixar o id da cidade, porque a linha
-- de Marília já pode ter sido criada com outro id pela migração
-- base (20260715223035_...).
-- =============================================================
INSERT INTO public.cities (name, state, slug, active)
VALUES ('Marília', 'SP', 'marilia-sp', true)
ON CONFLICT (slug) DO NOTHING;

INSERT INTO public.stores (id, city_id, name, slug, website_url, address, active)
SELECT '2e30f123-1567-43c7-bdfd-ebff48d89025', c.id, 'Tauste', 'tauste',
       'https://tauste.com.br/marilia/', NULL, true
FROM public.cities c WHERE c.slug = 'marilia-sp'
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.stores (id, city_id, name, slug, website_url, address, active)
SELECT '744b59fb-1bf9-4235-a900-fcea7fd1cfec', c.id, 'Confiança', 'confianca',
       'https://www.confianca.com.br/marilia', NULL, true
FROM public.cities c WHERE c.slug = 'marilia-sp'
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.stores (id, city_id, name, slug, website_url, address, active)
SELECT '3e38cf91-5f27-4530-bef7-aa7409d2eed9', c.id, 'Spani Marília', 'spani-marilia',
       'https://www.spanionline.com.br',
       'Av. João Ramalho, 2400, Nova Marília, Marília - SP', true
FROM public.cities c WHERE c.slug = 'marilia-sp'
ON CONFLICT (id) DO NOTHING;
