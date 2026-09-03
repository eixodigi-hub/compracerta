#!/usr/bin/env python3

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import Request, Response, sync_playwright


CATEGORY_URL = (
    "https://www.confianca.com.br"
    "/marilia/c/matinais/s_matinais"
    "?Ns=product.analytics.factorQuantitySold30d%7C1"
)

STATE_FILE = Path(
    ".collector_state/confianca/browser_state.json"
)

LOG_DIR = Path("logs")


def extract_product_ids(url: str) -> List[str]:
    parsed = urlparse(url)

    query = parse_qs(
        parsed.query,
        keep_blank_values=True,
    )

    product_ids: List[str] = []

    for raw_value in query.get("productIds", []):
        for product_id in raw_value.split(","):
            product_id = product_id.strip()

            if product_id.isdigit():
                product_ids.append(product_id)

    return product_ids


def contains_id(text: str, product_id: str) -> bool:
    return bool(
        re.search(
            rf"(?<!\d){re.escape(product_id)}(?!\d)",
            text,
        )
    )


def make_snippet(
    text: str,
    product_id: str,
    size: int = 180,
) -> str:
    match = re.search(
        rf"(?<!\d){re.escape(product_id)}(?!\d)",
        text,
    )

    if not match:
        return ""

    start = max(
        0,
        match.start() - size,
    )

    end = min(
        len(text),
        match.end() + size,
    )

    snippet = text[start:end]

    return re.sub(
        r"\s+",
        " ",
        snippet,
    ).strip()


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
        f"confianca_product_source_"
        f"{timestamp}.json"
    )

    captured_products_url = None
    responses: List[Response] = []

    print("=" * 72)
    print("RASTREAMENTO DA ORIGEM DOS PRODUTOS — MATINAIS")
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

        def handle_request(
            request: Request,
        ) -> None:
            nonlocal captured_products_url

            if (
                captured_products_url is None
                and "/ccstore/v1/products?"
                in request.url
                and "productIds="
                in request.url
            ):
                captured_products_url = request.url

        def handle_response(
            response: Response,
        ) -> None:
            resource_type = (
                response.request.resource_type
            )

            if resource_type not in {
                "document",
                "fetch",
                "xhr",
            }:
                return

            responses.append(response)

        page.on("request", handle_request)
        page.on("response", handle_response)

        print(f"Abrindo: {CATEGORY_URL}")

        page.goto(
            CATEGORY_URL,
            wait_until="domcontentloaded",
            timeout=90_000,
        )

        page.wait_for_timeout(20_000)

        if captured_products_url is None:
            browser.close()

            print(
                "ERRO: requisição de produtos "
                "não foi capturada."
            )
            return 3

        visible_product_ids = extract_product_ids(
            captured_products_url
        )

        print(
            "IDs exibidos na primeira carga: "
            f"{len(visible_product_ids)}"
        )

        print(
            "Amostra: "
            f"{visible_product_ids[:10]}"
        )

        matches: List[Dict] = []

        for response in responses:
            url = response.url

            if "/ccstore/v1/products?" in url:
                continue

            if response.status != 200:
                continue

            content_type = (
                response.headers.get(
                    "content-type",
                    "",
                )
                or ""
            ).lower()

            text_like = any(
                value in content_type
                for value in (
                    "json",
                    "text",
                    "html",
                    "javascript",
                )
            )

            if not text_like:
                continue

            try:
                body = response.text()
            except Exception:
                continue

            matched_ids = [
                product_id
                for product_id in visible_product_ids
                if contains_id(body, product_id)
            ]

            if not matched_ids:
                continue

            matches.append(
                {
                    "source": "response",
                    "url": url,
                    "status": response.status,
                    "content_type": content_type,
                    "body_bytes": len(
                        body.encode("utf-8")
                    ),
                    "matched_ids_total": len(
                        matched_ids
                    ),
                    "matched_ids": matched_ids,
                    "snippet": make_snippet(
                        body,
                        matched_ids[0],
                    ),
                }
            )

        try:
            html = page.content()
        except Exception:
            html = ""

        html_matched_ids = [
            product_id
            for product_id in visible_product_ids
            if contains_id(html, product_id)
        ]

        if html_matched_ids:
            matches.append(
                {
                    "source": "page_html",
                    "url": page.url,
                    "status": 200,
                    "content_type": "text/html",
                    "body_bytes": len(
                        html.encode("utf-8")
                    ),
                    "matched_ids_total": len(
                        html_matched_ids
                    ),
                    "matched_ids": html_matched_ids,
                    "snippet": make_snippet(
                        html,
                        html_matched_ids[0],
                    ),
                }
            )

        performance_urls = page.evaluate(
            """
            performance
                .getEntriesByType('resource')
                .map(item => item.name)
            """
        )

        final_url = page.url
        title = page.title()

        browser.close()

    matches.sort(
        key=lambda item: (
            -item["matched_ids_total"],
            item["url"],
        )
    )

    result = {
        "category": "matinais",
        "category_url": CATEGORY_URL,
        "final_url": final_url,
        "title": title,
        "captured_products_url": (
            captured_products_url
        ),
        "visible_product_ids_total": len(
            visible_product_ids
        ),
        "visible_product_ids": visible_product_ids,
        "matching_sources": matches,
        "performance_urls": performance_urls,
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
    print("FONTES QUE CONTÊM OS IDS DOS PRODUTOS")
    print("=" * 72)
    print(f"Total de fontes: {len(matches)}")

    for index, item in enumerate(
        matches,
        start=1,
    ):
        print()
        print(
            f"{index:03d}. "
            f"{item['matched_ids_total']} IDs encontrados"
        )
        print(
            f"Origem: {item['source']}"
        )
        print(
            f"HTTP: {item['status']}"
        )
        print(
            f"Tipo: {item['content_type']}"
        )
        print(
            f"URL: {item['url']}"
        )
        print(
            f"Amostra de IDs: "
            f"{item['matched_ids'][:10]}"
        )
        print(
            f"Trecho: {item['snippet']}"
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
