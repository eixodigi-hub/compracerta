#!/usr/bin/env python3

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import requests


ROOT_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT_DIR / ".env"
LOG_DIR = ROOT_DIR / "logs"

CONFIANCA_STORE_ID = (
    "4f97f5d6-6a17-46ab-bf63-b3724abef9ff"
)

TAUSTE_STORE_ID = (
    "9cc4a9b1-5bc1-48e8-b3ff-c89fa7009b02"
)

PAGE_SIZE = 1000


def load_env() -> None:
    if not ENV_FILE.exists():
        return

    for raw_line in ENV_FILE.read_text(
        encoding="utf-8"
    ).splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#"):
            continue

        if "=" not in line:
            continue

        key, value = line.split("=", 1)

        key = key.strip()
        value = (
            value.strip()
            .strip('"')
            .strip("'")
        )

        if key:
            os.environ.setdefault(
                key,
                value,
            )


def first_env(*names: str) -> str:
    for name in names:
        value = os.environ.get(
            name,
            "",
        ).strip()

        if value:
            return value

    return ""


def latest_consolidated() -> Path:
    files = list(
        LOG_DIR.glob(
            "confianca_consolidated_*.json"
        )
    )

    if not files:
        raise SystemExit(
            "ERRO: catálogo consolidado "
            "não encontrado."
        )

    return max(
        files,
        key=lambda path: path.stat().st_mtime,
    )


def fetch_store_products(
    supabase_url: str,
    key: str,
    store_id: str,
) -> list[dict[str, Any]]:
    url = (
        supabase_url.rstrip("/")
        + "/rest/v1/store_products"
    )

    rows: list[dict[str, Any]] = []
    offset = 0

    while True:
        headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Range-Unit": "items",
            "Range": (
                f"{offset}-"
                f"{offset + PAGE_SIZE - 1}"
            ),
        }

        params = {
            "select": (
                "id,store_id,"
                "canonical_product_id,"
                "external_id,"
                "external_name,"
                "active,available"
            ),
            "store_id": f"eq.{store_id}",
            "order": "external_id.asc",
        }

        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=60,
        )

        if response.status_code not in (
            200,
            206,
        ):
            raise SystemExit(
                "ERRO ao consultar Supabase: "
                f"HTTP {response.status_code}\n"
                f"{response.text[:500]}"
            )

        chunk = response.json()

        if not isinstance(chunk, list):
            raise SystemExit(
                "ERRO: resposta inesperada "
                "do Supabase."
            )

        rows.extend(chunk)

        if len(chunk) < PAGE_SIZE:
            break

        offset += PAGE_SIZE

    return rows


def main() -> int:
    load_env()

    supabase_url = first_env(
        "SUPABASE_URL",
        "VITE_SUPABASE_URL",
    )

    key = first_env(
        "SUPABASE_ANON_KEY",
        "SUPABASE_PUBLISHABLE_KEY",
        "VITE_SUPABASE_PUBLISHABLE_KEY",
        "VITE_SUPABASE_ANON_KEY",
    )

    if not supabase_url:
        print(
            "ERRO: URL do Supabase "
            "não encontrada no .env."
        )
        return 2

    if not key:
        print(
            "ERRO: chave pública/anon do "
            "Supabase não encontrada no .env."
        )
        return 3

    catalog_file = latest_consolidated()

    data = json.loads(
        catalog_file.read_text(
            encoding="utf-8"
        )
    )

    products = data.get(
        "products",
        [],
    )

    if not isinstance(products, list):
        print(
            "ERRO: products inválido "
            "no catálogo consolidado."
        )
        return 4

    catalog_ids = {
        str(
            product.get(
                "external_id",
                "",
            )
        ).strip()
        for product in products
        if isinstance(product, dict)
        and str(
            product.get(
                "external_id",
                "",
            )
        ).strip()
    }

    confianca_rows = fetch_store_products(
        supabase_url,
        key,
        CONFIANCA_STORE_ID,
    )

    tauste_rows = fetch_store_products(
        supabase_url,
        key,
        TAUSTE_STORE_ID,
    )

    confianca_by_external = {}

    duplicate_db_ids = []

    for row in confianca_rows:
        external_id = str(
            row.get(
                "external_id",
                "",
            )
        ).strip()

        if external_id in confianca_by_external:
            duplicate_db_ids.append(
                external_id
            )

        confianca_by_external[
            external_id
        ] = row

    db_ids = set(
        confianca_by_external
    )

    existing_ids = (
        catalog_ids
        & db_ids
    )

    new_ids = (
        catalog_ids
        - db_ids
    )

    db_not_in_catalog = (
        db_ids
        - catalog_ids
    )

    linked_confianca = [
        row
        for row in confianca_rows
        if row.get(
            "canonical_product_id"
        )
    ]

    linked_ids = {
        str(
            row.get(
                "external_id",
                "",
            )
        ).strip()
        for row in linked_confianca
    }

    linked_missing_catalog = (
        linked_ids
        - catalog_ids
    )

    confianca_canonical_ids = {
        str(
            row["canonical_product_id"]
        )
        for row in linked_confianca
        if row.get(
            "canonical_product_id"
        )
    }

    tauste_canonical_ids = {
        str(
            row["canonical_product_id"]
        )
        for row in tauste_rows
        if row.get(
            "canonical_product_id"
        )
    }

    shared_canonical_ids = (
        confianca_canonical_ids
        & tauste_canonical_ids
    )

    print("=" * 72)
    print(
        "SIMULAÇÃO DE SINCRONIZAÇÃO "
        "— CONFIANÇA"
    )
    print("=" * 72)

    print(
        f"Catálogo consolidado: "
        f"{catalog_file.name}"
    )

    print(
        f"Produtos no catálogo novo: "
        f"{len(catalog_ids)}"
    )

    print()
    print("ESTADO ATUAL NO SUPABASE")
    print("-" * 72)

    print(
        f"Store products Confiança atuais: "
        f"{len(confianca_rows)}"
    )

    print(
        f"External IDs duplicados no banco: "
        f"{len(duplicate_db_ids)}"
    )

    print()
    print("SIMULAÇÃO")
    print("-" * 72)

    print(
        f"Já existentes e presentes "
        f"no catálogo novo: "
        f"{len(existing_ids)}"
    )

    print(
        f"Novos external_ids a criar: "
        f"{len(new_ids)}"
    )

    print(
        f"Registros atuais fora do "
        f"catálogo novo: "
        f"{len(db_not_in_catalog)}"
    )

    print()
    print("VÍNCULOS CANÔNICOS")
    print("-" * 72)

    print(
        f"Produtos Confiança com "
        f"canonical_product_id: "
        f"{len(linked_confianca)}"
    )

    print(
        f"Canonical IDs únicos "
        f"no Confiança: "
        f"{len(confianca_canonical_ids)}"
    )

    print(
        f"Canonical IDs também encontrados "
        f"no Tauste: "
        f"{len(shared_canonical_ids)}"
    )

    print(
        f"Produtos vinculados ausentes "
        f"do catálogo novo: "
        f"{len(linked_missing_catalog)}"
    )

    if linked_missing_catalog:
        print()
        print(
            "ATENÇÃO — vínculos cujos "
            "external_ids não estão "
            "no catálogo novo:"
        )

        for external_id in sorted(
            linked_missing_catalog
        ):
            row = confianca_by_external[
                external_id
            ]

            print(
                f"  {external_id} | "
                f"{row.get('external_name')}"
            )

    print()
    print("=" * 72)
    print(
        "RESULTADO DE SEGURANÇA"
    )
    print("=" * 72)

    if duplicate_db_ids:
        print(
            "BLOQUEIO: há external_ids "
            "duplicados no banco."
        )
    elif linked_missing_catalog:
        print(
            "BLOQUEIO: há produtos com "
            "vínculo canônico fora do "
            "catálogo novo."
        )
    else:
        print(
            "Catálogo compatível com os "
            "vínculos canônicos atuais."
        )

    print()
    print(
        "Esta simulação fez apenas "
        "consultas GET."
    )

    print(
        "Nenhuma alteração foi feita "
        "no Supabase."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
