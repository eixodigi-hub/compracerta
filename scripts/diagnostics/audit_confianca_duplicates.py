#!/usr/bin/env python3

import json
from collections import Counter, defaultdict
from datetime import datetime
from itertools import combinations
from pathlib import Path


CATEGORIES = {
    "alimentos_basicos",
    "matinais",
    "padaria",
    "hortifruti",
    "acougue",
    "emporium",
    "bebidas",
    "higiene_beleza",
    "marcas_exclusivas",
    "pet_shop",
}

COMPARE_FIELDS = [
    "name",
    "barcode",
    "price",
    "regular_price",
    "sale_price",
    "promotional",
    "available",
    "stock_quantity",
    "active_esmeralda",
    "unit_of_measurement",
    "weight",
    "image_url",
]


def normalize_value(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
    )


files_by_category = defaultdict(list)

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

    # Ignora previews de --limite 10.
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

for category in CATEGORIES:
    candidates = files_by_category.get(
        category,
        [],
    )

    if not candidates:
        raise SystemExit(
            f"ERRO: arquivo completo ausente: "
            f"{category}"
        )

    candidates.sort(
        key=lambda item: item[0]
    )

    selected[category] = candidates[-1]


by_external_id = defaultdict(list)

for category, (_, path, data) in selected.items():
    for product in data["products"]:
        external_id = str(
            product.get(
                "external_id",
                "",
            )
        ).strip()

        if not external_id:
            continue

        by_external_id[external_id].append(
            {
                "category": category,
                "file": path.name,
                "product": product,
            }
        )


duplicate_groups = {
    external_id: records
    for external_id, records
    in by_external_id.items()
    if len(records) > 1
}

extra_occurrences = sum(
    len(records) - 1
    for records in duplicate_groups.values()
)

distribution = Counter(
    len(records)
    for records in duplicate_groups.values()
)

pair_overlaps = Counter()

for records in duplicate_groups.values():
    categories = sorted(
        {
            record["category"]
            for record in records
        }
    )

    for category_a, category_b in combinations(
        categories,
        2,
    ):
        pair_overlaps[
            (
                category_a,
                category_b,
            )
        ] += 1


conflicts = []

for external_id, records in sorted(
    duplicate_groups.items()
):
    field_conflicts = {}

    for field in COMPARE_FIELDS:
        values = defaultdict(list)

        for record in records:
            value = record["product"].get(
                field
            )

            values[
                normalize_value(value)
            ].append(
                record["category"]
            )

        if len(values) > 1:
            field_conflicts[field] = {
                value: categories
                for value, categories
                in values.items()
            }

    if field_conflicts:
        conflicts.append(
            {
                "external_id": external_id,
                "categories": sorted(
                    {
                        record["category"]
                        for record in records
                    }
                ),
                "name": records[0][
                    "product"
                ].get("name"),
                "conflicts": field_conflicts,
                "records": [
                    {
                        "category": record[
                            "category"
                        ],
                        "product": record[
                            "product"
                        ],
                    }
                    for record in records
                ],
            }
        )


timestamp = datetime.now().strftime(
    "%Y%m%d_%H%M%S"
)

output_file = Path(
    "logs"
) / (
    "confianca_duplicate_audit_"
    f"{timestamp}.json"
)

report = {
    "raw_products": sum(
        len(data["products"])
        for _, _, data in selected.values()
    ),
    "unique_external_ids": len(
        by_external_id
    ),
    "duplicate_external_ids": len(
        duplicate_groups
    ),
    "extra_occurrences": extra_occurrences,
    "duplicate_distribution": dict(
        sorted(distribution.items())
    ),
    "conflicting_external_ids": len(
        conflicts
    ),
    "pair_overlaps": [
        {
            "category_a": pair[0],
            "category_b": pair[1],
            "products": count,
        }
        for pair, count in pair_overlaps.most_common()
    ],
    "conflicts": conflicts,
}

output_file.write_text(
    json.dumps(
        report,
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)


print("=" * 72)
print("AUDITORIA DE DUPLICIDADES — CONFIANÇA")
print("=" * 72)

print(
    f"Registros brutos: "
    f"{report['raw_products']}"
)

print(
    f"External IDs únicos: "
    f"{report['unique_external_ids']}"
)

print(
    f"IDs presentes em mais de uma categoria: "
    f"{report['duplicate_external_ids']}"
)

print(
    f"Ocorrências excedentes: "
    f"{report['extra_occurrences']}"
)

print()
print("Distribuição das duplicidades:")

for occurrences, count in sorted(
    distribution.items()
):
    print(
        f"  Em {occurrences} categorias: "
        f"{count} produtos"
    )

print()
print(
    "External IDs com algum campo "
    "conflitante: "
    f"{len(conflicts)}"
)

print()
print("=" * 72)
print("MAIORES SOBREPOSIÇÕES ENTRE CATEGORIAS")
print("=" * 72)

for (
    category_a,
    category_b,
), count in pair_overlaps.most_common(
    20
):
    print(
        f"{category_a:20} x "
        f"{category_b:20} = "
        f"{count}"
    )

print()
print("=" * 72)
print("CONFLITOS POR CAMPO")
print("=" * 72)

field_counter = Counter()

for conflict in conflicts:
    for field in conflict["conflicts"]:
        field_counter[field] += 1

if not field_counter:
    print(
        "Nenhum conflito encontrado."
    )
else:
    for field, count in (
        field_counter.most_common()
    ):
        print(
            f"{field:25} = "
            f"{count}"
        )

print()
print(f"Relatório: {output_file.resolve()}")
print()
print(
    "Nenhuma alteração foi feita "
    "no Supabase."
)
