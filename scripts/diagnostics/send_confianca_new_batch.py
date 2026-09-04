#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[2]
LOGS = ROOT / "logs"
ENV = ROOT / ".env"

STORE_ID = (
    "744b59fb-1bf9-4235-a900-fcea7fd1cfec"
)

BATCH_SIZE = 50


def load_env():
    if not ENV.exists():
        return

    for raw in ENV.read_text(
        encoding="utf-8"
    ).splitlines():
        line = raw.strip()

        if (
            not line
            or line.startswith("#")
            or "=" not in line
        ):
            continue

        key, value = line.split("=", 1)

        os.environ.setdefault(
            key.strip(),
            value.strip()
            .strip('"')
            .strip("'"),
        )


def env_first(*names):
    for name in names:
        value = os.environ.get(
            name,
            "",
        ).strip()

        if value:
            return value

    return ""


def fetch_products(url, key):
    rows = []
    offset = 0

    while True:
        response = requests.get(
            url.rstrip("/")
            + "/rest/v1/store_products",
            headers={
                "apikey": key,
                "Authorization": (
                    f"Bearer {key}"
                ),
                "Range-Unit": "items",
                "Range": (
                    f"{offset}-"
                    f"{offset + 999}"
                ),
            },
            params={
                "select": (
                    "id,external_id,"
                    "external_name,"
                    "canonical_product_id"
                ),
                "store_id": (
                    f"eq.{STORE_ID}"
                ),
                "order": "external_id.asc",
            },
            timeout=60,
        )

        response.raise_for_status()

        chunk = response.json()

        if not isinstance(chunk, list):
            raise SystemExit(
                "ERRO: resposta inválida "
                "do Supabase."
            )

        rows.extend(chunk)

        if len(chunk) < 1000:
            break

        offset += 1000

    return rows


def canonical_map(rows):
    return {
        str(row["external_id"]): str(
            row["canonical_product_id"]
        )
        for row in rows
        if row.get(
            "canonical_product_id"
        )
    }


def latest_full_file():
    files = [
        path
        for path in LOGS.glob(
            "confianca_new_only_*.json"
        )
        if "canary" not in path.name
    ]

    if not files:
        raise SystemExit(
            "ERRO: lote completo "
            "não encontrado."
        )

    return max(
        files,
        key=lambda p: p.stat().st_mtime,
    )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--limite",
        type=int,
        required=True,
    )

    args = parser.parse_args()

    if args.limite <= 0:
        raise SystemExit(
            "ERRO: limite deve ser maior que zero."
        )

    load_env()

    supabase_url = env_first(
        "SUPABASE_URL",
        "VITE_SUPABASE_URL",
    )

    public_key = env_first(
        "SUPABASE_ANON_KEY",
        "SUPABASE_PUBLISHABLE_KEY",
        "VITE_SUPABASE_PUBLISHABLE_KEY",
        "VITE_SUPABASE_ANON_KEY",
    )

    ingest_url = env_first(
        "INGEST_URL"
    )

    secret = env_first(
        "INGEST_SECRET"
    )

    if not all([
        supabase_url,
        public_key,
        ingest_url,
        secret,
    ]):
        raise SystemExit(
            "ERRO: configuração incompleta "
            "no .env."
        )

    full_file = latest_full_file()

    data = json.loads(
        full_file.read_text(
            encoding="utf-8"
        )
    )

    all_products = data.get(
        "products",
        [],
    )

    print("=" * 72)
    print(
        "INGESTÃO CONTROLADA "
        "— CONFIANÇA"
    )
    print("=" * 72)

    print(
        f"Arquivo mestre: "
        f"{full_file.name}"
    )

    before = fetch_products(
        supabase_url,
        public_key,
    )

    before_ids = {
        str(
            row.get(
                "external_id",
                "",
            )
        ).strip()
        for row in before
    }

    before_canonical = canonical_map(
        before
    )

    pending = [
        product
        for product in all_products
        if str(
            product.get(
                "external_id",
                "",
            )
        ).strip()
        not in before_ids
    ]

    selected = pending[
        :args.limite
    ]

    print(
        f"Produtos Confiança antes: "
        f"{len(before)}"
    )

    print(
        f"Vínculos canônicos antes: "
        f"{len(before_canonical)}"
    )

    print(
        f"Produtos ainda pendentes: "
        f"{len(pending)}"
    )

    print(
        f"Produtos selecionados nesta rodada: "
        f"{len(selected)}"
    )

    if len(before_canonical) != 36:
        raise SystemExit(
            "BLOQUEADO: quantidade de "
            "vínculos canônicos diferente de 36."
        )

    if not selected:
        print()
        print(
            "Nenhum produto novo pendente."
        )
        return

    selected_ids = {
        str(
            product["external_id"]
        )
        for product in selected
    }

    if len(selected_ids) != len(
        selected
    ):
        raise SystemExit(
            "BLOQUEADO: IDs duplicados "
            "no lote selecionado."
        )

    print()
    print("-" * 72)
    print("INICIANDO ENVIO")
    print("-" * 72)

    created_total = 0
    updated_total = 0
    errors_total = 0
    batches_ok = 0

    for start in range(
        0,
        len(selected),
        BATCH_SIZE,
    ):
        batch = selected[
            start:start + BATCH_SIZE
        ]

        batch_number = (
            start // BATCH_SIZE
        ) + 1

        payload = {
            "store_id": STORE_ID,
            "products": batch,
        }

        response = requests.post(
            ingest_url,
            headers={
                "x-ingest-secret": secret,
                "content-type": (
                    "application/json"
                ),
            },
            json=payload,
            timeout=180,
        )

        print(
            f"Lote {batch_number}: "
            f"HTTP {response.status_code}"
        )

        if not response.ok:
            print(
                response.text[:1000]
            )

            raise SystemExit(
                "BLOQUEADO: falha no envio. "
                "Execução interrompida."
            )

        result = response.json()

        counts = result.get(
            "counts",
            {},
        )

        created = int(
            counts.get(
                "created",
                0,
            )
        )

        updated = int(
            counts.get(
                "updated",
                0,
            )
        )

        errors = int(
            counts.get(
                "errors",
                0,
            )
        )

        print(
            f"  created={created} "
            f"updated={updated} "
            f"errors={errors}"
        )

        created_total += created
        updated_total += updated
        errors_total += errors
        batches_ok += 1

        if updated != 0 or errors != 0:
            raise SystemExit(
                "BLOQUEADO: lote apresentou "
                "updates ou erros inesperados."
            )

        time.sleep(1)

    print()
    print("-" * 72)
    print("VERIFICAÇÃO PÓS-ENVIO")
    print("-" * 72)

    after = fetch_products(
        supabase_url,
        public_key,
    )

    after_ids = {
        str(
            row.get(
                "external_id",
                "",
            )
        ).strip()
        for row in after
    }

    after_canonical = canonical_map(
        after
    )

    inserted = (
        selected_ids
        & after_ids
    )

    missing = (
        selected_ids
        - after_ids
    )

    canonical_ok = (
        before_canonical
        == after_canonical
    )

    expected_total = (
        len(before)
        + len(selected)
    )

    print(
        f"Lotes concluídos: "
        f"{batches_ok}"
    )

    print(
        f"Criados reportados: "
        f"{created_total}"
    )

    print(
        f"Atualizados reportados: "
        f"{updated_total}"
    )

    print(
        f"Erros reportados: "
        f"{errors_total}"
    )

    print()
    print(
        f"Produtos Confiança depois: "
        f"{len(after)}"
    )

    print(
        f"Total esperado: "
        f"{expected_total}"
    )

    print(
        f"Produtos desta rodada encontrados: "
        f"{len(inserted)}/{len(selected)}"
    )

    print(
        f"Produtos ausentes: "
        f"{len(missing)}"
    )

    print(
        f"Vínculos canônicos depois: "
        f"{len(after_canonical)}"
    )

    print(
        "Mapa canônico preservado: "
        + (
            "SIM"
            if canonical_ok
            else "NÃO"
        )
    )

    success = (
        len(after)
        == expected_total
        and created_total
        == len(selected)
        and updated_total == 0
        and errors_total == 0
        and not missing
        and len(after_canonical) == 36
        and canonical_ok
    )

    print()
    print("=" * 72)
    print("RESULTADO FINAL")
    print("=" * 72)

    if success:
        print(
            "SUCESSO: rodada aprovada."
        )

        print(
            f"{len(selected)} produtos "
            "novos inseridos com segurança."
        )

        print(
            "36 vínculos canônicos "
            "preservados integralmente."
        )

        print(
            f"Restantes estimados: "
            f"{len(pending) - len(selected)}"
        )

        return

    print(
        "BLOQUEADO: resultado inesperado."
    )

    print(
        "NÃO execute nova rodada."
    )


if __name__ == "__main__":
    main()
