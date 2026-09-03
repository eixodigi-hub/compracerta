#!/usr/bin/env python3

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import Request, sync_playwright


BASE_URL = (
    "https://www.confianca.com.br"
    "/marilia/c/matinais/s_matinais"
    "?Ns=product.analytics.factorQuantitySold30d%7C1"
)

STATE_FILE = Path(
    ".collector_state/confianca/browser_state.json"
)

LOG_DIR = Path("logs")


def extract_ids_from_products_url(url: str) -> List[str]:
    parsed = urlparse(url)

    query = parse_qs(
        parsed.query,
        keep_blank_values=True,
    )

    results: List[str] = []

    for raw_value in query.get("productIds", []):
        for product_id in raw_value.split(","):
            product_id = product_id.strip()

            if product_id.isdigit():
                results.append(product_id)

    return results


def extract_ids_from_dom(page) -> Set[str]:
    hrefs = page.locator(
        'a[href*="/p/"]'
    ).evaluate_all(
        """
        elements => elements.map(
            element =>
                element.href ||
                element.getAttribute('href') ||
                ''
        )
        """
    )

    ids: Set[str] = set()

    for href in hrefs:
        match = re.search(
            r"/p/[^/?]+/(\d+)(?:[/?]|$)",
            href,
        )

        if match:
            ids.add(match.group(1))

    return ids


def click_load_more(page) -> bool:
    patterns = (
        "mostrar mais",
        "carregar mais",
        "ver mais",
        "mais produtos",
    )

    buttons = page.locator("button:visible")

    for index in range(buttons.count()):
        button = buttons.nth(index)

        try:
            text = (
                button.inner_text(timeout=1000)
                or ""
            ).strip().lower()
        except Exception:
            continue

        if not any(
            pattern in text
            for pattern in patterns
        ):
            continue

        try:
            button.click(
                force=True,
                timeout=3000,
            )

            print(
                f"Botão acionado: {text}"
            )

            return True

        except Exception:
            continue

    return False


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
        f"confianca_scroll_probe_{timestamp}.json"
    )

    request_product_ids: Set[str] = set()
    request_urls: List[str] = []
    request_batches: List[Dict] = []

    print("=" * 72)
    print("DIAGNÓSTICO DE ROLAGEM — MATINAIS")
    print("=" * 72)
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

        def handle_request(request: Request) -> None:
            if (
                "/ccstore/v1/products?"
                not in request.url
            ):
                return

            if "productIds=" not in request.url:
                return

            product_ids = extract_ids_from_products_url(
                request.url
            )

            if not product_ids:
                return

            request_urls.append(request.url)

            before = len(request_product_ids)

            request_product_ids.update(product_ids)

            new_ids = (
                len(request_product_ids) - before
            )

            request_batches.append(
                {
                    "total_in_request": len(
                        product_ids
                    ),
                    "new_ids": new_ids,
                    "sample": product_ids[:5],
                }
            )

            print(
                "Requisição de produtos: "
                f"{len(product_ids)} IDs, "
                f"{new_ids} novos, "
                f"{len(request_product_ids)} únicos"
            )

        page.on(
            "request",
            handle_request,
        )

        print(f"Abrindo: {BASE_URL}")

        page.goto(
            BASE_URL,
            wait_until="domcontentloaded",
            timeout=90_000,
        )

        page.wait_for_timeout(15_000)

        stable_rounds = 0
        previous_total = len(request_product_ids)

        for round_number in range(1, 21):
            clicked = click_load_more(page)

            page.evaluate(
                """
                window.scrollTo({
                    top: document.body.scrollHeight,
                    behavior: 'instant'
                })
                """
            )

            page.wait_for_timeout(3000)

            current_total = len(request_product_ids)

            dom_ids = extract_ids_from_dom(page)

            print(
                f"Rodada {round_number:02d}: "
                f"{current_total} IDs nas requisições, "
                f"{len(dom_ids)} IDs no DOM, "
                f"altura={page.evaluate('document.body.scrollHeight')}"
            )

            if (
                current_total == previous_total
                and not clicked
            ):
                stable_rounds += 1
            else:
                stable_rounds = 0

            previous_total = current_total

            if stable_rounds >= 4:
                print(
                    "Rolagem estabilizada."
                )
                break

        final_dom_ids = extract_ids_from_dom(page)

        page_title = page.title()
        final_url = page.url

        browser.close()

    combined_ids = (
        request_product_ids
        | final_dom_ids
    )

    result = {
        "category": "matinais",
        "page_title": page_title,
        "final_url": final_url,
        "products_requests": len(
            request_urls
        ),
        "request_batches": request_batches,
        "request_product_ids": sorted(
            request_product_ids
        ),
        "request_product_ids_total": len(
            request_product_ids
        ),
        "dom_product_ids": sorted(
            final_dom_ids
        ),
        "dom_product_ids_total": len(
            final_dom_ids
        ),
        "combined_product_ids": sorted(
            combined_ids
        ),
        "combined_product_ids_total": len(
            combined_ids
        ),
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
        "Requisições de produtos: "
        f"{result['products_requests']}"
    )
    print(
        "IDs únicos nas requisições: "
        f"{result['request_product_ids_total']}"
    )
    print(
        "IDs únicos no DOM: "
        f"{result['dom_product_ids_total']}"
    )
    print(
        "IDs únicos combinados: "
        f"{result['combined_product_ids_total']}"
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
