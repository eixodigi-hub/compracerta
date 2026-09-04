#!/usr/bin/env python3

import json
import os
from datetime import datetime
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[2]
LOGS = ROOT / "logs"
ENV = ROOT / ".env"

STORE_ID = "744b59fb-1bf9-4235-a900-fcea7fd1cfec"


def load_env():
    if not ENV.exists():
        return

    for raw in ENV.read_text(encoding="utf-8").splitlines():
        line = raw.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)

        os.environ.setdefault(
            key.strip(),
            value.strip().strip('"').strip("'"),
        )


def first_env(*names):
    for name in names:
        value = os.environ.get(name, "").strip()

        if value:
            return value

    return ""


def latest_catalog():
    files = list(
        LOGS.glob("confianca_consolidated_*.json")
    )

    if not files:
        raise SystemExit(
            "ERRO: catálogo consolidado não encontrado."
        )

    return max(
        files,
        key=lambda p: p.stat().st_mtime,
    )


def fetch_existing(url, key):
    rows = []
    offset = 0
    page_size = 1000

    while True:
        response = requests.get(
            url.rstrip("/") + "/rest/v1/store_products",
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Range-Unit": "items",
                "Range": (
                    f"{offset}-{offset + page_size - 1}"
                ),
            },
            params={
                "select": (
                    "id,external_id,external_name,"
                    "canonical_product_id"
                ),
                "store_id": f"eq.{STORE_ID}",
                "order": "external_id.asc",
            },
            timeout=60,
        )

        if response.status_code not in (200, 206):
            raise SystemExit(
                f"ERRO Supabase HTTP "
                f"{response.status_code}: "
                f"{response.text[:500]}"
            )

        chunk = response.json()
        rows.extend(chunk)

        if len(chunk) < page_size:
            break

        offset += page_size

    return rows


def convert(product, collected_at):
    promotional = bool(
        product.get("promotional")
    )

    sale_price = product.get("sale_price")

    return {
        "external_id": str(
            product.get("external_id", "")
        ).strip(),
        "external_name": str(
            product.get("name", "")
        ).strip(),
        "product_url": product.get("product_url"),
        "image_url": product.get("image_url"),
        "brand_raw": None,
        "quantity_raw": (
            str(product["weight"])
            if product.get("weight") is not None
            else None
        ),
        "unit_raw": product.get(
            "unit_of_measurement"
        ),
        "barcode_raw": product.get("barcode"),
        "regular_price": product.get(
            "regular_price"
        ),
        "promotional_price": (
            sale_price
            if promotional
            else None
        ),
        "effective_price": product.get("price"),
        "promotion_text": (
            "Oferta Confiança"
            if promotional
            else None
        ),
        "promotion_end_at": None,
        "available": bool(
            product.get("available")
        ),
        "collected_at": collected_at,
        "source_category": product.get(
            "source_category"
        ),
    }


def main():
    load_env()

    url = first_env(
        "SUPABASE_URL",
        "VITE_SUPABASE_URL",
    )

    key = first_env(
        "SUPABASE_ANON_KEY",
        "SUPABASE_PUBLISHABLE_KEY",
        "VITE_SUPABASE_PUBLISHABLE_KEY",
        "VITE_SUPABASE_ANON_KEY",
    )

    if not url or not key:
        raise SystemExit(
            "ERRO: credenciais públicas do Supabase ausentes."
        )

    catalog_path = latest_catalog()

    catalog = json.loads(
        catalog_path.read_text(
            encoding="utf-8"
        )
    )

    products = catalog["products"]

    existing = fetch_existing(
        url,
        key,
    )

    existing_ids = {
        str(row["external_id"]).strip()
        for row in existing
    }

    new_products = [
        product
        for product in products
        if str(
            product.get("external_id", "")
        ).strip()
        not in existing_ids
    ]

    collected_at = (
        datetime.now()
        .astimezone()
        .isoformat()
    )

    converted = [
        convert(product, collected_at)
        for product in new_products
    ]

    ids = [
        product["external_id"]
        for product in converted
    ]

    invalid = [
        product["external_id"]
        for product in converted
        if (
            not product["external_id"]
            or not product["external_name"]
            or not isinstance(
                product["effective_price"],
                (int, float),
            )
            or isinstance(
                product["effective_price"],
                bool,
            )
            or product["effective_price"] <= 0
        )
    ]

    overlap = (
        set(ids)
        & existing_ids
    )

    if len(ids) != len(set(ids)):
        raise SystemExit(
            "ERRO: external_id duplicado "
            "no lote novo."
        )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    full_file = LOGS / (
        f"confianca_new_only_{timestamp}.json"
    )

    canary_file = LOGS / (
        f"confianca_new_only_canary_{timestamp}.json"
    )

    full_file.write_text(
        json.dumps(
            {
                "store_id": STORE_ID,
                "products": converted,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    canary_file.write_text(
        json.dumps(
            {
                "store_id": STORE_ID,
                "products": converted[:10],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    linked = sum(
        1
        for row in existing
        if row.get("canonical_product_id")
    )

    print("=" * 72)
    print("PREPARAÇÃO DA EXPANSÃO — CONFIANÇA")
    print("=" * 72)
    print(
        f"Catálogo consolidado: {len(products)}"
    )
    print(
        f"Produtos já existentes: {len(existing_ids)}"
    )
    print(
        f"Produtos novos preparados: {len(converted)}"
    )
    print(
        f"Interseção novos x existentes: {len(overlap)}"
    )
    print(
        f"Produtos inválidos: {len(invalid)}"
    )
    print(
        f"Vínculos canônicos atuais: {linked}"
    )
    print()
    print(f"Lote completo: {full_file}")
    print(f"Canário de 10: {canary_file}")
    print()

    if (
        len(products) == 9306
        and len(existing_ids) == 290
        and len(converted) == 9016
        and len(overlap) == 0
        and len(invalid) == 0
        and linked == 36
    ):
        print(
            "RESULTADO: lote novo isolado corretamente."
        )
    else:
        print(
            "RESULTADO: BLOQUEADO — "
            "há números inesperados."
        )

    print()
    print(
        "Nenhuma alteração foi feita no Supabase."
    )


if __name__ == "__main__":
    main()
