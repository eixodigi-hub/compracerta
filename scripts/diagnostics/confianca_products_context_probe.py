from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from playwright.sync_api import Request, sync_playwright


ROOT_DIR = Path(__file__).resolve().parents[2]

STATE_FILE = (
    ROOT_DIR
    / ".collector_state"
    / "confianca"
    / "browser_state.json"
)

OUTPUT_DIR = (
    ROOT_DIR
    / "logs"
    / f"confianca_products_context_{datetime.now():%Y%m%d_%H%M%S}"
)

BASE_URL = os.environ.get(
    "CONFIANCA_BASE_URL",
    "https://www.confianca.com.br/marilia",
).rstrip("/")

CATEGORY_URL = (
    f"{BASE_URL}/c/alimentos-basicos/g_alimentos_basicos"
    "?Ns=product.analytics.factorQuantitySold30d%7C1"
)

PRODUCTS_FRAGMENT = "/ccstore/v1/products?"

CATALOG_URL = (
    "https://www.confianca.com.br"
    "/ccstore/v1/assembler/pages/Default/osf/catalog/_/"
    "N-776784396"
    "?No=0"
    "&Nrpp=60"
    "&Ns=product.analytics.factorQuantitySold30d%7C1"
)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def save_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def replay_headers(
    captured: dict[str, str],
) -> dict[str, str]:
    result: dict[str, str] = {}

    allowed = {
        "accept",
        "accept-language",
        "content-type",
    }

    for key, value in captured.items():
        lower = key.lower()

        if lower.startswith("x-") or lower in allowed:
            result[key] = value

    result["Accept"] = "application/json"
    result["Referer"] = CATEGORY_URL

    return result


def product_summary(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {
            "root_type": type(data).__name__,
            "items": 0,
        }

    items = data.get("items", [])

    if not isinstance(items, list):
        items = []

    first_product = None

    if items and isinstance(items[0], dict):
        product = items[0]
        child_skus = product.get("childSKUs") or []

        sku = (
            child_skus[0]
            if isinstance(child_skus, list)
            and child_skus
            and isinstance(child_skus[0], dict)
            else {}
        )

        first_product = {
            "id": product.get("id"),
            "displayName": product.get("displayName"),
            "barcode": sku.get("barcode"),
            "listPrice": sku.get("listPrice"),
            "salePrice": sku.get("salePrice"),
            "activeEsmeralda": (
                sku.get("x_activeConfiancaEsmeralda")
            ),
        }

    return {
        "items": len(items),
        "first_product": first_product,
    }


def catalog_summary(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {
            "root_type": type(data).__name__,
        }

    results = data.get("results", {})

    if not isinstance(results, dict):
        results = {}

    records = results.get("records", [])

    if not isinstance(records, list):
        records = []

    return {
        "total_records": results.get("totalNumRecs"),
        "records_per_page": results.get("recsPerPage"),
        "records_received": len(records),
        "paging_template": (
            results.get("pagingActionTemplate", {}).get("link")
            if isinstance(
                results.get("pagingActionTemplate"),
                dict,
            )
            else None
        ),
    }


def main() -> int:
    if not STATE_FILE.exists():
        print("ERRO: sessão do Confiança não encontrada.")
        print(f"Esperado em: {STATE_FILE}")
        return 1

    captured_url: str | None = None
    captured_headers: dict[str, str] = {}

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

        def handle_request(request: Request) -> None:
            nonlocal captured_url
            nonlocal captured_headers

            if PRODUCTS_FRAGMENT not in request.url:
                return

            if "productIds=" not in request.url:
                return

            if captured_url is not None:
                return

            captured_url = request.url
            captured_headers = request.all_headers()

        page.on("request", handle_request)

        print("Abrindo a categoria de Marília...")

        page.goto(
            CATEGORY_URL,
            wait_until="domcontentloaded",
            timeout=90_000,
        )

        page.wait_for_timeout(20_000)

        if captured_url is None:
            print("Rolando a página para carregar produtos...")

            page.evaluate(
                """
                window.scrollTo({
                    top: document.body.scrollHeight,
                    behavior: "instant"
                })
                """
            )

            page.wait_for_timeout(10_000)

        if captured_url is None:
            print("Recarregando a categoria...")

            page.reload(
                wait_until="domcontentloaded",
                timeout=90_000,
            )

            page.wait_for_timeout(20_000)

        products_status = None
        products_result = None
        catalog_status = None
        catalog_result = None
        replay_error = None

        if captured_url and captured_headers:
            save_json(
                OUTPUT_DIR / "request_headers_private.json",
                captured_headers,
            )

            headers = replay_headers(captured_headers)

            try:
                print("Repetindo a consulta de produtos...")

                products_response = context.request.get(
                    captured_url,
                    headers=headers,
                    timeout=90_000,
                )

                products_status = products_response.status

                if products_response.ok:
                    products_data = products_response.json()

                    save_json(
                        OUTPUT_DIR / "products_replay.json",
                        products_data,
                    )

                    products_result = product_summary(
                        products_data
                    )

                print("Testando o catálogo com o mesmo contexto...")

                catalog_response = context.request.get(
                    CATALOG_URL,
                    headers=headers,
                    timeout=90_000,
                )

                catalog_status = catalog_response.status

                if catalog_response.ok:
                    catalog_data = catalog_response.json()

                    save_json(
                        OUTPUT_DIR / "catalog_replay.json",
                        catalog_data,
                    )

                    catalog_result = catalog_summary(
                        catalog_data
                    )

            except Exception as error:
                replay_error = str(error)

        custom_header_names = sorted(
            key
            for key in captured_headers
            if key.lower().startswith("x-")
        )

        summary = {
            "category_url": CATEGORY_URL,
            "final_page_url": page.url,
            "products_request_captured": (
                captured_url is not None
            ),
            "captured_products_url": captured_url,
            "custom_header_names": custom_header_names,
            "products_replay_status": products_status,
            "products_replay": products_result,
            "catalog_replay_status": catalog_status,
            "catalog_replay": catalog_result,
            "replay_error": replay_error,
        }

        save_json(
            OUTPUT_DIR / "summary.json",
            summary,
        )

        page.screenshot(
            path=str(OUTPUT_DIR / "page.png"),
            full_page=True,
        )

        browser.close()

    print()
    print("=" * 60)
    print("RESULTADO")
    print("=" * 60)
    print(f"URL final: {summary['final_page_url']}")
    print(
        "Requisição de produtos capturada: "
        f"{summary['products_request_captured']}"
    )
    print(
        "Cabeçalhos personalizados: "
        f"{summary['custom_header_names']}"
    )
    print()
    print(
        "Repetição dos produtos, HTTP: "
        f"{products_status}"
    )
    print(
        json.dumps(
            products_result,
            ensure_ascii=False,
            indent=2,
        )
    )
    print()
    print(
        "Repetição do catálogo, HTTP: "
        f"{catalog_status}"
    )
    print(
        json.dumps(
            catalog_result,
            ensure_ascii=False,
            indent=2,
        )
    )

    if replay_error:
        print()
        print(f"Erro: {replay_error}")

    print()
    print(
        "Resumo salvo em: "
        f"{OUTPUT_DIR / 'summary.json'}"
    )
    print(
        "Não compartilhe request_headers_private.json "
        "nem browser_state.json."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
