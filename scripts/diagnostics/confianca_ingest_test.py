from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import requests


ROOT_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT_DIR / ".env"
LOG_DIR = ROOT_DIR / "logs"

EXPECTED_STORE_ID = (
    "744b59fb-1bf9-4235-a900-fcea7fd1cfec"
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


def latest_preview() -> Path:
    files = list(
        LOG_DIR.glob("confianca_preview_*.json")
    )

    if not files:
        raise SystemExit(
            "ERRO: nenhum arquivo "
            "confianca_preview_*.json encontrado."
        )

    return max(
        files,
        key=lambda path: path.stat().st_mtime,
    )


def as_float(value: Any) -> float | None:
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

    promotional_price = (
        sale_price
        if promotional
        and sale_price is not None
        else None
    )

    quantity = product.get("weight")

    quantity_raw = (
        str(quantity).strip()
        if quantity is not None
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
        "promotional_price": promotional_price,
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
        "source_category": product.get(
            "source_category"
        ),
    }


def validate_product(
    product: dict[str, Any],
) -> list[str]:
    errors: list[str] = []

    if not product["external_id"]:
        errors.append("external_id ausente")

    if not product["external_name"]:
        errors.append("external_name ausente")

    effective_price = product.get(
        "effective_price"
    )

    regular_price = product.get(
        "regular_price"
    )

    if (
        not isinstance(
            effective_price,
            (int, float),
        )
        or effective_price <= 0
    ):
        errors.append(
            f"effective_price inválido: "
            f"{effective_price}"
        )

    if (
        not isinstance(
            regular_price,
            (int, float),
        )
        or regular_price <= 0
    ):
        errors.append(
            f"regular_price inválido: "
            f"{regular_price}"
        )

    if (
        product.get("source_category")
        != "alimentos_basicos"
    ):
        errors.append(
            "source_category incorreta"
        )

    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Teste seguro de ingestão "
            "do Confiança Marília."
        )
    )

    parser.add_argument(
        "--produtos",
        type=int,
        default=5,
        help="Quantidade a testar. Máximo: 20.",
    )

    parser.add_argument(
        "--enviar",
        action="store_true",
        help=(
            "Realiza o envio. Sem esta opção, "
            "apenas mostra a prévia."
        ),
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_env()

    if args.produtos < 1 or args.produtos > 20:
        print(
            "ERRO: --produtos deve estar "
            "entre 1 e 20."
        )
        return 2

    store_id = os.environ.get(
        "CONFIANCA_STORE_ID",
        "",
    ).strip()

    if store_id != EXPECTED_STORE_ID:
        print(
            "ERRO: CONFIANCA_STORE_ID "
            "não corresponde à loja esperada."
        )
        print(f"Valor encontrado: {store_id}")
        return 2

    preview_file = latest_preview()

    data = json.loads(
        preview_file.read_text(
            encoding="utf-8",
        )
    )

    original_products = data.get(
        "products",
        [],
    )

    if not isinstance(
        original_products,
        list,
    ):
        print(
            "ERRO: campo products inválido "
            "no arquivo de prévia."
        )
        return 2

    selected = original_products[
        :args.produtos
    ]

    if len(selected) != args.produtos:
        print(
            "ERRO: o arquivo não possui "
            "produtos suficientes."
        )
        return 2

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
        for product in selected
        if isinstance(product, dict)
    ]

    validation_errors: list[str] = []

    for index, product in enumerate(
        products,
        start=1,
    ):
        errors = validate_product(product)

        for error in errors:
            validation_errors.append(
                f"Produto {index} "
                f"({product.get('external_id')}): "
                f"{error}"
            )

    print("=" * 60)
    print("TESTE DE INGESTÃO DO CONFIANÇA")
    print("=" * 60)
    print(f"Arquivo: {preview_file}")
    print(f"Store ID: {store_id}")
    print(f"Produtos selecionados: {len(products)}")
    print("Finalização de categoria: DESATIVADA")
    print()

    for product in products:
        print(
            f"{product['external_id']} | "
            f"{product['external_name']} | "
            f"R$ {product['effective_price']:.2f} | "
            f"disponível={product['available']}"
        )

    if validation_errors:
        print()
        print("ERROS DE VALIDAÇÃO:")

        for error in validation_errors:
            print(f"- {error}")

        return 3

    payload = {
        "store_id": store_id,
        "products": products,
    }

    if not args.enviar:
        print()
        print(
            "PRÉVIA APROVADA. "
            "Nenhum dado foi enviado."
        )
        print(
            "Use --enviar para realizar "
            "o teste real."
        )
        return 0

    ingest_url = os.environ.get(
        "INGEST_URL",
        "",
    ).strip()

    secret = os.environ.get(
        "INGEST_SECRET",
        "",
    ).strip()

    if not ingest_url or not secret:
        print(
            "ERRO: INGEST_URL ou "
            "INGEST_SECRET não configurado."
        )
        return 4

    print()
    print("Enviando lote limitado...")

    try:
        response = requests.post(
            ingest_url,
            headers={
                "x-ingest-secret": secret,
                "content-type": "application/json",
            },
            json=payload,
            timeout=120,
        )
    except requests.RequestException as error:
        print(f"ERRO na conexão: {error}")
        return 5

    print(f"HTTP: {response.status_code}")

    try:
        response_data: Any = response.json()
    except ValueError:
        response_data = {
            "raw_response": response.text[:3000],
        }

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
        / f"confianca_ingest_test_{timestamp}.json"
    )

    result_file.write_text(
        json.dumps(
            {
                "sent_at": collected_at,
                "store_id": store_id,
                "products_sent": len(products),
                "http_status": response.status_code,
                "response": response_data,
                "category_finalized": False,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print(f"Resultado salvo em: {result_file}")
    print("Categoria não finalizada.")

    if not response.ok:
        print("RESULTADO: FALHA NA INGESTÃO")
        return 6

    print("RESULTADO: INGESTÃO CONCLUÍDA")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
