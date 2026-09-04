-- Novo mercado: Supermercados Kawakami, loja de Marília (Av. João
-- Ramalho, 2270 — mesma rua do Spani, mais adiante).
INSERT INTO public.stores (id, city_id, name, slug, website_url, address, active)
SELECT '7814fa07-1f68-4fdb-a688-678fd32dd686', c.id, 'Kawakami', 'kawakami',
       'https://www.kawakami.com.br',
       'Av. João Ramalho, 2270, Núcleo Habitacional Nova Marília, Marília - SP', true
FROM public.cities c WHERE c.slug = 'marilia-sp'
ON CONFLICT (id) DO NOTHING;
