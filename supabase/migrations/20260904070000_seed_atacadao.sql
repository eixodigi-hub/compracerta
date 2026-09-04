-- Novo mercado: Atacadão, loja de Marília (Shopping Marília / Jardim
-- Rivera).
INSERT INTO public.stores (id, city_id, name, slug, website_url, address, active)
SELECT 'a85817f2-a4c8-4967-9644-d5ba5fa62d49', c.id, 'Atacadão', 'atacadao',
       'https://www.atacadao.com.br/loja/marilia',
       'Rua Luiz Gabaldi Filho, 50, Jardim Rivera, Marília - SP', true
FROM public.cities c WHERE c.slug = 'marilia-sp'
ON CONFLICT (id) DO NOTHING;
