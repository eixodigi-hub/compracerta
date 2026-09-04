#!/usr/bin/env python3

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


CONFIANCA_STORE_ID = "744b59fb-1bf9-4235-a900-fcea7fd1cfec"
TAUSTE_STORE_ID = "9cc4a9b1-5bc1-48e8-b3ff-c89fa7009b02"

EXCLUDED_PAIRS = {
    (
        "Sal Rosa do Himalaia Fino Br Spices 1kg",
        "Sal Rosa do Himalaia Br Spices Pacote 1000g",
    ),
}


def sql_literal(value: Any) -> str:
    if value is None or value == "":
        return "NULL"

    escaped = str(value).replace("'", "''")
    return f"'{escaped}'"


def normalize_barcode(value: Any) -> Optional[str]:
    code = re.sub(r"\D", "", str(value or ""))

    if 8 <= len(code) <= 14:
        return code

    return None


def get_quantity(
    proposal: Dict[str, Any],
) -> Tuple[Optional[float], Optional[str]]:
    details = proposal.get("details") or {}

    quantity = (
        details.get("quantity_confianca")
        or details.get("quantity_tauste")
    )

    if not quantity or len(quantity) != 2:
        return None, None

    return float(quantity[0]), str(quantity[1])


def load_latest_simulation() -> Tuple[Path, List[Dict[str, Any]]]:
    files = sorted(
        Path("logs").glob("product_match_simulation_*.json"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )

    if not files:
        raise SystemExit("Nenhuma simulação foi encontrada em logs/.")

    file = files[0]
    data = json.loads(file.read_text(encoding="utf-8"))

    return file, data


def approved_matches(
    data: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    approved = []

    for proposal in data:
        if proposal.get("status") != "alta_confianca":
            continue

        confianca = proposal.get("confianca") or {}
        tauste = proposal.get("tauste") or {}

        pair = (
            confianca.get("external_name"),
            tauste.get("external_name"),
        )

        if pair in EXCLUDED_PAIRS:
            continue

        if not confianca.get("id") or not tauste.get("id"):
            raise SystemExit(
                f"Associação sem IDs válidos: {pair}"
            )

        approved.append(proposal)

    if len(approved) != 36:
        raise SystemExit(
            f"ERRO: eram esperadas 36 associações, "
            f"mas foram encontradas {len(approved)}."
        )

    confianca_ids = [
        item["confianca"]["id"]
        for item in approved
    ]

    tauste_ids = [
        item["tauste"]["id"]
        for item in approved
    ]

    if len(set(confianca_ids)) != len(confianca_ids):
        raise SystemExit(
            "ERRO: um produto do Confiança aparece em mais de um par."
        )

    if len(set(tauste_ids)) != len(tauste_ids):
        raise SystemExit(
            "ERRO: um produto do Tauste aparece em mais de um par."
        )

    return approved


def values_rows(
    approved: List[Dict[str, Any]],
) -> str:
    rows = []

    for index, proposal in enumerate(approved, start=1):
        confianca = proposal["confianca"]
        tauste = proposal["tauste"]

        barcode = normalize_barcode(
            confianca.get("barcode_raw")
        )

        rows.append(
            "    ("
            f"{index}, "
            f"{sql_literal(confianca['id'])}::uuid, "
            f"{sql_literal(tauste['id'])}::uuid, "
            f"{sql_literal(confianca.get('external_name'))}, "
            f"{sql_literal(tauste.get('external_name'))}, "
            f"{sql_literal(barcode)}"
            ")"
        )

    return ",\n".join(rows)


def generate_preflight(
    approved: List[Dict[str, Any]],
) -> str:
    rows = values_rows(approved)

    return f"""-- Pré-validação das 36 associações aprovadas
-- Este arquivo não modifica o banco.

WITH approved (
    pair_number,
    confianca_id,
    tauste_id,
    confianca_name,
    tauste_name,
    barcode
) AS (
  VALUES
{rows}
),
checked AS (
  SELECT
    a.*,
    spc.id AS confianca_found,
    spt.id AS tauste_found,
    spc.canonical_product_id AS confianca_canonical,
    spt.canonical_product_id AS tauste_canonical,
    (
      SELECT COUNT(*)
      FROM public.canonical_products cp
      WHERE a.barcode IS NOT NULL
        AND regexp_replace(
          COALESCE(cp.barcode, ''),
          '[^0-9]',
          '',
          'g'
        ) = a.barcode
    ) AS canonical_barcode_count
  FROM approved a
  LEFT JOIN public.store_products spc
    ON spc.id = a.confianca_id
   AND spc.store_id =
       '{CONFIANCA_STORE_ID}'::uuid
  LEFT JOIN public.store_products spt
    ON spt.id = a.tauste_id
   AND spt.store_id =
       '{TAUSTE_STORE_ID}'::uuid
)
SELECT
  COUNT(*) AS pares_esperados,

  COUNT(*) FILTER (
    WHERE confianca_found IS NOT NULL
      AND tauste_found IS NOT NULL
  ) AS pares_encontrados,

  COUNT(*) FILTER (
    WHERE confianca_canonical IS NULL
      AND tauste_canonical IS NULL
  ) AS pares_sem_associacao,

  COUNT(*) FILTER (
    WHERE confianca_canonical IS NOT NULL
       OR tauste_canonical IS NOT NULL
  ) AS pares_com_associacao_previa,

  COUNT(*) FILTER (
    WHERE canonical_barcode_count = 1
  ) AS canonical_existente_por_barcode,

  COUNT(*) FILTER (
    WHERE canonical_barcode_count > 1
  ) AS barcode_canonical_duplicado,

  COALESCE(
    jsonb_agg(
      jsonb_build_object(
        'par', pair_number,
        'confianca', confianca_name,
        'tauste', tauste_name,
        'confianca_encontrado',
          confianca_found IS NOT NULL,
        'tauste_encontrado',
          tauste_found IS NOT NULL,
        'confianca_canonical',
          confianca_canonical,
        'tauste_canonical',
          tauste_canonical,
        'canonical_barcode_count',
          canonical_barcode_count
      )
      ORDER BY pair_number
    ) FILTER (
      WHERE confianca_found IS NULL
         OR tauste_found IS NULL
         OR confianca_canonical IS NOT NULL
         OR tauste_canonical IS NOT NULL
         OR canonical_barcode_count > 1
    ),
    '[]'::jsonb
  ) AS problemas
FROM checked;
"""


def generate_apply(
    approved: List[Dict[str, Any]],
) -> str:
    blocks = []

    for index, proposal in enumerate(approved, start=1):
        confianca = proposal["confianca"]
        tauste = proposal["tauste"]

        quantity, unit = get_quantity(proposal)

        canonical_name = confianca.get("external_name")
        brand = (
            tauste.get("brand_raw")
            or confianca.get("brand_raw")
        )

        barcode = normalize_barcode(
            confianca.get("barcode_raw")
        )

        image_url = (
            confianca.get("image_url")
            or tauste.get("image_url")
        )

        quantity_sql = (
            str(quantity)
            if quantity is not None
            else "NULL"
        )

        barcode_lookup = ""

        if barcode:
            barcode_lookup = f"""
  SELECT COUNT(*)
    INTO v_existing_count
  FROM public.canonical_products cp
  WHERE regexp_replace(
          COALESCE(cp.barcode, ''),
          '[^0-9]',
          '',
          'g'
        ) = {sql_literal(barcode)};

  IF v_existing_count > 1 THEN
    RAISE EXCEPTION
      'Par {index}: mais de um canonical_product possui o barcode {barcode}.';
  END IF;

  IF v_existing_count = 1 THEN
    SELECT cp.id
      INTO v_canonical_id
    FROM public.canonical_products cp
    WHERE regexp_replace(
            COALESCE(cp.barcode, ''),
            '[^0-9]',
            '',
            'g'
          ) = {sql_literal(barcode)}
    LIMIT 1;
  END IF;
"""

        blocks.append(
            f"""
DO $match_{index:03d}$
DECLARE
  v_canonical_id uuid;
  v_existing_count integer := 0;
  v_product_count integer := 0;
  v_conflict_count integer := 0;
BEGIN
  SELECT COUNT(*)
    INTO v_product_count
  FROM public.store_products sp
  WHERE
    (
      sp.id = {sql_literal(confianca['id'])}::uuid
      AND sp.store_id =
          '{CONFIANCA_STORE_ID}'::uuid
    )
    OR
    (
      sp.id = {sql_literal(tauste['id'])}::uuid
      AND sp.store_id =
          '{TAUSTE_STORE_ID}'::uuid
    );

  IF v_product_count <> 2 THEN
    RAISE EXCEPTION
      'Par {index}: eram esperados 2 store_products, encontrados %.',
      v_product_count;
  END IF;

  SELECT COUNT(*)
    INTO v_conflict_count
  FROM public.store_products sp
  WHERE sp.id IN (
      {sql_literal(confianca['id'])}::uuid,
      {sql_literal(tauste['id'])}::uuid
    )
    AND sp.canonical_product_id IS NOT NULL;

  IF v_conflict_count > 0 THEN
    RAISE EXCEPTION
      'Par {index}: existe associação canônica anterior.';
  END IF;

{barcode_lookup}

  IF v_canonical_id IS NULL THEN
    INSERT INTO public.canonical_products (
      name,
      brand,
      quantity,
      unit,
      barcode,
      image_url,
      active
    )
    VALUES (
      {sql_literal(canonical_name)},
      {sql_literal(brand)},
      {quantity_sql},
      {sql_literal(unit)},
      {sql_literal(barcode)},
      {sql_literal(image_url)},
      true
    )
    RETURNING id INTO v_canonical_id;
  END IF;

  UPDATE public.store_products
  SET
    canonical_product_id = v_canonical_id,
    updated_at = NOW()
  WHERE id IN (
    {sql_literal(confianca['id'])}::uuid,
    {sql_literal(tauste['id'])}::uuid
  );

  RAISE NOTICE
    'Par {index}/36 associado ao canonical_product %.',
    v_canonical_id;
END
$match_{index:03d}$;
"""
        )

    rows = values_rows(approved)

    verification = f"""
COMMIT;

WITH approved (
    pair_number,
    confianca_id,
    tauste_id,
    confianca_name,
    tauste_name,
    barcode
) AS (
  VALUES
{rows}
)
SELECT
  COUNT(*) AS pares,

  COUNT(*) FILTER (
    WHERE spc.canonical_product_id IS NOT NULL
      AND spc.canonical_product_id =
          spt.canonical_product_id
  ) AS pares_associados_corretamente,

  COUNT(DISTINCT spc.canonical_product_id) FILTER (
    WHERE spc.canonical_product_id =
          spt.canonical_product_id
  ) AS canonical_products_utilizados,

  COUNT(*) FILTER (
    WHERE spc.canonical_product_id IS NULL
       OR spt.canonical_product_id IS NULL
       OR spc.canonical_product_id <>
          spt.canonical_product_id
  ) AS pares_com_problema

FROM approved a
LEFT JOIN public.store_products spc
  ON spc.id = a.confianca_id
LEFT JOIN public.store_products spt
  ON spt.id = a.tauste_id;
"""

    return (
        "-- Associação atômica dos 36 pares aprovados\n"
        "-- Qualquer erro cancela toda a transação.\n\n"
        "BEGIN;\n"
        "SET LOCAL lock_timeout = '10s';\n"
        "SET LOCAL statement_timeout = '180s';\n"
        + "\n".join(blocks)
        + verification
    )


def main() -> int:
    simulation_file, data = load_latest_simulation()
    approved = approved_matches(data)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    preflight_file = Path(
        f"logs/canonical_matches_preflight_{timestamp}.sql"
    )

    apply_file = Path(
        f"logs/canonical_matches_apply_{timestamp}.sql"
    )

    preflight_file.write_text(
        generate_preflight(approved),
        encoding="utf-8",
    )

    apply_file.write_text(
        generate_apply(approved),
        encoding="utf-8",
    )

    print("=" * 72)
    print("SCRIPTS DE ASSOCIAÇÃO GERADOS")
    print("=" * 72)
    print(f"Simulação usada: {simulation_file}")
    print(f"Pares aprovados: {len(approved)}")
    print("Pares excluídos: 1")
    print(f"Pré-validação: {preflight_file.resolve()}")
    print(f"Aplicação real: {apply_file.resolve()}")
    print()
    print("Nenhuma alteração foi feita no banco.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
