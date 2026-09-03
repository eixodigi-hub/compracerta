#!/usr/bin/env python3

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path


CATEGORY_PRIORITY = [
    "alimentos_basicos",
    "matinais",
    "padaria",
    "hortifruti",
    "acougue",
    "emporium",
    "bebidas",
    "higiene_beleza",
    "pet_shop",
    "marcas_exclusivas",
]

CATEGORIES = set(CATEGORY_PRIORITY)

files_by_category = defaultdict(list)


# ------------------------------------------------------------
# Localiza o arquivo completo mais recente de cada categoria.
# ------------------------------------------------------------

for path in Path("logs").glob(
    "confianca_preview_*.json"
):
    try:
        data = json.loads(
            path.read_text(encoding="utf-8")
        )
    except Exception:
        continue

    category = data.get("category")
    products = data.get("products", [])

    if category not in CATEGORIES:
        continue

    if not isinstance(products, list):
        continue

    # Ignora os previews antigos feitos com --limite 10.
    if len(products) <= 10:
        continue

    files_by_category[category].append(
        (
            data.get("generated_at", ""),
            path,
            data,
        )
    )


selected = {}

for category in CATEGORY_PRIORITY:
    candidates = files_by_category.get(
        category,
        [],
    )

    if not candidates:
        raise SystemExit(
            "ERRO: arquivo completo não encontrado "
            f"para {category}"
        )

    candidates.sort(
        key=lambda item: item[0]
    )

    generated_at, path, data = candidates[-1]

    selected[category] = {
        "generated_at": generated_at,
        "path": path,
        "data": data,
    }


# ------------------------------------------------------------
# Agrupa todos os produtos pelo external_id.
# ------------------------------------------------------------

by_external_id = defaultdict(list)

raw_total = 0

for category in CATEGORY_PRIORITY:
    data = selected[category]["data"]

    for product in data.get(
        "products",
        [],
    ):
        raw_total += 1

        if not isinstance(product, dict):
            continue

        external_id = str(
            product.get(
                "external_id",
                "",
            )
        ).strip()

        if not external_id:
            raise SystemExit(
                "ERRO: produto sem external_id "
                f"em {category}"
            )

        by_external_id[external_id].append(
            {
                "category": category,
                "product": product,
            }
        )


# ------------------------------------------------------------
# Consolida um único registro por external_id.
# ------------------------------------------------------------

consolidated_products = []
multi_category_products = []

priority_index = {
    category: index
    for index, category
    in enumerate(CATEGORY_PRIORITY)
}

for external_id in sorted(
    by_external_id,
    key=lambda value: (
        int(value)
        if value.isdigit()
        else value
    ),
):
    records = by_external_id[
        external_id
    ]

    records.sort(
        key=lambda record: priority_index[
            record["category"]
        ]
    )

    source_categories = sorted(
        {
            record["category"]
            for record in records
        },
        key=lambda category: priority_index[
            category
        ],
    )

    # Como a auditoria confirmou zero conflitos,
    # podemos usar os dados do primeiro registro.
    product = dict(
        records[0]["product"]
    )

    product["source_category"] = (
        source_categories[0]
    )

    product["source_categories"] = (
        source_categories
    )

    consolidated_products.append(
        product
    )

    if len(source_categories) > 1:
        multi_category_products.append(
            {
                "external_id": external_id,
                "name": product.get(
                    "name"
                ),
                "source_category": product[
                    "source_category"
                ],
                "source_categories": (
                    source_categories
                ),
            }
        )


# ------------------------------------------------------------
# Estatísticas.
# ------------------------------------------------------------

available_products = sum(
    1
    for product in consolidated_products
    if product.get("available") is True
)

promotional_products = sum(
    1
    for product in consolidated_products
    if product.get("promotional") is True
)

timestamp = datetime.now().strftime(
    "%Y%m%d_%H%M%S"
)

output_file = Path("logs") / (
    "confianca_consolidated_"
    f"{timestamp}.json"
)

overlap_file = Path("logs") / (
    "confianca_category_overlaps_"
    f"{timestamp}.json"
)


output = {
    "generated_at": datetime.now().isoformat(),
    "dry_run": True,
    "store_id": (
        "4f97f5d6-6a17-46ab-bf63-b3724abef9ff"
    ),
    "source": "confianca_marilia",
    "categories": CATEGORY_PRIORITY,
    "raw_normalized_products": raw_total,
    "unique_products": len(
        consolidated_products
    ),
    "duplicates_removed": (
        raw_total
        - len(consolidated_products)
    ),
    "available_products": (
        available_products
    ),
    "promotional_products": (
        promotional_products
    ),
    "selected_files": {
        category: {
            "file": selected[
                category
            ]["path"].name,
            "generated_at": selected[
                category
            ]["generated_at"],
            "products": len(
                selected[
                    category
                ]["data"].get(
                    "products",
                    [],
                )
            ),
        }
        for category in CATEGORY_PRIORITY
    },
    "products": consolidated_products,
}


output_file.write_text(
    json.dumps(
        output,
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)

overlap_file.write_text(
    json.dumps(
        {
            "total_multi_category_products": (
                len(
                    multi_category_products
                )
            ),
            "products": (
                multi_category_products
            ),
        },
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)


# ------------------------------------------------------------
# Validações finais.
# ------------------------------------------------------------

external_ids = [
    str(
        product.get(
            "external_id",
            "",
        )
    )
    for product in consolidated_products
]

if len(external_ids) != len(
    set(external_ids)
):
    raise SystemExit(
        "ERRO: ainda existem external_ids "
        "duplicados no catálogo consolidado."
    )

if len(consolidated_products) != 9306:
    print(
        "AVISO: total diferente dos "
        "9306 esperados pela auditoria."
    )


print("=" * 72)
print("CATÁLOGO CONSOLIDADO — CONFIANÇA MARÍLIA")
print("=" * 72)

print(
    f"Registros normalizados brutos: "
    f"{raw_total}"
)

print(
    f"Produtos únicos: "
    f"{len(consolidated_products)}"
)

print(
    f"Duplicidades removidas: "
    f"{raw_total - len(consolidated_products)}"
)

print(
    f"Produtos em múltiplas categorias: "
    f"{len(multi_category_products)}"
)

print(
    f"Disponíveis: "
    f"{available_products}"
)

print(
    f"Em promoção: "
    f"{promotional_products}"
)

print()
print(
    f"Catálogo: "
    f"{output_file.resolve()}"
)

print(
    f"Sobreposições: "
    f"{overlap_file.resolve()}"
)

print()
print(
    "Nenhuma alteração foi feita "
    "no Supabase."
)
