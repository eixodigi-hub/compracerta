import json
from pathlib import Path
from collections import Counter

JSON_PATH = Path(
    "/Users/williamcamargo/Projects/compra-certa-mar-lia/"
    "logs/confianca_api_probe_20260718_091243/products_01.json"
)

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

if not JSON_PATH.exists():
    raise SystemExit(f"Arquivo não encontrado: {JSON_PATH}")

with JSON_PATH.open("r", encoding="utf-8") as f:
    data = json.load(f)

items = data.get("items", [])
results = []
counter = Counter()

for item_index, item in enumerate(items):
    if not isinstance(item, dict):
        continue

    product_name = (
        item.get("displayName")
        or item.get("name")
        or item.get("description")
        or "SEM NOME"
    )

    product_id = item.get("repositoryId") or item.get("id")

    for sku_index, sku in enumerate(item.get("childSKUs") or []):
        if not isinstance(sku, dict):
            continue

        name = (
            sku.get("displayName")
            or sku.get("name")
            or product_name
        )

        default_list = nested(
            sku, "listPrices", "DefaultPriceListEsmeralda"
        )

        club_list = nested(
            sku, "listPrices", "ClubPriceListEsmeralda"
        )

        default_sale = nested(
            sku, "salePrices", "DefaultPriceListEsmeralda"
        )

        club_sale = nested(
            sku, "salePrices", "ClubPriceListEsmeralda"
        )

        differences = []

        if default_list != club_list:
            differences.append("LIST_DIFERENTE")

        if default_sale != club_sale:
            differences.append("SALE_DIFERENTE")

        status = (
            " | ".join(differences)
            if differences
            else "SEM_DIFERENCA"
        )

        counter[status] += 1

        results.append({
            "name": name,
            "product_id": product_id,
            "repository_id": sku.get("repositoryId"),
            "barcode": sku.get("barcode"),
            "direct_list": sku.get("listPrice"),
            "direct_sale": sku.get("salePrice"),
            "default_list": default_list,
            "club_list": club_list,
            "default_sale": default_sale,
            "club_sale": club_sale,
            "status": status,
        })

print("=" * 90)
print("AUDITORIA DEFAULT x CLUB, CONFIANÇA")
print("=" * 90)

print(f"Arquivo: {JSON_PATH}")
print(f"Produtos: {len(items)}")
print(f"SKUs analisados: {len(results)}")

print()
print("=" * 90)
print("RESUMO")
print("=" * 90)

for status, count in counter.most_common():
    print(f"{status}: {count}")

different = [
    r for r in results
    if r["status"] != "SEM_DIFERENCA"
]

print()
print(
    "SKUs COM DIFERENÇA ENTRE DEFAULT E CLUB:",
    len(different)
)

if different:
    print()
    print("=" * 90)
    print("DIFERENÇAS ENCONTRADAS")
    print("=" * 90)

    for i, r in enumerate(different, 1):
        print()
        print(f"{i}. {r['name']}")
        print(f"Product ID: {r['product_id']}")
        print(f"repositoryId: {r['repository_id']}")
        print(f"EAN: {r['barcode']}")

        print(
            "LIST:",
            f"Default={money(r['default_list'])}",
            f"Club={money(r['club_list'])}"
        )

        print(
            "SALE:",
            f"Default={money(r['default_sale'])}",
            f"Club={money(r['club_sale'])}"
        )

        print(
            "DIRETO:",
            f"listPrice={money(r['direct_list'])}",
            f"salePrice={money(r['direct_sale'])}"
        )

        print(f"STATUS: {r['status']}")

else:
    print()
    print("Nenhuma diferença encontrada entre Default e Club.")

print()
print("=" * 90)
print("AMOSTRA DOS PRIMEIROS 30 SKUs")
print("=" * 90)

for i, r in enumerate(results[:30], 1):
    print()
    print(f"{i}. {r['name']}")

    print(
        f"LIST Default={money(r['default_list'])}"
        f" | Club={money(r['club_list'])}"
    )

    print(
        f"SALE Default={money(r['default_sale'])}"
        f" | Club={money(r['club_sale'])}"
    )

    print(
        f"DIRETO listPrice={money(r['direct_list'])}"
        f" | salePrice={money(r['direct_sale'])}"
    )

    print(f"Status: {r['status']}")

print()
print("=" * 90)
print("SOMENTE LEITURA. BANCO NÃO ALTERADO.")
print("=" * 90)
