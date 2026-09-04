-- Mais um padrão encontrado revisando os conflitos restantes: o
-- catálogo do Confiança com frequência marca a DIMENSÃO errada
-- (peso vs volume) só que o VALOR numérico bate certinho com as
-- outras lojas — ex.: "Bebida Proteica Yopro 250ml" vem como "0.25
-- KG" no Confiança (deveria ser volume, não peso) contra "250 ml" no
-- Spani; "Refresco Tang 18g" vem como "0.018 L" no Confiança contra
-- "18 g" no Spani. Não é diferença de tamanho de verdade — é rótulo
-- de unidade inconsistente na origem.
--
-- Passa a tratar peso e volume como a mesma "dimensão de tamanho"
-- pra fins de comparação (valores continuam sendo comparados
-- normalmente — só não bloqueia mais só por causa da unidade
-- discordar entre peso/volume). Contagem (unidades) continua
-- separada — "10 unidades" nunca deve virar compatível com "250ml".
CREATE OR REPLACE FUNCTION public.qty_compatible(
  qty_a numeric, unit_a text, name_a text,
  qty_b numeric, unit_b text, name_b text
)
RETURNS boolean
LANGUAGE sql
IMMUTABLE PARALLEL SAFE
AS $$
  WITH ra AS (SELECT public.resolve_qty(qty_a, unit_a, name_a) AS q),
       rb AS (SELECT public.resolve_qty(qty_b, unit_b, name_b) AS q)
  SELECT
    (ra.q).norm_kind IS NULL
    OR (rb.q).norm_kind IS NULL
    OR (
      -- peso e volume contam como a mesma dimensão pra comparação;
      -- contagem só bate com contagem.
      (
        ((ra.q).norm_kind = (rb.q).norm_kind)
        OR ((ra.q).norm_kind IN ('mass', 'volume') AND (rb.q).norm_kind IN ('mass', 'volume'))
      )
      AND abs((ra.q).norm_value - (rb.q).norm_value)
          <= greatest((ra.q).norm_value, (rb.q).norm_value, 1) * 0.03
    )
  FROM ra, rb;
$$;
