-- Mesmo ajuste feito nos coletores Python: usa a ÚLTIMA ocorrência de
-- número+unidade no nome, não a primeira. Nomes às vezes trazem um
-- número cedo que não é o tamanho da embalagem (ex.: "Bebida Láctea
-- Yopro 15g de Proteína ... 250ml" — "15g" é a chamada nutricional,
-- "250ml" no fim é o tamanho de verdade). Isso já causou um vínculo
-- perdido entre lojas por essa extração pegar o número errado.
CREATE OR REPLACE FUNCTION public.extract_qty_from_name(name text)
RETURNS public.qty_normalized
LANGUAGE sql
IMMUTABLE PARALLEL SAFE
SET search_path = public, extensions
AS $$
  WITH matches AS (
    SELECT g[1] AS num, g[2] AS unit
    FROM regexp_matches(
      coalesce(name, ''),
      '(\d+(?:[.,]\d+)?)\s*(kgs?|gramas?|grs?|g|mg|mls?|litros?|lts?|l)\y',
      'gi'
    ) AS g
  ),
  last_match AS (
    SELECT num, unit FROM matches
    OFFSET GREATEST((SELECT count(*) FROM matches) - 1, 0)
    LIMIT 1
  )
  SELECT public.normalize_qty(
    NULLIF(replace(num, ',', '.'), '')::numeric,
    lower(unit)
  )
  FROM last_match;
$$;
