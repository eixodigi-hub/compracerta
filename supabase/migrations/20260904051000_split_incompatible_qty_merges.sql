-- Reparo do falso positivo relatado: "Arroz Solito Tipo 1 Pacote
-- 2000g" (Tauste) tinha sido unido a "Arroz Tipo 1 Solito 5kg"
-- (Spani) — tamanhos bem diferentes. A causa foi corrigida na
-- migração anterior (extração de quantidade do texto do nome como
-- plano B). Esta migração desfaz os vínculos já feitos que a lógica
-- nova reconhece como incompatíveis, e roda o casador de novo nelas
-- — cada uma vira seu próprio canônico ou casa com um candidato de
-- verdade compatível.
SET statement_timeout = '10min';

DO $$
DECLARE
  r record;
  v_unlinked integer := 0;
BEGIN
  FOR r IN
    SELECT DISTINCT sp1.id
    FROM public.store_products sp1
    JOIN public.store_products sp2
      ON sp2.canonical_product_id = sp1.canonical_product_id
     AND sp2.id <> sp1.id
    WHERE sp1.canonical_product_id IS NOT NULL
      AND sp1.active
      AND sp2.active
      AND NOT public.qty_compatible(
            NULLIF(regexp_replace(coalesce(sp1.quantity_raw, ''), '[^0-9,\.]', '', 'g'), '')::numeric,
            NULLIF(lower(trim(coalesce(sp1.unit_raw, ''))), ''), sp1.external_name,
            NULLIF(regexp_replace(coalesce(sp2.quantity_raw, ''), '[^0-9,\.]', '', 'g'), '')::numeric,
            NULLIF(lower(trim(coalesce(sp2.unit_raw, ''))), ''), sp2.external_name
          )
  LOOP
    UPDATE public.store_products
       SET canonical_product_id = NULL, updated_at = now()
     WHERE id = r.id;
    v_unlinked := v_unlinked + 1;
  END LOOP;

  RAISE NOTICE 'desfeitos % vínculos com quantidade incompatível', v_unlinked;
END $$;

DO $$
DECLARE
  r record;
  v_processed integer := 0;
BEGIN
  FOR r IN
    SELECT id FROM public.store_products WHERE canonical_product_id IS NULL AND active = true
  LOOP
    PERFORM public.auto_link_or_create_canonical(r.id);
    v_processed := v_processed + 1;
    IF v_processed % 200 = 0 THEN
      RAISE NOTICE 'recasamento: % processados', v_processed;
    END IF;
  END LOOP;

  RAISE NOTICE 'recasamento concluído: % processados', v_processed;
END $$;
