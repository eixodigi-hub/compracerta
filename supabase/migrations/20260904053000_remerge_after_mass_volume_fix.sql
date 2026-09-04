-- Repete o mesmo reparo de casamento (mais antigo pro mais novo, une
-- num candidato mais antigo compatível) agora que peso/volume contam
-- como a mesma dimensão de tamanho — recupera pares como "Bebida
-- Proteica Yopro 250ml" que ficaram separados só porque o Confiança
-- rotulou como peso (0.25 KG) e o Spani como volume (250 ml), mesmo
-- valor. Idempotente: grupos já unidos não encontram mais nada pra
-- unir, só as novas oportunidades liberadas por essa mudança agem.
SET statement_timeout = '45min';

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
    v_kind := (public.resolve_qty(r.quantity, r.unit, r.name)).norm_kind;
    v_brand := public.effective_brand(r.brand, r.name);

    FOR cand IN
      SELECT cp2.id,
             (public.resolve_qty(cp2.quantity, cp2.unit, cp2.name)).norm_kind AS cand_kind,
             public.effective_brand(cp2.brand, cp2.name) AS cand_brand,
             similarity(
               public.immutable_unaccent(public.match_name_key(cp2.name || ' ' || COALESCE(cp2.brand, ''))),
               public.immutable_unaccent(public.match_name_key(r.name || ' ' || COALESCE(r.brand, '')))
             ) AS score
      FROM public.canonical_products cp2
      WHERE cp2.active = true
        AND cp2.id <> r.id
        AND cp2.created_at < r.created_at
        AND public.qty_compatible(r.quantity, r.unit, r.name, cp2.quantity, cp2.unit, cp2.name)
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

    IF v_processed % 2000 = 0 THEN
      RAISE NOTICE 'recasamento: % processados, % unidos', v_processed, v_merged;
    END IF;
  END LOOP;

  RAISE NOTICE 'recasamento concluído: % processados, % unidos', v_processed, v_merged;
END $$;
