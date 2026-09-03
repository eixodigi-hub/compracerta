#!/usr/bin/env python3

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set
from urllib.parse import parse_qs, urlencode, urlparse

from playwright.sync_api import Request, sync_playwright


HOST = "https://www.confianca.com.br"
PATH = "/marilia/c/matinais/s_matinais"
SORT = "product.analytics.factorQuantitySold30d|1"

STATE_FILE = Path(
    ".collector_state/confianca/browser_state.json"
)

LOG_DIR = Path("logs")


def extract_product_ids(url: str) -> List[str]:
    query = parse_qs(
        urlparse(url).query,
        keep_blank_values=True,
    )

    found: List[str] = []
    seen: Set[str] = set()

    for raw_value in query.get("productIds", []):
        for product_id in raw_value.split(","):
            product_id = product_id.strip()

            if (
                product_id.isdigit()
                and product_id not in seen
            ):
                seen.add(product_id)
                found.append(product_id)

    return found


def main() -> int:
    if not STATE_FILE.exists():
        print(
            "ERRO: browser_state.json não encontrado."
        )
        return 2

    tests = [
        ("base", {}),
        (
            "No_60",
            {
                "No": 60,
                "Nrpp": 60,
            },
        ),
        (
            "No_120",
            {
                "No": 120,
                "Nrpp": 60,
            },
        ),
        (
            "page_2",
            {
                "page": 2,
            },
        ),
        (
            "page_3",
            {
                "page": 3,
            },
        ),
    ]

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    LOG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_file = LOG_DIR / (
        "confianca_browser_pagination_"
        f"{timestamp}.json"
    )

    print("=" * 72)
    print("PAGINAÇÃO REAL DO NAVEGADOR — MATINAIS")
    print("=" * 72)
    print("Nenhum dado será enviado ao banco.")

    results: List[Dict] = []

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

        for name, extra_params in tests:
            query = {
                "Ns": SORT,
                **extra_params,
            }

            url = (
                f"{HOST}{PATH}?"
                + urlencode(query)
            )

            page = context.new_page()
            batches: List[List[str]] = []

            def handle_request(
                request: Request,
            ) -> None:
                if (
                    "/ccstore/v1/products?"
                    not in request.url
                ):
                    return

                if "productIds=" not in request.url:
                    return

                ids = extract_product_ids(
                    request.url
                )

                if ids:
                    batches.append(ids)

            page.on("request", handle_request)

            print()
            print(f"Abrindo: {name}")
            print(f"URL: {url}")

            try:
                response = page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=90_000,
                )

                page.wait_for_timeout(15_000)

                largest_batch = max(
                    batches,
                    key=len,
                    default=[],
                )

                result = {
                    "name": name,
                    "requested_url": url,
                    "final_url": page.url,
                    "http_status": (
                        response.status
                        if response
                        else None
                    ),
                    "batches_total": len(batches),
                    "batch_sizes": [
                        len(batch)
                        for batch in batches
                    ],
                    "product_ids": largest_batch,
                    "product_ids_total": len(
                        largest_batch
                    ),
                }

                print(
                    "HTTP: "
                    f"{result['http_status']}"
                )

                print(
                    "Lotes capturados: "
                    f"{result['batch_sizes']}"
                )

                print(
                    "Maior lote: "
                    f"{len(largest_batch)} IDs"
                )

                print(
                    "Primeiros IDs: "
                    f"{largest_batch[:5]}"
                )

                print(
                    "Últimos IDs: "
                    f"{largest_batch[-5:]}"
                )

                results.append(result)

            except Exception as error:
                print(f"ERRO: {error}")

                results.append(
                    {
                        "name": name,
                        "requested_url": url,
                        "error": str(error),
                        "product_ids": [],
                        "product_ids_total": 0,
                    }
                )

            page.close()

        browser.close()

    by_name = {
        result["name"]: result
        for result in results
    }

    base_ids = set(
        by_name.get(
            "base",
            {},
        ).get(
            "product_ids",
            [],
        )
    )

    print()
    print("=" * 72)
    print("COMPARAÇÃO DOS 60 PRODUTOS")
    print("=" * 72)

    for result in results:
        ids = set(
            result.get(
                "product_ids",
                [],
            )
        )

        print(
            f"{result['name']}: "
            f"IDs={len(ids)} | "
            f"coincidentes_base="
            f"{len(ids & base_ids)} | "
            f"novos="
            f"{len(ids - base_ids)}"
        )

    no_60 = set(
        by_name.get(
            "No_60",
            {},
        ).get(
            "product_ids",
            [],
        )
    )

    no_120 = set(
        by_name.get(
            "No_120",
            {},
        ).get(
            "product_ids",
            [],
        )
    )

    page_2 = set(
        by_name.get(
            "page_2",
            {},
        ).get(
            "product_ids",
            [],
        )
    )

    page_3 = set(
        by_name.get(
            "page_3",
            {},
        ).get(
            "product_ids",
            [],
        )
    )

    print()
    print(
        "No_60 igual a page_2: "
        f"{bool(no_60) and no_60 == page_2}"
    )

    print(
        "No_120 igual a page_3: "
        f"{bool(no_120) and no_120 == page_3}"
    )

    print(
        "Sobreposição No_60/page_2: "
        f"{len(no_60 & page_2)}"
    )

    print(
        "Sobreposição No_120/page_3: "
        f"{len(no_120 & page_3)}"
    )

    output_file.write_text(
        json.dumps(
            results,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print("=" * 72)
    print("ARQUIVO")
    print("=" * 72)
    print(output_file.resolve())
    print()
    print(
        "RESULTADO: somente diagnóstico. "
        "Banco não alterado."
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
