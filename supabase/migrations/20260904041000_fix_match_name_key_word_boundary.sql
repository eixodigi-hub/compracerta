-- Corrige match_name_key: no dialeto de regex do Postgres (ARE),
-- \b significa o caractere BACKSPACE, não "borda de palavra" como em
-- outras linguagens — por isso "300g"/"40g" nunca eram removidos do
-- nome antes de comparar. A borda de palavra correta é \y.
CREATE OR REPLACE FUNCTION public.match_name_key(raw text)
RETURNS text
LANGUAGE sql
IMMUTABLE PARALLEL SAFE
AS $$
  SELECT trim(regexp_replace(
    regexp_replace(
      coalesce(raw, ''),
      '\d+([.,]\d+)?\s*(kgs?|gramas?|grs?|g|mg|mls?|litros?|lts?|l|un|und|unid(ade)?s?|pacotes?|pcts?|caixas?|cxs?|c\s*/\s*\d+)\y',
      ' ', 'gi'
    ),
    '\s+', ' ', 'g'
  ));
$$;
