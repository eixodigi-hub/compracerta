#!/usr/bin/env python3

import json
import os
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[2]
LOGS = ROOT / "logs"
ENV = ROOT / ".env"

STORE_ID = "744b59fb-1bf9-4235-a900-fcea7fd1cfec"


def load_env():
    for raw in ENV.read_text(encoding="utf-8").splitlines():
        line = raw.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)

        os.environ.setdefault(
            key.strip(),
            value.strip().strip('"').strip("'"),
        )


def env_first(*names):
    for name in names:
        value = os.environ.get(name, "").strip()

        if value:
            return value

    return ""


def fetch_products(url, key):
    rows = []
    offset = 0

    while True:
        response = requests.get(
            url.rstrip("/") + "/rest/v1/store_products",
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Range-Unit": "items",
                "Range": f"{offset}-{offset + 999}",
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

        response.raise_for_status()

        chunk = response.json()
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
        if row.get("canonical_product_id")
    }


def main():
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

    ingest_url = env_first("INGEST_URL")
    secret = env_first("INGEST_SECRET")

    if not all([
        supabase_url,
        public_key,
        ingest_url,
        secret,
    ]):
        raise SystemExit(
            "ERRO: configuração incompleta no .env."
        )

    files = list(
        LOGS.glob(
            "confianca_new_only_canary_*.json"
        )
    )

    if not files:
        raise SystemExit(
            "ERRO: arquivo canário não encontrado."
        )

    canary_file = max(
        files,
        key=lambda p: p.stat().st_mtime,
    )

    payload = json.loads(
        canary_file.read_text(
            encoding="utf-8"
        )
    )

    products = payload.get("products", [])

    if payload.get("store_id") != STORE_ID:
        raise SystemExit(
            "BLOQUEADO: store_id incorreto."
        )

    if len(products) != 10:
        raise SystemExit(
            "BLOQUEADO: o lote deve ter "
            "exatamente 10 produtos."
        )

    canary_ids = {
        str(p.get("external_id", "")).strip()
        for p in products
    }

    if len(canary_ids) != 10 or "" in canary_ids:
        raise SystemExit(
            "BLOQUEADO: external_ids inválidos "
            "ou duplicados."
        )

    print("=" * 72)
    print("TESTE-CANÁRIO — CONFIANÇA")
    print("=" * 72)
    print(f"Arquivo: {canary_file.name}")
    print("Produtos no lote: 10")
    print()

    before = fetch_products(
        supabase_url,
        public_key,
    )

    before_ids = {
        str(row["external_id"])
        for row in before
    }

    before_canonical = canonical_map(before)

    overlap = canary_ids & before_ids

    print(f"Produtos Confiança antes: {len(before)}")
    print(f"Canários já existentes: {len(overlap)}")
    print(
        "Vínculos canônicos antes: "
        f"{len(before_canonical)}"
    )

    if overlap:
        raise SystemExit(
            "BLOQUEADO: produto do canário "
            "já existe no banco."
        )

    if len(before_canonical) != 36:
        raise SystemExit(
            "BLOQUEADO: eram esperados "
            "36 vínculos canônicos."
        )

    print()
    print("Enviando SOMENTE os 10 produtos novos...")

    response = requests.post(
        ingest_url,
        headers={
            "x-ingest-secret": secret,
            "content-type": "application/json",
        },
        json=payload,
        timeout=180,
    )

    print(f"HTTP: {response.status_code}")

    try:
        print(
            json.dumps(
                response.json(),
                ensure_ascii=False,
                indent=2,
            )
        )
    except Exception:
        print(response.text[:2000])

    if not response.ok:
        raise SystemExit(
            "FALHA: endpoint rejeitou o lote."
        )

    after = fetch_products(
        supabase_url,
        public_key,
    )

    after_ids = {
        str(row["external_id"])
        for row in after
    }

    after_canonical = canonical_map(after)

    inserted = canary_ids & after_ids
    missing = canary_ids - after_ids

    canonical_ok = (
        before_canonical == after_canonical
    )

    print()
    print("=" * 72)
    print("VERIFICAÇÃO PÓS-ENVIO")
    print("=" * 72)

    print(
        f"Produtos Confiança depois: {len(after)}"
    )

    print(
        f"Canários encontrados: {len(inserted)}/10"
    )

    print(
        f"Canários ausentes: {len(missing)}"
    )

    print(
        "Vínculos canônicos depois: "
        f"{len(after_canonical)}"
    )

    print(
        "Mapa canônico preservado: "
        + ("SIM" if canonical_ok else "NÃO")
    )

    success = (
        len(after) == len(before) + 10
        and len(inserted) == 10
        and not missing
        and len(after_canonical) == 36
        and canonical_ok
    )

    print()

    if success:
        print("SUCESSO: TESTE-CANÁRIO APROVADO.")
        print("10 produtos novos inseridos.")
        print(
            "36 vínculos canônicos preservados."
        )
        return

    print("BLOQUEADO: resultado inesperado.")
    print(
        "NÃO prossiga com o lote completo."
    )


if __name__ == "__main__":
    main()
