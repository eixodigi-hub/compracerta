from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from playwright.sync_api import Request, Response, sync_playwright


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
    / f"confianca_request_context_{TIMESTAMP}"
)

BASE_URL = os.environ.get(
    "CONFIANCA_BASE_URL",
    "https://www.confianca.com.br/marilia",
).rstrip("/")

CATEGORY_URL = (
    f"{BASE_URL}/c/alimentos-basicos/g_alimentos_basicos"
    "?Ns=product.analytics.factorQuantitySold30d%7C1"
)

CATALOG_FRAGMENT = (
    "/ccstore/v1/assembler/pages/Default/osf/catalog/"
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


def collect_product_ids(value: Any) -> list[str]:
    product_ids: list[str] = []
    seen: set[str] = set()

    def add_value(candidate: Any) -> None:
        if isinstance(candidate, list):
            for item in candidate:
                add_value(item)
            return

        if isinstance(candidate, int):
            candidate = str(candidate)

        if not isinstance(candidate, str):
            return

        candidate = candidate.strip()

        if candidate.isdigit() and candidate not in seen:
            seen.add(candidate)
            product_ids.append(candidate)

    def walk(item: Any) -> None:
        if isinstance(item, dict):
            for key, nested in item.items():
                key_lower = key.lower().replace("_", "")

                is_product_id = (
                    key_lower == "productid"
                    or key_lower == "repositoryid"
                    or "product.repositoryid" in key.lower()
                    or "productid" in key_lower
                )

                if is_product_id:
                    add_value(nested)

                walk(nested)

        elif isinstance(item, list):
            for nested in item:
                walk(nested)

    walk(value)
    return product_ids


def catalog_summary(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {
            "root_type": type(data).__name__,
            "total_records": None,
            "records_per_page": None,
            "records_received": None,
            "product_ids_detected": 0,
            "first_product_ids": [],
        }

    results = data.get("results", {})

    if not isinstance(results, dict):
        results = {}

    records = results.get("records", [])

    if not isinstance(records, list):
        records = []

    product_ids = collect_product_ids(data)

    return {
        "root_type": type(data).__name__,
        "total_records": results.get("totalNumRecs"),
        "records_per_page": results.get("recsPerPage"),
        "records_received": len(records),
        "product_ids_detected": len(product_ids),
        "first_product_ids": product_ids[:20],
        "paging_template": (
            results
            .get("pagingActionTemplate", {})
            .get("link")
            if isinstance(
                results.get("pagingActionTemplate"),
                dict,
            )
            else None
        ),
    }


def replay_headers(
    captured_headers: dict[str, str],
) -> dict[str, str]:
    allowed_headers: dict[str, str] = {}

    standard_allowed = {
        "accept",
        "accept-language",
        "content-type",
        "user-agent",
    }

    for key, value in captured_headers.items():
        key_lower = key.lower()

        if key_lower.startswith("x-"):
            allowed_headers[key] = value
            continue

        if key_lower in standard_allowed:
            allowed_headers[key] = value

    allowed_headers["Referer"] = CATEGORY_URL
    allowed_headers["Accept"] = "application/json"

    return allowed_headers


def public_header_summary(
    headers: dict[str, str],
) -> dict[str, Any]:
    safe_values: dict[str, str] = {}

    for key, value in headers.items():
        key_lower = key.lower()

        if key_lower.startswith("x-"):
            safe_values[key] = value

    return {
        "header_names": sorted(headers.keys()),
        "custom_headers": safe_values,
    }


def main() -> int:
    if not STATE_FILE.exists():
        print("ERRO: browser_state.json não encontrado.")
        print(f"Esperado em: {STATE_FILE}")
        return 1

    captured_request_url: str | None = None
    captured_request_headers: dict[str, str] = {}
    captured_response_data: Any = None
    captured_response_status: int | None = None

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=False,
        )

        context = browser.new_context(
            storage_state=str(STATE_FILE),
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
            service_workers="block",
            viewport={
                "width": 1440,
                "height": 900,
            },
        )

        page = context.new_page()

        def handle_request(request: Request) -> None:
            nonlocal captured_request_url
            nonlocal captured_request_headers

            if CATALOG_FRAGMENT not in request.url:
                return

            if captured_request_url is not None:
                return

            captured_request_url = request.url
            captured_request_headers = request.all_headers()

            save_json(
                OUTPUT_DIR / "request_headers_private.json",
                captured_request_headers,
            )

        def handle_response(response: Response) -> None:
            nonlocal captured_response_data
            nonlocal captured_response_status

            if CATALOG_FRAGMENT not in response.url:
                return

            try:
                data = response.json()
            except Exception:
                return

            captured_response_status = response.status
            captured_response_data = data

            save_json(
                OUTPUT_DIR / "catalog_browser_response.json",
                data,
            )

        page.on("request", handle_request)
        page.on("response", handle_response)

        print("Abrindo a categoria de Marília...")

        page.goto(
            CATEGORY_URL,
            wait_until="domcontentloaded",
            timeout=90_000,
        )

        page.wait_for_timeout(15_000)

        page.evaluate(
            """
            window.scrollTo({
                top: document.body.scrollHeight,
                behavior: "instant"
            })
            """
        )

        page.wait_for_timeout(10_000)

        if captured_request_url is None:
            print(
                "A primeira abertura não capturou o catálogo. "
                "Recarregando..."
            )

            page.reload(
                wait_until="domcontentloaded",
                timeout=90_000,
            )

            page.wait_for_timeout(20_000)

        browser_result = (
            catalog_summary(captured_response_data)
            if captured_response_data is not None
            else None
        )

        replay_result: dict[str, Any] | None = None
        replay_status: int | None = None
        replay_error: str | None = None

        if captured_request_url and captured_request_headers:
            headers = replay_headers(
                captured_request_headers
            )

            print("Repetindo a chamada com o contexto capturado...")

            try:
                replay_response = context.request.get(
                    captured_request_url,
                    headers=headers,
                    timeout=90_000,
                )

                replay_status = replay_response.status

                if replay_response.ok:
                    replay_data = replay_response.json()

                    save_json(
                        OUTPUT_DIR / "catalog_replay_response.json",
                        replay_data,
                    )

                    replay_result = catalog_summary(
                        replay_data
                    )
                else:
                    replay_error = (
                        replay_response.text()[:1000]
                    )

            except Exception as error:
                replay_error = str(error)

        summary = {
            "category_url": CATEGORY_URL,
            "final_page_url": page.url,
            "captured_request_url": captured_request_url,
            "captured_response_status": (
                captured_response_status
            ),
            "request_context": (
                public_header_summary(
                    captured_request_headers
                )
                if captured_request_headers
                else None
            ),
            "browser_catalog": browser_result,
            "replay_status": replay_status,
            "replay_catalog": replay_result,
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
        "Requisição do catálogo capturada: "
        f"{captured_request_url is not None}"
    )
    print(
        "Status da resposta do navegador: "
        f"{captured_response_status}"
    )
    print()

    print("Catálogo carregado pelo navegador:")
    print(
        json.dumps(
            browser_result,
            ensure_ascii=False,
            indent=2,
        )
    )

    print()
    print("Catálogo repetido com os cabeçalhos:")
    print(f"HTTP: {replay_status}")
    print(
        json.dumps(
            replay_result,
            ensure_ascii=False,
            indent=2,
        )
    )

    if replay_error:
        print()
        print(f"Erro da repetição: {replay_error}")

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
