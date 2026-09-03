from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import requests


ROOT_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT_DIR / ".env"
LOG_DIR = ROOT_DIR / "logs"

EXPECTED_STORE_ID = (
    "4f97f5d6-6a17-46ab-bf63-b3724abef9ff"
)

BATCH_SIZE = 50
CATEGORY_KEY = "alimentos_basicos"

# Piso de sanidade: o catálogo variou entre ~260 e ~300 itens nas últimas
# coletas. Um total abaixo disso indica coleta quebrada (bloqueio, parse
# errado etc.) e deve continuar travando o envio. Crescimento normal do
# catálogo acima do piso não deve mais travar a coleta diária.
MIN_EXPECTED_TOTAL = 200


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


def latest_preview() -> Path:
    files = list(
        LOG_DIR.glob("confianca_preview_*.json")
    )

    if not files:
        raise SystemExit(
            "ERRO: nenhum arquivo de prévia encontrado."
        )

    return max(
        files,
        key=lambda path: path.stat().st_mtime,
    )


def as_float(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        return float(value)

    return None


def convert_product(
    product: dict[str, Any],
    collected_at: str,
) -> dict[str, Any]:
    regular_price = as_float(
        product.get("regular_price")
    )

    effective_price = as_float(
        product.get("price")
    )

    sale_price = as_float(
        product.get("sale_price")
    )

    promotional = bool(
        product.get("promotional")
    )

    weight = product.get("weight")

    quantity_raw = (
        str(weight).strip()
        if weight is not None
        else None
    )

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
        "quantity_raw": quantity_raw,
        "unit_raw": product.get(
            "unit_of_measurement"
        ),
        "barcode_raw": product.get("barcode"),
        "regular_price": regular_price,
        "promotional_price": (
            sale_price
            if promotional
            and sale_price is not None
            else None
        ),
        "effective_price": effective_price,
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
        "source_category": CATEGORY_KEY,
    }


def validate_preview(
    data: dict[str, Any],
) -> list[str]:
    errors: list[str] = []

    expected_total = data.get("expected_total")
    ids_collected = data.get("ids_collected")
    products_received = data.get("products_received")
    products_normalized = data.get(
        "products_normalized"
    )

    products = data.get("products", [])
    skipped = data.get("skipped", {})

    if (
        not isinstance(expected_total, int)
        or expected_total < MIN_EXPECTED_TOTAL
    ):
        errors.append(
            f"expected_total abaixo do piso de sanidade "
            f"({MIN_EXPECTED_TOTAL}): {expected_total}"
        )

    if ids_collected != expected_total:
        errors.append(
            "ids_collected diferente de expected_total"
        )

    if products_received != expected_total:
        errors.append(
            "products_received diferente de expected_total"
        )

    if products_normalized != expected_total:
        errors.append(
            "products_normalized diferente de expected_total"
        )

    if not isinstance(products, list):
        errors.append("campo products inválido")
    elif len(products) != expected_total:
        errors.append(
            f"quantidade no array products: {len(products)}"
        )

    if isinstance(skipped, dict):
        skipped_total = sum(
            value
            for value in skipped.values()
            if isinstance(value, int)
        )

        if skipped_total != 0:
            errors.append(
                f"produtos ignorados: {skipped}"
            )
    else:
        errors.append("campo skipped inválido")

    ids: list[str] = []

    if isinstance(products, list):
        for index, product in enumerate(
            products,
            start=1,
        ):
            if not isinstance(product, dict):
                errors.append(
                    f"produto {index} não é objeto"
                )
                continue

            external_id = str(
                product.get("external_id", "")
            ).strip()

            name = str(
                product.get("name", "")
            ).strip()

            price = product.get("price")

            if not external_id:
                errors.append(
                    f"produto {index} sem external_id"
                )
            else:
                ids.append(external_id)

            if not name:
                errors.append(
                    f"produto {external_id} sem nome"
                )

            if (
                not isinstance(price, (int, float))
                or isinstance(price, bool)
                or price <= 0
            ):
                errors.append(
                    f"produto {external_id} "
                    f"com preço inválido: {price}"
                )

            if (
                product.get("source_category")
                != CATEGORY_KEY
            ):
                errors.append(
                    f"produto {external_id} "
                    "com categoria incorreta"
                )

    if len(ids) != len(set(ids)):
        errors.append("external_id duplicado")

    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Ingestão completa do Confiança "
            "sem finalizar categoria."
        )
    )

    parser.add_argument(
        "--enviar",
        action="store_true",
        help="Realiza o envio dos produtos.",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_env()

    store_id = os.environ.get(
        "CONFIANCA_STORE_ID",
        "",
    ).strip()

    ingest_url = os.environ.get(
        "INGEST_URL",
        "",
    ).strip()

    secret = os.environ.get(
        "INGEST_SECRET",
        "",
    ).strip()

    if store_id != EXPECTED_STORE_ID:
        print(
            "ERRO: CONFIANCA_STORE_ID incorreto."
        )
        print(f"Encontrado: {store_id}")
        return 2

    preview_file = latest_preview()

    data = json.loads(
        preview_file.read_text(
            encoding="utf-8",
        )
    )

    errors = validate_preview(data)

    print("=" * 60)
    print("INGESTÃO COMPLETA DO CONFIANÇA")
    print("=" * 60)
    print(f"Arquivo: {preview_file}")
    print(f"Store ID: {store_id}")
    print(
        f"Produtos: "
        f"{data.get('products_normalized')}"
    )
    print("Finalização de categoria: DESATIVADA")
    print()

    if errors:
        print("ERROS DE VALIDAÇÃO:")

        for error in errors[:50]:
            print(f"- {error}")

        print()
        print("RESULTADO: ENVIO BLOQUEADO")
        return 3

    original_products = data["products"]

    collected_at = (
        datetime.now()
        .astimezone()
        .isoformat()
    )

    products = [
        convert_product(
            product,
            collected_at,
        )
        for product in original_products
    ]

    print("Prévia validada com sucesso.")
    print(
        f"Lotes previstos: "
        f"{(len(products) + BATCH_SIZE - 1) // BATCH_SIZE}"
    )

    if not args.enviar:
        print()
        print("Nenhum produto foi enviado.")
        print(
            "Execute novamente com --enviar."
        )
        return 0

    if not ingest_url or not secret:
        print(
            "ERRO: INGEST_URL ou "
            "INGEST_SECRET não configurado."
        )
        return 4

    responses: list[dict[str, Any]] = []
    sent = 0
    failures = 0

    for start in range(
        0,
        len(products),
        BATCH_SIZE,
    ):
        batch = products[
            start:start + BATCH_SIZE
        ]

        batch_number = (
            start // BATCH_SIZE
        ) + 1

        payload = {
            "store_id": store_id,
            "products": batch,
        }

        print()
        print(
            f"Enviando lote {batch_number} "
            f"com {len(batch)} produtos..."
        )

        try:
            response = requests.post(
                ingest_url,
                headers={
                    "x-ingest-secret": secret,
                    "content-type": (
                        "application/json"
                    ),
                },
                json=payload,
                timeout=120,
            )
        except requests.RequestException as error:
            print(
                f"FALHA de conexão no lote "
                f"{batch_number}: {error}"
            )

            failures += 1

            responses.append(
                {
                    "batch": batch_number,
                    "products": len(batch),
                    "error": str(error),
                }
            )

            continue

        try:
            response_data: Any = response.json()
        except ValueError:
            response_data = {
                "raw_response": (
                    response.text[:3000]
                ),
            }

        print(f"HTTP: {response.status_code}")
        print(
            json.dumps(
                response_data,
                ensure_ascii=False,
                indent=2,
            )
        )

        responses.append(
            {
                "batch": batch_number,
                "products": len(batch),
                "http_status": (
                    response.status_code
                ),
                "response": response_data,
            }
        )

        if response.ok:
            sent += len(batch)
        else:
            failures += 1

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    result_file = (
        LOG_DIR
        / f"confianca_full_ingest_{timestamp}.json"
    )

    result_file.write_text(
        json.dumps(
            {
                "sent_at": collected_at,
                "store_id": store_id,
                "preview_file": str(preview_file),
                "products_expected": len(products),
                "products_sent": sent,
                "batch_failures": failures,
                "category_finalized": False,
                "responses": responses,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print("=" * 60)
    print("RESUMO DA INGESTÃO")
    print("=" * 60)
    print(f"Produtos previstos: {len(products)}")
    print(f"Produtos enviados: {sent}")
    print(f"Lotes com falha: {failures}")
    print("Categoria finalizada: NÃO")
    print(f"Resultado salvo em: {result_file}")

    if failures:
        print()
        print(
            "RESULTADO: HOUVE FALHA. "
            "NÃO FINALIZE A CATEGORIA."
        )
        return 5

    if sent != len(products):
        print()
        print(
            "RESULTADO: QUANTIDADE INCOMPLETA. "
            "NÃO FINALIZE A CATEGORIA."
        )
        return 6

    print()
    print(
        "RESULTADO: TODOS OS PRODUTOS "
        "FORAM ENVIADOS."
    )
    print(
        "Os contadores de ausência ainda "
        "não foram processados."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
