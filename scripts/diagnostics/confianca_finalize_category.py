from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any
from uuid import uuid4

import requests


ROOT_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT_DIR / ".env"
LOG_DIR = ROOT_DIR / "logs"

STORE_ID = "4f97f5d6-6a17-46ab-bf63-b3724abef9ff"

# Mesmas chaves de scripts/collectors/confianca_marilia.py::CATEGORIES.
CATEGORY_CHOICES = (
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
)


def load_env() -> None:
    if not ENV_FILE.exists():
        return

    for raw_line in ENV_FILE.read_text(
        encoding="utf-8",
    ).splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#"):
            continue

        if "=" not in line:
            continue

        key, value = line.split("=", 1)

        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key:
            os.environ.setdefault(key, value)


def _file_category(path: Path) -> str | None:
    try:
        data = json.loads(
            path.read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return None

    if not isinstance(data, dict):
        return None

    category = data.get("category")

    return category if isinstance(category, str) else None


def latest_file(pattern: str, category: str) -> Path:
    files = [
        path
        for path in LOG_DIR.glob(pattern)
        if path.is_file()
        and _file_category(path) == category
    ]

    if not files:
        raise SystemExit(
            f"ERRO: nenhum arquivo encontrado para {pattern!r} "
            f"na categoria {category!r}."
        )

    return max(
        files,
        key=lambda path: path.stat().st_mtime,
    )


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(
        path.read_text(encoding="utf-8")
    )

    if not isinstance(data, dict):
        raise SystemExit(
            f"ERRO: conteúdo inválido em {path}"
        )

    return data


def successful_finalization_exists(
    preview_file: Path,
) -> Path | None:
    for result_file in sorted(
        LOG_DIR.glob("confianca_finalize_*.json"),
        reverse=True,
    ):
        try:
            result = load_json(result_file)
        except Exception:
            continue

        if (
            result.get("preview_file")
            == str(preview_file)
            and result.get("http_status") in range(200, 300)
        ):
            return result_file

    return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Finalização segura de uma categoria "
            "do Confiança."
        )
    )

    parser.add_argument(
        "--categoria",
        choices=CATEGORY_CHOICES,
        default="alimentos_basicos",
    )

    parser.add_argument(
        "--enviar",
        action="store_true",
        help="Executa a finalização real.",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_env()

    configured_store_id = os.environ.get(
        "CONFIANCA_STORE_ID",
        "",
    ).strip()

    secret = os.environ.get(
        "INGEST_SECRET",
        "",
    ).strip()

    finalize_url = os.environ.get(
        "FINALIZE_CATEGORY_URL",
        "",
    ).strip()

    if configured_store_id != STORE_ID:
        print(
            "ERRO: CONFIANCA_STORE_ID diferente "
            "da loja esperada."
        )
        print(f"Encontrado: {configured_store_id}")
        return 2

    preview_file = latest_file(
        "confianca_preview_*.json",
        args.categoria,
    )

    ingest_file = latest_file(
        "confianca_full_ingest_*.json",
        args.categoria,
    )

    preview = load_json(preview_file)
    ingest = load_json(ingest_file)

    products = preview.get("products", [])

    if not isinstance(products, list):
        print("ERRO: products inválido na prévia.")
        return 3

    seen_external_ids = sorted(
        {
            str(product.get("external_id", "")).strip()
            for product in products
            if (
                isinstance(product, dict)
                and product.get("source_category")
                == args.categoria
                and str(
                    product.get("external_id", "")
                ).strip()
            )
        }
    )

    errors: list[str] = []

    expected_total = preview.get("expected_total")
    ids_collected = preview.get("ids_collected")
    products_normalized = preview.get(
        "products_normalized"
    )

    # Só a categoria com "catálogo assembler" reporta expected_total;
    # as demais paginam por HTML e usam ids_collected como referência
    # (mesmo critério de scripts/diagnostics/confianca_full_ingest.py).
    reference_total = (
        expected_total
        if isinstance(expected_total, int)
        else ids_collected
    )

    ingest_preview_file = ingest.get(
        "preview_file"
    )

    if ingest_preview_file != str(preview_file):
        errors.append(
            "a ingestão mais recente não pertence "
            "à prévia mais recente"
        )

    products_expected = ingest.get(
        "products_expected"
    )

    products_sent = ingest.get(
        "products_sent"
    )

    batch_failures = ingest.get(
        "batch_failures"
    )

    if (
        not isinstance(reference_total, int)
        or reference_total <= 0
    ):
        errors.append(
            f"total de referência inválido: {reference_total}"
        )

    if ids_collected != reference_total:
        errors.append(
            "ids_collected diferente do total de referência"
        )

    if products_normalized != reference_total:
        errors.append(
            "products_normalized diferente do total de referência"
        )

    if products_expected != reference_total:
        errors.append(
            "products_expected da ingestão está incorreto"
        )

    if products_sent != reference_total:
        errors.append(
            "products_sent da ingestão está incorreto"
        )

    if batch_failures != 0:
        errors.append(
            f"ingestão possui falhas: {batch_failures}"
        )

    if len(seen_external_ids) != reference_total:
        errors.append(
            "quantidade de IDs para finalização incorreta: "
            f"{len(seen_external_ids)}"
        )

    if len(seen_external_ids) != len(
        set(seen_external_ids)
    ):
        errors.append(
            "existem IDs duplicados"
        )

    previous = successful_finalization_exists(
        preview_file
    )

    if previous is not None:
        errors.append(
            "esta mesma prévia já foi finalizada com sucesso: "
            f"{previous}"
        )

    print("=" * 60)
    print("FINALIZAÇÃO DO CONFIANÇA")
    print("=" * 60)
    print(f"Prévia: {preview_file}")
    print(f"Ingestão: {ingest_file}")
    print(f"Store ID: {configured_store_id}")
    print(f"Categoria: {args.categoria}")
    print(
        f"IDs que serão marcados como vistos: "
        f"{len(seen_external_ids)}"
    )
    print()

    if errors:
        print("FINALIZAÇÃO BLOQUEADA:")

        for error in errors:
            print(f"- {error}")

        return 4

    raw_collected_at = preview.get(
        "generated_at"
    )

    timezone_sp = ZoneInfo(
        "America/Sao_Paulo"
    )

    if isinstance(
        raw_collected_at,
        str,
    ) and raw_collected_at.strip():
        try:
            collected_datetime = (
                datetime.fromisoformat(
                    raw_collected_at
                    .strip()
                    .replace("Z", "+00:00")
                )
            )

            if collected_datetime.tzinfo is None:
                collected_datetime = (
                    collected_datetime.replace(
                        tzinfo=timezone_sp
                    )
                )

            collected_at = (
                collected_datetime.isoformat()
            )

        except ValueError:
            collected_at = (
                datetime.now(
                    timezone_sp
                ).isoformat()
            )

    else:
        collected_at = (
            datetime.now(
                timezone_sp
            ).isoformat()
        )

    sync_token = (
        f"confianca-{args.categoria}-{uuid4()}"
    )

    payload = {
        "store_id": configured_store_id,
        "category_key": args.categoria,
        "seen_external_ids": seen_external_ids,
        "sync_token": sync_token,
        "collected_at": collected_at,
    }

    print(f"Sync token: {sync_token}")

    if not args.enviar:
        print()
        print("PRÉVIA APROVADA.")
        print("Nenhuma finalização foi executada.")
        print(
            "Execute novamente com --enviar."
        )
        return 0

    if not secret or not finalize_url:
        print(
            "ERRO: INGEST_SECRET ou "
            "FINALIZE_CATEGORY_URL não configurado."
        )
        return 5

    print()
    print("Executando finalização...")

    try:
        response = requests.post(
            finalize_url,
            headers={
                "x-ingest-secret": secret,
                "content-type": "application/json",
            },
            json=payload,
            timeout=120,
        )
    except requests.RequestException as error:
        print(f"ERRO de conexão: {error}")
        return 6

    try:
        response_data: Any = response.json()
    except ValueError:
        response_data = {
            "raw_response": response.text[:3000],
        }

    print(f"HTTP: {response.status_code}")
    print(
        json.dumps(
            response_data,
            ensure_ascii=False,
            indent=2,
        )
    )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    result_file = (
        LOG_DIR
        / f"confianca_finalize_{timestamp}.json"
    )

    result_file.write_text(
        json.dumps(
            {
                "finalized_at": (
                    datetime.now()
                    .astimezone()
                    .isoformat()
                ),
                "preview_file": str(preview_file),
                "ingest_file": str(ingest_file),
                "store_id": configured_store_id,
                "category_key": args.categoria,
                "seen_external_ids_count": (
                    len(seen_external_ids)
                ),
                "sync_token": sync_token,
                "http_status": response.status_code,
                "response": response_data,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print(f"Resultado salvo em: {result_file}")

    if not response.ok:
        print("RESULTADO: FALHA NA FINALIZAÇÃO")
        return 7

    print(
        "RESULTADO: CATEGORIA FINALIZADA "
        "COM SUCESSO"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
