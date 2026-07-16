"""
Exemplo de robô de ingestão de produtos.

Uso:
  export INGEST_SECRET="<segredo salvo no backend>"
  export STORE_ID="<uuid do mercado - copie em /admin/mercados>"
  python scripts/ingest-example.py

Substitua a função `coletar_produtos()` pela sua lógica de scraping.
Envie em lotes de até ~500 produtos para respostas rápidas.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

import requests

ENDPOINT = "https://project--0848491c-2052-4001-80d7-0f52822c8772.lovable.app/api/public/ingest-products"


def coletar_produtos() -> list[dict]:
    """Retorne aqui a lista de produtos coletados do site do mercado."""
    agora = datetime.now(timezone.utc).isoformat()
    return [
        {
            "external_id": "SKU-0001",
            "external_name": "Arroz Branco Tio João 5kg",
            "product_url": "https://mercado.example.com/arroz-tio-joao-5kg",
            "image_url": "https://mercado.example.com/img/arroz.jpg",
            "brand_raw": "Tio João",
            "quantity_raw": "5",
            "unit_raw": "kg",
            "barcode_raw": "7891234567890",
            "regular_price": 29.90,
            "promotional_price": 25.90,
            "effective_price": 25.90,
            "promotion_text": "Oferta da semana",
            "promotion_end_at": None,
            "available": True,
            "collected_at": agora,
        },
    ]


def enviar(store_id: str, secret: str, produtos: list[dict]) -> dict:
    resp = requests.post(
        ENDPOINT,
        headers={
            "x-ingest-secret": secret,
            "content-type": "application/json",
        },
        json={"store_id": store_id, "products": produtos},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()


def main() -> int:
    secret = os.environ.get("INGEST_SECRET")
    store_id = os.environ.get("STORE_ID")
    if not secret or not store_id:
        print("Defina INGEST_SECRET e STORE_ID nas variáveis de ambiente.", file=sys.stderr)
        return 1

    produtos = coletar_produtos()
    if not produtos:
        print("Nenhum produto coletado.")
        return 0

    print(f"Enviando {len(produtos)} produto(s)...")
    resultado = enviar(store_id, secret, produtos)
    print("Resposta:", resultado)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
