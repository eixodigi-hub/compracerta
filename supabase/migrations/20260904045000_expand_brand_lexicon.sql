-- Mais marcas encontradas testando com dados reais que ainda
-- passavam como falso positivo por não estarem na lista (ex.: "Frango
-- Sadia" vs "Frango Adoro" — Adoro não estava listada).
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
    ('danone'), ('danoninho'), ('vigor'), ('nestle'), ('betania'), ('batavo'), ('elege'), ('verde campo'), ('da fazenda'), ('serramar'), ('xando'),
    ('lux'), ('protex'), ('palmolive'), ('phebo'), ('granado'),
    ('trakinas'), ('negresco'), ('marilan'), ('bauducco'), ('passatempo'), ('club social'), ('richester'), ('adria'),
    ('garoto'), ('lacta'), ('kraft'), ('kitkat'), ('kit kat'),
    ('liza'), ('soya'), ('mazola'), ('cocamar'), ('vitaliv'),
    ('uniao'), ('santa isabel'), ('caravelas'), ('da barra'), ('alto alegre'),
    ('lebre'), ('cisne'), ('cisne parrilla'),
    ('pampers'), ('babysec'), ('pom pom'), ('huggies'), ('turma da monica'), ('personal baby'),
    ('yodel'), ('yakult'), ('activia'),
    ('kelloggs'), ('nesfit'), ('mais vita'), ('quaker'),
    ('elseve'), ('tresemme'), ('seda'), ('pantene'), ('novex'), ('haskell'),
    ('listerine'), ('cepacol'), ('plax'),
    ('quero'), ('predilecta'), ('gomes da costa'), ('coqueiro'), ('fugini'), ('cica'), ('heinz'), ('etti'),
    ('seara'), ('sadia'), ('perdigao'), ('friboi'), ('swift'), ('aurora'), ('adoro'),
    ('del valle'), ('maguary'), ('sufresh'), ('cutrale'),
    ('tio joao'), ('camil'), ('kicaldo'), ('prato fino'), ('urbano'), ('namorado'),
    ('nivea men'), ('gillette'), ('bic'),
    ('wickbold'), ('pullman'), ('plusvita'), ('panco'), ('sete graos'), ('nutrella'),
    ('favorita'), ('guloso'), ('girassol'), ('veneza'), ('bonjour'), ('la pastina'), ('patako')
  ) AS b(brand)
  WHERE public.immutable_unaccent(coalesce(name, '')) ILIKE '%' || b.brand || '%'
  ORDER BY length(b.brand) DESC
  LIMIT 1;
$$;
