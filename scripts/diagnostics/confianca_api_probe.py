from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from playwright.sync_api import Response, sync_playwright


ROOT_DIR = Path(__file__).resolve().parents[2]
STATE_FILE = (
    ROOT_DIR
    / ".collector_state"
    / "confianca"
    / "browser_state.json"
)

TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
OUTPUT_DIR = (
    ROOT_DIR
    / "logs"
    / f"confianca_api_probe_{TIMESTAMP}"
)

BASE_URL = os.environ.get(
    "CONFIANCA_BASE_URL",
    "https://www.confianca.com.br/marilia",
).rstrip("/")

CATEGORY_URL = (
    f"{BASE_URL}/c/alimentos-basicos/g_alimentos_basicos"
    "?Ns=product.analytics.factorQuantitySold30d%7C1"
)

TARGETS = {
    "sites": "/ccstore/v1/sites",
    "category_page": (
        "/ccstore/v1/clientApplications/confianca/"
        "page/c/alimentos-basicos/"
    ),
    "catalog": (
        "/ccstore/v1/assembler/pages/Default/osf/catalog/"
    ),
    "products": "/ccstore/v1/products?",
    "stock": "/ccstore/v1/stockStatus?",
}

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

captured: dict[str, list[dict[str, Any]]] = {
    name: []
    for name in TARGETS
}


def safe_filename(label: str, number: int) -> Path:
    return OUTPUT_DIR / f"{label}_{number:02d}.json"


def selected_product_fields(product: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "id",
        "repositoryId",
        "displayName",
        "active",
        "listPrice",
        "salePrice",
        "listPrices",
        "salePrices",
        "route",
        "primaryImageURL",
        "primarySmallImageURL",
        "primarySourceImageURL",
        "x_unitOfMeasurement",
        "x_ProductWeightLiteracy",
        "defaultProductListingSku",
    )

    return {
        key: product.get(key)
        for key in fields
        if key in product
    }


def find_items(data: Any) -> list[Any]:
    if isinstance(data, list):
        return data

    if not isinstance(data, dict):
        return []

    preferred_keys = (
        "items",
        "products",
        "records",
        "results",
        "resultsList",
        "navigation",
    )

    for key in preferred_keys:
        value = data.get(key)

        if isinstance(value, list):
            return value

        if isinstance(value, dict):
            nested = find_items(value)

            if nested:
                return nested

    for value in data.values():
        if isinstance(value, dict):
            nested = find_items(value)

            if nested:
                return nested

    return []


def response_handler(response: Response) -> None:
    url = response.url

    for label, fragment in TARGETS.items():
        if fragment not in url:
            continue

        index = len(captured[label]) + 1
        record: dict[str, Any] = {
            "status": response.status,
            "url": url,
            "content_type": response.headers.get(
                "content-type",
                "",
            ),
        }

        try:
            data = response.json()
            output_file = safe_filename(label, index)

            output_file.write_text(
                json.dumps(
                    data,
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            record["file"] = str(output_file)
            record["root_type"] = type(data).__name__

            if isinstance(data, dict):
                record["root_keys"] = list(data.keys())[:50]

            items = find_items(data)
            record["detected_items"] = len(items)

            if label == "products" and items:
                first = items[0]

                if isinstance(first, dict):
                    record["first_product"] = (
                        selected_product_fields(first)
                    )

            if label == "stock" and items:
                record["first_stock_item"] = items[0]

        except Exception as error:
            record["body_error"] = str(error)

        captured[label].append(record)
        break


def main() -> int:
    if not STATE_FILE.exists():
        print("ERRO: sessão do Confiança não encontrada.")
        print(f"Arquivo esperado: {STATE_FILE}")
        return 1

    print("=" * 60)
    print("Diagnóstico da API do Confiança")
    print("=" * 60)
    print(f"Categoria: {CATEGORY_URL}")
    print("Nenhum produto será enviado ao Lovable.")
    print()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=False,
        )

        context = browser.new_context(
            storage_state=str(STATE_FILE),
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
            viewport={
                "width": 1440,
                "height": 900,
            },
        )

        page = context.new_page()
        page.on("response", response_handler)

        page.goto(
            CATEGORY_URL,
            wait_until="domcontentloaded",
            timeout=90_000,
        )

        page.wait_for_timeout(20_000)

        final_url = page.url
        page_title = page.title()

        summary = {
            "requested_url": CATEGORY_URL,
            "final_url": final_url,
            "page_title": page_title,
            "contains_bauru": bool(
                re.search(
                    r"/bauru(?:/|$)",
                    final_url,
                    re.IGNORECASE,
                )
            ),
            "contains_marilia": bool(
                re.search(
                    r"/marilia(?:/|$)",
                    final_url,
                    re.IGNORECASE,
                )
            ),
            "captured": captured,
        }

        summary_file = OUTPUT_DIR / "summary.json"
        summary_file.write_text(
            json.dumps(
                summary,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        page.screenshot(
            path=str(OUTPUT_DIR / "page.png"),
            full_page=True,
        )

        browser.close()

    print()
    print("=" * 60)
    print("Resultado")
    print("=" * 60)
    print(f"URL solicitada: {CATEGORY_URL}")
    print(f"URL final: {summary['final_url']}")
    print(f"Título: {summary['page_title']}")
    print(f"Permaneceu em Marília: {summary['contains_marilia']}")
    print(f"Redirecionou para Bauru: {summary['contains_bauru']}")
    print()

    for label, responses in captured.items():
        print(f"{label}: {len(responses)} resposta(s)")

        for response in responses:
            print(
                f"  HTTP {response['status']}, "
                f"itens detectados: "
                f"{response.get('detected_items', 0)}"
            )

            if response.get("first_product"):
                print(
                    "  Primeiro produto: "
                    + json.dumps(
                        response["first_product"],
                        ensure_ascii=False,
                    )
                )

    print()
    print(f"Resumo salvo em: {summary_file}")
    print("Não compartilhe browser_state.json.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
