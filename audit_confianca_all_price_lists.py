import json
from pathlib import Path
from collections import Counter

BASE_DIR = Path(
    "/Users/williamcamargo/Projects/compra-certa-mar-lia/"
    "logs/confianca_api_probe_20260718_091243"
)

FILES = sorted(BASE_DIR.glob("products_*.json"))


def money(value):
    if value is None:
        return "None"
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return repr(value)


def nested(obj, *keys):
    cur = obj
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def different(a, b):
    return a != b


if not FILES:
    raise SystemExit(
        f"Nenhum arquivo products_*.json encontrado em:\n{BASE_DIR}"
    )


results = []
file_stats = []
seen = set()

for file_path in FILES:

    try:
        with file_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        print(f"ERRO AO LER {file_path.name}: {exc}")
        continue

    items = data.get("items", [])

    if not isinstance(items, list):
        print(f"IGNORADO {file_path.name}: root.items não é lista")
        continue

    file_skus = 0

    for item_index, item in enumerate(items):

        if not isinstance(item, dict):
            continue

        product_name = (
            item.get("displayName")
            or item.get("name")
            or item.get("description")
            or "SEM NOME"
        )

        product_id = (
            item.get("repositoryId")
            or item.get("id")
        )

        child_skus = item.get("childSKUs") or []

        if not isinstance(child_skus, list):
            continue

        for sku_index, sku in enumerate(child_skus):

            if not isinstance(sku, dict):
                continue

            file_skus += 1

            name = (
                sku.get("displayName")
                or sku.get("name")
                or product_name
            )

            repository_id = sku.get("repositoryId")
            sku_id = sku.get("id")
            barcode = sku.get("barcode")

            default_list = nested(
                sku,
                "listPrices",
                "DefaultPriceListEsmeralda"
            )

            club_list = nested(
                sku,
                "listPrices",
                "ClubPriceListEsmeralda"
            )

            default_sale = nested(
                sku,
                "salePrices",
                "DefaultPriceListEsmeralda"
            )

            club_sale = nested(
                sku,
                "salePrices",
                "ClubPriceListEsmeralda"
            )

            direct_list = sku.get("listPrice")
            direct_sale = sku.get("salePrice")

            active = sku.get(
                "x_activeConfiancaEsmeralda"
            )

            if active is None:
                active = nested(
                    sku,
                    "dynamicPropertyMapLong",
                    "sku_x_activeConfiancaEsmeralda"
                )

            list_diff = different(
                default_list,
                club_list
            )

            sale_diff = different(
                default_sale,
                club_sale
            )

            has_exclusive_club = (
                list_diff or sale_diff
            )

            candidates = []

            if club_sale is not None:
                candidates.append(
                    ("club_sale", club_sale)
                )

            if club_list is not None:
                candidates.append(
                    ("club_list", club_list)
                )

            club_price = None
            club_source = None

            if has_exclusive_club and candidates:

                valid_candidates = [
                    (source, value)
                    for source, value in candidates
                    if value is not None
                ]

                if valid_candidates:
                    club_source, club_price = min(
                        valid_candidates,
                        key=lambda x: float(x[1])
                    )

            key = (
                str(repository_id),
                str(barcode),
                str(product_id)
            )

            duplicate = key in seen
            seen.add(key)

            results.append({
                "file": file_path.name,
                "item_index": item_index,
                "sku_index": sku_index,
                "name": name,
                "product_id": product_id,
                "repository_id": repository_id,
                "sku_id": sku_id,
                "barcode": barcode,
                "active": active,
                "default_list": default_list,
                "club_list": club_list,
                "default_sale": default_sale,
                "club_sale": club_sale,
                "direct_list": direct_list,
                "direct_sale": direct_sale,
                "list_diff": list_diff,
                "sale_diff": sale_diff,
                "has_exclusive_club": has_exclusive_club,
                "club_price": club_price,
                "club_source": club_source,
                "duplicate": duplicate,
            })

    file_stats.append(
        (file_path.name, len(items), file_skus)
    )


exclusive = [
    r for r in results
    if r["has_exclusive_club"]
]

unique_exclusive = []

unique_keys = set()

for r in exclusive:

    key = (
        str(r["repository_id"]),
        str(r["barcode"]),
        str(r["product_id"])
    )

    if key in unique_keys:
        continue

    unique_keys.add(key)
    unique_exclusive.append(r)


print("=" * 100)
print("AUDITORIA COMPLETA DE PREÇOS, CONFIANÇA")
print("DEFAULT PRICE LIST x CLUB PRICE LIST")
print("=" * 100)

print(f"Diretório: {BASE_DIR}")
print(f"Arquivos encontrados: {len(FILES)}")
print()

print("=" * 100)
print("ARQUIVOS ANALISADOS")
print("=" * 100)

for filename, item_count, sku_count in file_stats:
    print(
        f"{filename}: "
        f"{item_count} produtos | "
        f"{sku_count} SKUs"
    )


print()
print("=" * 100)
print("RESUMO GERAL")
print("=" * 100)

print(f"Registros de SKU analisados: {len(results)}")

unique_products = {
    (
        str(r["repository_id"]),
        str(r["barcode"]),
        str(r["product_id"])
    )
    for r in results
}

print(
    f"SKUs únicos aproximados: "
    f"{len(unique_products)}"
)

print(
    "Registros com diferença Default x Club:",
    len(exclusive)
)

print(
    "SKUs únicos com possível preço exclusivo de clube:",
    len(unique_exclusive)
)


print()
print("=" * 100)
print("PRODUTOS COM DIFERENÇA DEFAULT x CLUB")
print("=" * 100)

if not unique_exclusive:

    print()
    print(
        "Nenhum preço exclusivo de clube "
        "foi encontrado nos arquivos analisados."
    )

else:

    for i, r in enumerate(
        unique_exclusive,
        start=1
    ):

        print()
        print("-" * 100)

        print(
            f"{i}. {r['name']}"
        )

        print("-" * 100)

        print(
            f"Arquivo:       {r['file']}"
        )

        print(
            f"Product ID:    {r['product_id']}"
        )

        print(
            f"repositoryId:  {r['repository_id']}"
        )

        print(
            f"EAN:           {r['barcode']}"
        )

        print(
            f"x_active:      {r['active']}"
        )

        print()

        print(
            "LIST:"
        )

        print(
            f"  Default = "
            f"{money(r['default_list'])}"
        )

        print(
            f"  Club    = "
            f"{money(r['club_list'])}"
        )

        print()

        print(
            "SALE:"
        )

        print(
            f"  Default = "
            f"{money(r['default_sale'])}"
        )

        print(
            f"  Club    = "
            f"{money(r['club_sale'])}"
        )

        print()

        print(
            "DIRETO:"
        )

        print(
            f"  listPrice = "
            f"{money(r['direct_list'])}"
        )

        print(
            f"  salePrice = "
            f"{money(r['direct_sale'])}"
        )

        print()

        print(
            f"Preço clube candidato: "
            f"{money(r['club_price'])}"
        )

        print(
            f"Origem candidato: "
            f"{r['club_source']}"
        )

        print(
            f"LIST diferente: "
            f"{r['list_diff']}"
        )

        print(
            f"SALE diferente: "
            f"{r['sale_diff']}"
        )


print()
print("=" * 100)
print("VALIDAÇÃO DE PADRÃO")
print("=" * 100)

patterns = Counter()

for r in unique_exclusive:

    if r["list_diff"] and r["sale_diff"]:
        patterns[
            "LIST_DIFERENTE_E_SALE_DIFERENTE"
        ] += 1

    elif r["list_diff"]:
        patterns[
            "SOMENTE_LIST_DIFERENTE"
        ] += 1

    elif r["sale_diff"]:
        patterns[
            "SOMENTE_SALE_DIFERENTE"
        ] += 1


if patterns:

    for pattern, count in patterns.items():
        print(
            f"{pattern}: {count}"
        )

else:

    print(
        "Nenhum padrão de preço exclusivo encontrado."
    )


print()
print("=" * 100)
print(
    "RESULTADO: SOMENTE LEITURA DOS JSONS."
)
print(
    "BANCO E COLETOR NÃO ALTERADOS."
)
print("=" * 100)
