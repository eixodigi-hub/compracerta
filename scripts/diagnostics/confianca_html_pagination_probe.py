#!/usr/bin/env python3

import hashlib
import html as html_module
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Set
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright


HOST = "https://www.confianca.com.br"

BASE_PATH = (
    "/marilia/c/matinais/s_matinais"
)

SORT = (
    "product.analytics."
    "factorQuantitySold30d|1"
)

STATE_FILE = Path(
    ".collector_state/confianca/browser_state.json"
)

LOG_DIR = Path("logs")


def extract_product_ids_from_value(
    value: Any,
) -> List[str]:
    serialized = json.dumps(
        value,
        ensure_ascii=False,
    )

    patterns = (
        r"/p/[^\"'?#\s]+/(\d+)",
        r"products/(\d+)(?:\.|/|\\)",
    )

    found: List[str] = []
    seen: Set[str] = set()

    for pattern in patterns:
        for product_id in re.findall(
            pattern,
            serialized,
            flags=re.IGNORECASE,
        ):
            if product_id in seen:
                continue

            seen.add(product_id)
            found.append(product_id)

    return found


def find_item_lists(
    value: Any,
    output: List[Any],
) -> None:
    if isinstance(value, dict):
        item_type = value.get("@type")

        is_item_list = (
            item_type == "ItemList"
            or (
                isinstance(item_type, list)
                and "ItemList" in item_type
            )
        )

        if is_item_list:
            output.append(value)

        for nested in value.values():
            find_item_lists(nested, output)

    elif isinstance(value, list):
        for nested in value:
            find_item_lists(nested, output)


def extract_itemlist_product_ids(
    page_html: str,
) -> List[str]:
    scripts = re.findall(
        (
            r"<script[^>]*"
            r"type=[\"']application/ld\+json[\"']"
            r"[^>]*>(.*?)</script>"
        ),
        page_html,
        flags=re.IGNORECASE | re.DOTALL,
    )

    product_ids: List[str] = []
    seen: Set[str] = set()

    for raw_script in scripts:
        decoded = html_module.unescape(
            raw_script
        ).strip()

        if not decoded:
            continue

        try:
            data = json.loads(decoded)
        except json.JSONDecodeError:
            continue

        item_lists: List[Any] = []

        find_item_lists(
            data,
            item_lists,
        )

        for item_list in item_lists:
            ids = extract_product_ids_from_value(
                item_list.get(
                    "itemListElement",
                    [],
                )
            )

            for product_id in ids:
                if product_id in seen:
                    continue

                seen.add(product_id)
                product_ids.append(product_id)

    return product_ids


def extract_html_product_ids(
    page_html: str,
) -> List[str]:
    found: List[str] = []
    seen: Set[str] = set()

    for product_id in re.findall(
        r"/p/[^\"'?#\s]+/(\d+)",
        page_html,
        flags=re.IGNORECASE,
    ):
        if product_id in seen:
            continue

        seen.add(product_id)
        found.append(product_id)

    return found


def main() -> int:
    if not STATE_FILE.exists():
        print(
            "ERRO: browser_state.json "
            "não encontrado."
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
        "confianca_html_pagination_"
        f"{timestamp}.json"
    )

    tests: List[Dict] = [
        {
            "name": "base",
            "params": {},
        },
        {
            "name": "No_60",
            "params": {
                "No": 60,
                "Nrpp": 60,
            },
        },
        {
            "name": "No_120",
            "params": {
                "No": 120,
                "Nrpp": 60,
            },
        },
        {
            "name": "page_2",
            "params": {
                "page": 2,
            },
        },
        {
            "name": "page_3",
            "params": {
                "page": 3,
            },
        },
        {
            "name": "pageNumber_2",
            "params": {
                "pageNumber": 2,
                "pageSize": 60,
            },
        },
        {
            "name": "offset_60",
            "params": {
                "offset": 60,
                "limit": 60,
            },
        },
        {
            "name": "start_60",
            "params": {
                "start": 60,
                "count": 60,
            },
        },
    ]

    print("=" * 72)
    print("PAGINAÇÃO DO HTML — MATINAIS")
    print("=" * 72)
    print(
        "Nenhum dado será enviado ao banco."
    )

    results = []

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

        # Abre a página uma vez para inicializar
        # corretamente cookies e contexto da loja.
        page = context.new_page()

        initial_url = (
            f"{HOST}{BASE_PATH}?"
            + urlencode(
                {
                    "Ns": SORT,
                }
            )
        )

        print(f"Inicializando: {initial_url}")

        page.goto(
            initial_url,
            wait_until="domcontentloaded",
            timeout=90_000,
        )

        page.wait_for_timeout(5000)
        page.close()

        for test in tests:
            query = {
                "Ns": SORT,
                **test["params"],
            }

            url = (
                f"{HOST}{BASE_PATH}?"
                + urlencode(query)
            )

            print()
            print(f"Consultando: {test['name']}")
            print(f"URL: {url}")

            try:
                response = context.request.get(
                    url,
                    headers={
                        "Accept": "text/html",
                        "Referer": initial_url,
                    },
                    timeout=90_000,
                )

                body = response.text()

                itemlist_ids = (
                    extract_itemlist_product_ids(
                        body
                    )
                )

                html_ids = extract_html_product_ids(
                    body
                )

                result = {
                    "name": test["name"],
                    "url": url,
                    "status": response.status,
                    "bytes": len(
                        body.encode("utf-8")
                    ),
                    "sha256": hashlib.sha256(
                        body.encode("utf-8")
                    ).hexdigest(),
                    "itemlist_ids": itemlist_ids,
                    "itemlist_ids_total": len(
                        itemlist_ids
                    ),
                    "html_ids": html_ids,
                    "html_ids_total": len(
                        html_ids
                    ),
                }

                results.append(result)

                print(
                    f"HTTP: {response.status}"
                )

                print(
                    "IDs no ItemList: "
                    f"{len(itemlist_ids)}"
                )

                print(
                    "Primeiros IDs: "
                    f"{itemlist_ids[:5]}"
                )

                print(
                    "Últimos IDs: "
                    f"{itemlist_ids[-5:]}"
                )

            except Exception as error:
                print(f"ERRO: {error}")

                results.append(
                    {
                        "name": test["name"],
                        "url": url,
                        "error": str(error),
                    }
                )

        browser.close()

    base_result = next(
        (
            item
            for item in results
            if item.get("name") == "base"
        ),
        {},
    )

    base_ids = set(
        base_result.get(
            "itemlist_ids",
            [],
        )
    )

    print()
    print("=" * 72)
    print("COMPARAÇÃO COM A PRIMEIRA PÁGINA")
    print("=" * 72)

    for result in results:
        ids = set(
            result.get(
                "itemlist_ids",
                [],
            )
        )

        overlap = len(
            ids & base_ids
        )

        new_ids = len(
            ids - base_ids
        )

        identical = (
            ids == base_ids
            and bool(ids)
        )

        print(
            f"{result.get('name')}: "
            f"HTTP={result.get('status')} | "
            f"IDs={len(ids)} | "
            f"coincidentes={overlap} | "
            f"novos={new_ids} | "
            f"idêntica={identical}"
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
