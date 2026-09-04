-- =============================================================
-- Reparo retroativo: une produtos canônicos que já existem separados
-- no banco (cada um só com fichas de um mercado) mas que, pelas
-- regras novas de casamento (quantidade normalizada + nome limpo +
-- marca detectada), são claramente o mesmo produto.
--
-- Processa do canônico mais antigo pro mais novo. Pra cada um, procura
-- um candidato MAIS ANTIGO (já processado, nunca um mais novo — evita
-- ciclos) que bateria pelas regras da função auto_link_or_create_canonical.
-- Se achar, redireciona todas as fichas de loja do mais novo pro mais
-- antigo e desativa o mais novo (soft delete via active=false — nunca
-- some do banco, só some das buscas/comparações).
-- =============================================================
SET statement_timeout = '25min';

DO $$
DECLARE
  r record;
  cand record;
  v_kind text;
  v_brand text;
  v_merged integer := 0;
  v_processed integer := 0;
BEGIN
  FOR r IN
    SELECT cp.id, cp.name, cp.brand, cp.quantity, cp.unit, cp.created_at
    FROM public.canonical_products cp
    WHERE cp.active = true
    ORDER BY cp.created_at ASC
  LOOP
    v_processed := v_processed + 1;
    v_kind := (public.normalize_qty(r.quantity, r.unit)).norm_kind;
    v_brand := public.effective_brand(r.brand, r.name);

    FOR cand IN
      SELECT cp2.id,
             (public.normalize_qty(cp2.quantity, cp2.unit)).norm_kind AS cand_kind,
             public.effective_brand(cp2.brand, cp2.name) AS cand_brand,
             similarity(
               public.immutable_unaccent(public.match_name_key(cp2.name || ' ' || COALESCE(cp2.brand, ''))),
               public.immutable_unaccent(public.match_name_key(r.name || ' ' || COALESCE(r.brand, '')))
             ) AS score
      FROM public.canonical_products cp2
      WHERE cp2.active = true
        AND cp2.id <> r.id
        AND cp2.created_at < r.created_at
        AND public.qty_compatible(r.quantity, r.unit, cp2.quantity, cp2.unit)
        AND public.immutable_unaccent(cp2.name) % public.immutable_unaccent(r.name)
        AND NOT EXISTS (
          SELECT 1 FROM public.store_products a
          JOIN public.store_products b ON a.store_id = b.store_id
          WHERE a.canonical_product_id = cp2.id AND b.canonical_product_id = r.id
        )
      ORDER BY score DESC
      LIMIT 5
    LOOP
      IF cand.score >= 0.82
         OR (cand.score >= 0.60 AND v_kind IS NOT NULL AND cand.cand_kind IS NOT NULL
             AND public.brand_compatible(v_brand, cand.cand_brand))
      THEN
        UPDATE public.store_products
           SET canonical_product_id = cand.id, updated_at = now()
         WHERE canonical_product_id = r.id;

        UPDATE public.canonical_products
           SET active = false, updated_at = now()
         WHERE id = r.id;

        v_merged := v_merged + 1;
        EXIT;
      END IF;
    END LOOP;

    IF v_processed % 1000 = 0 THEN
      RAISE NOTICE 'reparo de casamento: % processados, % unidos', v_processed, v_merged;
    END IF;
  END LOOP;

  RAISE NOTICE 'reparo de casamento concluído: % processados, % unidos', v_processed, v_merged;
END $$;
