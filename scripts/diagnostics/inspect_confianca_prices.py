from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[2]
LOG_DIR = ROOT_DIR / "logs"


def latest_directory(pattern: str) -> Path:
    directories = [
        path
        for path in LOG_DIR.glob(pattern)
        if path.is_dir()
    ]

    if not directories:
        raise SystemExit(
            f"ERRO: nenhum diretório encontrado: {pattern}"
        )

    return max(
        directories,
        key=lambda path: path.stat().st_mtime,
    )


def latest_file(pattern: str) -> Path | None:
    files = [
        path
        for path in LOG_DIR.glob(pattern)
        if path.is_file()
    ]

    if not files:
        return None

    return max(
        files,
        key=lambda path: path.stat().st_mtime,
    )


def load_json(path: Path) -> Any:
    return json.loads(
        path.read_text(encoding="utf-8")
    )


def walk_price_values(
    value: Any,
    path: str = "",
) -> list[tuple[str, Any]]:
    found: list[tuple[str, Any]] = []

    if isinstance(value, dict):
        for key, nested_value in value.items():
            nested_path = (
                f"{path}.{key}"
                if path
                else key
            )

            key_lower = key.lower()

            if (
                "price" in key_lower
                and nested_value is not None
            ):
                found.append(
                    (
                        nested_path,
                        nested_value,
                    )
                )

            found.extend(
                walk_price_values(
                    nested_value,
                    nested_path,
                )
            )

    elif isinstance(value, list):
        for index, nested_value in enumerate(value):
            found.extend(
                walk_price_values(
                    nested_value,
                    f"{path}[{index}]",
                )
            )

    return found


def compact(value: Any, limit: int = 5000) -> str:
    text = json.dumps(
        value,
        ensure_ascii=False,
        indent=2,
    )

    if len(text) > limit:
        return text[:limit] + "\n... conteúdo reduzido ..."

    return text


def inspect_products(probe_dir: Path) -> None:
    products_files = sorted(
        probe_dir.glob("products_*.json")
    )

    if not products_files:
        print("ERRO: products_*.json não encontrado.")
        return

    products_file = products_files[0]
    data = load_json(products_file)
    items = data.get("items", [])

    print("=" * 70)
    print("PRODUTOS")
    print("=" * 70)
    print(f"Arquivo: {products_file}")
    print(f"Quantidade de produtos: {len(items)}")
    print()

    top_level_prices = 0
    child_sku_prices = 0
    recursive_prices = 0

    examples: list[dict[str, Any]] = []

    for product in items:
        product_id = product.get("id")
        display_name = product.get("displayName")

        top_values = {
            "listPrice": product.get("listPrice"),
            "salePrice": product.get("salePrice"),
            "listPrices": product.get("listPrices"),
            "salePrices": product.get("salePrices"),
        }

        if any(
            value not in (None, {}, [])
            for value in top_values.values()
        ):
            top_level_prices += 1

        child_skus = product.get("childSKUs") or []

        child_values: list[dict[str, Any]] = []

        if isinstance(child_skus, list):
            for sku in child_skus:
                if not isinstance(sku, dict):
                    continue

                sku_prices = {
                    key: value
                    for key, value in sku.items()
                    if "price" in key.lower()
                    and value is not None
                }

                if sku_prices:
                    child_sku_prices += 1
                    child_values.append(
                        {
                            "sku_id": (
                                sku.get("repositoryId")
                                or sku.get("id")
                            ),
                            "prices": sku_prices,
                        }
                    )

        recursive = [
            {
                "path": found_path,
                "value": found_value,
            }
            for found_path, found_value
            in walk_price_values(product)
            if found_value not in (
                None,
                {},
                [],
            )
        ]

        if recursive:
            recursive_prices += 1

        if (
            len(examples) < 5
            and (
                child_values
                or recursive
                or top_values["listPrice"] is not None
                or top_values["salePrice"] is not None
            )
        ):
            examples.append(
                {
                    "id": product_id,
                    "displayName": display_name,
                    "top_level": top_values,
                    "child_skus": child_values[:3],
                    "recursive_values": recursive[:20],
                }
            )

    print(
        "Produtos com preço no nível principal: "
        f"{top_level_prices}"
    )
    print(
        "SKUs filhos com algum campo de preço: "
        f"{child_sku_prices}"
    )
    print(
        "Produtos com algum valor de preço encontrado: "
        f"{recursive_prices}"
    )
    print()

    if examples:
        print("EXEMPLOS DE PREÇOS ENCONTRADOS")
        print(compact(examples))
    else:
        print(
            "Nenhum valor de preço não nulo foi encontrado "
            "na resposta de produtos."
        )

    print()
    print("ESTRUTURA DO PRIMEIRO PRODUTO")
    print()

    if items:
        first_product = items[0]

        print("Chaves principais:")
        print(
            ", ".join(
                sorted(first_product.keys())
            )
        )
        print()
        print("childSKUs do primeiro produto:")
        print(
            compact(
                first_product.get("childSKUs"),
                limit=8000,
            )
        )


def inspect_sites(probe_dir: Path) -> None:
    sites_files = sorted(
        probe_dir.glob("sites_*.json")
    )

    if not sites_files:
        return

    data = load_json(sites_files[0])
    items = data.get("items", [])

    print()
    print("=" * 70)
    print("SITES E UNIDADES")
    print("=" * 70)

    for item in items:
        item_text = json.dumps(
            item,
            ensure_ascii=False,
        ).lower()

        if any(
            term in item_text
            for term in (
                "esmeralda",
                "marilia",
                "marília",
            )
        ):
            print(compact(item, limit=5000))
            print()


def inspect_network() -> None:
    network_file = latest_file(
        "confianca_network_*.jsonl"
    )

    if network_file is None:
        print("Nenhum arquivo de rede encontrado.")
        return

    print()
    print("=" * 70)
    print("ENDPOINTS RELACIONADOS A PREÇO")
    print("=" * 70)
    print(f"Arquivo: {network_file}")
    print()

    matches: list[str] = []
    seen: set[str] = set()

    for line in network_file.read_text(
        encoding="utf-8"
    ).splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue

        url = str(record.get("url", ""))
        resource_type = str(
            record.get("resource_type", "")
        )

        url_lower = url.lower()

        has_price_term = any(
            term in url_lower
            for term in (
                "price",
                "pricing",
                "pricelist",
                "pricegroup",
                "saleprice",
                "listprice",
            )
        )

        is_api = (
            resource_type in {"fetch", "xhr"}
            or "/ccstore/v1/" in url_lower
        )

        if not has_price_term or not is_api:
            continue

        if url in seen:
            continue

        seen.add(url)
        matches.append(
            f"{record.get('status')} "
            f"{resource_type} "
            f"{url}"
        )

    if matches:
        for match in matches[:100]:
            print(match)
    else:
        print(
            "Nenhum endpoint específico de preço "
            "foi identificado no log."
        )


def main() -> int:
    probe_dir = latest_directory(
        "confianca_api_probe_*"
    )

    print(f"Diagnóstico analisado: {probe_dir}")
    print()

    inspect_products(probe_dir)
    inspect_sites(probe_dir)
    inspect_network()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
