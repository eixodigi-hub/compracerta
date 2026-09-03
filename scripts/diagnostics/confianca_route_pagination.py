#!/usr/bin/env python3

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Set
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import Request, sync_playwright


HOST = "https://www.confianca.com.br"
SORT = "product.analytics.factorQuantitySold30d|1"
PAGE_SIZE = 60

CATEGORY_KEY = "matinais"
CATEGORY_PATH = "/c/matinais/s_matinais"
CATALOG_ROUTE_ID = "s_matinais"

STATE_FILE = Path(
    ".collector_state/confianca/browser_state.json"
)

LOG_DIR = Path("logs")


def extract_numeric_values(value: Any) -> List[str]:
    found: List[str] = []

    if isinstance(value, int):
        found.append(str(value))

    elif isinstance(value, str):
        found.extend(
            re.findall(
                r"\b\d{5,12}\b",
                value,
            )
        )

    elif isinstance(value, list):
        for item in value:
            found.extend(
                extract_numeric_values(item)
            )

    return found


def extract_product_ids(data: Any) -> List[str]:
    if not isinstance(data, dict):
        return []

    results = data.get("results", {})

    if not isinstance(results, dict):
        return []

    records = results.get("records", [])

    if not isinstance(records, list):
        return []

    product_ids: List[str] = []
    seen: Set[str] = set()

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                key_lower = key.lower().replace(
                    "_",
                    "",
                )

                is_product_field = (
                    "product.repositoryid"
                    in key.lower()
                    or key_lower.endswith("productid")
                    or key_lower == "repositoryid"
                )

                if is_product_field:
                    candidates = extract_numeric_values(
                        nested
                    )

                    for candidate in candidates:
                        if candidate in seen:
                            continue

                        seen.add(candidate)
                        product_ids.append(candidate)

                walk(nested)

        elif isinstance(value, list):
            for nested in value:
                walk(nested)

    for record in records:
        walk(record)

    return product_ids


def replay_headers(
    captured: Dict[str, str],
    referer: str,
) -> Dict[str, str]:
    headers: Dict[str, str] = {}

    for key, value in captured.items():
        key_lower = key.lower()

        if key_lower.startswith("x-"):
            headers[key] = value

        elif key_lower in {
            "accept",
            "accept-language",
            "content-type",
        }:
            headers[key] = value

    headers["Accept"] = "application/json"
    headers["Referer"] = referer

    return headers


def main() -> int:
    if not STATE_FILE.exists():
        print(
            "ERRO: browser_state.json não encontrado."
        )
        return 2

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    LOG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_file = LOG_DIR / (
        f"confianca_route_pagination_"
        f"{timestamp}.json"
    )

    encoded_sort = SORT.replace(
        "|",
        "%7C",
    )

    category_url = (
        f"{HOST}/marilia"
        f"{CATEGORY_PATH}"
        f"?Ns={encoded_sort}"
    )

    captured_products_url = None
    captured_headers: Dict[str, str] = {}

    print("=" * 72)
    print("PAGINAÇÃO PELO ROUTE ID — MATINAIS")
    print("=" * 72)
    print(f"Route ID: {CATALOG_ROUTE_ID}")
    print("Nenhum dado será enviado ao banco.")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
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

        def handle_request(
            request: Request,
        ) -> None:
            nonlocal captured_products_url
            nonlocal captured_headers

            if (
                "/ccstore/v1/products?"
                not in request.url
            ):
                return

            if "productIds=" not in request.url:
                return

            if captured_products_url is not None:
                return

            captured_products_url = request.url
            captured_headers = (
                request.all_headers()
            )

        page.on("request", handle_request)

        print(f"Abrindo: {category_url}")

        page.goto(
            category_url,
            wait_until="domcontentloaded",
            timeout=90_000,
        )

        page.wait_for_timeout(20_000)

        if (
            captured_products_url is None
            or not captured_headers
        ):
            browser.close()

            print(
                "ERRO: contexto da loja "
                "não foi capturado."
            )
            return 3

        headers = replay_headers(
            captured_headers,
            category_url,
        )

        all_product_ids: List[str] = []
        seen_ids: Set[str] = set()
        pages = []

        expected_total = None
        offset = 0
        page_number = 0

        while page_number < 50:
            page_number += 1

            catalog_url = (
                f"{HOST}/ccstore/v1/"
                f"assembler/pages/Default/"
                f"osf/catalog/_/"
                f"{CATALOG_ROUTE_ID}"
                f"?No={offset}"
                f"&Nrpp={PAGE_SIZE}"
                f"&Ns={encoded_sort}"
            )

            response = context.request.get(
                catalog_url,
                headers=headers,
                timeout=90_000,
            )

            if not response.ok:
                print(
                    f"Página {page_number}: "
                    f"HTTP {response.status}"
                )
                break

            data = response.json()
            results = data.get("results", {})

            if not isinstance(results, dict):
                results = {}

            raw_total = results.get(
                "totalNumRecs"
            )

            if (
                expected_total is None
                and isinstance(raw_total, int)
            ):
                expected_total = raw_total

            page_ids = extract_product_ids(data)

            new_ids = []

            for product_id in page_ids:
                if product_id in seen_ids:
                    continue

                seen_ids.add(product_id)
                all_product_ids.append(product_id)
                new_ids.append(product_id)

            pages.append(
                {
                    "page": page_number,
                    "offset": offset,
                    "http_status": response.status,
                    "ids": page_ids,
                    "ids_total": len(page_ids),
                    "new_ids_total": len(new_ids),
                }
            )

            print(
                f"Página {page_number}: "
                f"{len(page_ids)} IDs, "
                f"{len(new_ids)} novos, "
                f"offset {offset}, "
                f"total acumulado "
                f"{len(all_product_ids)}, "
                f"total esperado "
                f"{expected_total}"
            )

            if not page_ids:
                break

            if not new_ids:
                print(
                    "Paginação repetiu os mesmos IDs."
                )
                break

            if (
                expected_total is not None
                and len(all_product_ids)
                >= expected_total
            ):
                break

            if len(page_ids) < PAGE_SIZE:
                break

            offset += PAGE_SIZE

        browser.close()

    result = {
        "category": CATEGORY_KEY,
        "route_id": CATALOG_ROUTE_ID,
        "expected_total": expected_total,
        "collected_unique_ids": len(
            all_product_ids
        ),
        "pages": pages,
        "product_ids": all_product_ids,
    }

    output_file.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print("=" * 72)
    print("RESULTADO")
    print("=" * 72)
    print(
        f"Total informado pelo catálogo: "
        f"{expected_total}"
    )
    print(
        f"IDs únicos coletados: "
        f"{len(all_product_ids)}"
    )
    print(
        f"Páginas consultadas: "
        f"{len(pages)}"
    )
    print(f"Arquivo: {output_file.resolve()}")
    print()
    print(
        "RESULTADO: somente diagnóstico. "
        "Banco não alterado."
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
