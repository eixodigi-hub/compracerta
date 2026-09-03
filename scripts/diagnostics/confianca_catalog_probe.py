from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright


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
    / f"confianca_catalog_probe_{datetime.now():%Y%m%d_%H%M%S}"
)

BASE_URL = os.environ.get(
    "CONFIANCA_BASE_URL",
    "https://www.confianca.com.br/marilia",
).rstrip("/")

CATEGORY_URL = (
    f"{BASE_URL}/c/alimentos-basicos/g_alimentos_basicos"
    "?Ns=product.analytics.factorQuantitySold30d%7C1"
)

CATALOG_URL = (
    "https://www.confianca.com.br"
    "/ccstore/v1/assembler/pages/Default/osf/catalog/_/"
    "N-776784396"
    "?Ns=product.analytics.factorQuantitySold30d%7C1"
)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def compact(value: Any, limit: int = 2000) -> str:
    text = json.dumps(
        value,
        ensure_ascii=False,
        indent=2,
    )

    if len(text) > limit:
        return text[:limit] + "\n... reduzido ..."

    return text


def find_pagination(
    value: Any,
    path: str = "",
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    terms = (
        "total",
        "count",
        "offset",
        "limit",
        "page",
        "start",
        "end",
        "record",
        "navigation",
        "link",
    )

    if isinstance(value, dict):
        for key, nested in value.items():
            current_path = f"{path}.{key}" if path else key

            if any(term in key.lower() for term in terms):
                if isinstance(
                    nested,
                    (str, int, float, bool, type(None)),
                ):
                    results.append(
                        {
                            "path": current_path,
                            "value": nested,
                        }
                    )

            results.extend(
                find_pagination(
                    nested,
                    current_path,
                )
            )

    elif isinstance(value, list):
        for index, nested in enumerate(value[:100]):
            results.extend(
                find_pagination(
                    nested,
                    f"{path}[{index}]",
                )
            )

    return results


def find_product_ids(value: Any) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()

    def walk(item: Any) -> None:
        if isinstance(item, dict):
            for key, nested in item.items():
                key_lower = key.lower()

                if key_lower in {
                    "productid",
                    "product_id",
                    "repositoryid",
                }:
                    if isinstance(nested, (str, int)):
                        product_id = str(nested)

                        if (
                            product_id.isdigit()
                            and product_id not in seen
                        ):
                            seen.add(product_id)
                            ids.append(product_id)

                walk(nested)

        elif isinstance(item, list):
            for nested in item:
                walk(nested)

    walk(value)
    return ids


def main() -> int:
    if not STATE_FILE.exists():
        print("ERRO: browser_state.json não encontrado.")
        return 1

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=False,
        )

        context = browser.new_context(
            storage_state=str(STATE_FILE),
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
        )

        page = context.new_page()

        print("Abrindo categoria de Marília...")

        page.goto(
            CATEGORY_URL,
            wait_until="domcontentloaded",
            timeout=90_000,
        )

        page.wait_for_timeout(5_000)

        print("Consultando endpoint do catálogo...")

        response = context.request.get(
            CATALOG_URL,
            headers={
                "Accept": "application/json",
                "Referer": CATEGORY_URL,
            },
            timeout=90_000,
        )

        print(f"HTTP: {response.status}")

        if not response.ok:
            print(response.text()[:2000])
            browser.close()
            return 1

        data = response.json()

        raw_file = OUTPUT_DIR / "catalog.json"
        raw_file.write_text(
            json.dumps(
                data,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        product_ids = find_product_ids(data)
        pagination = find_pagination(data)

        summary = {
            "http_status": response.status,
            "category_url": CATEGORY_URL,
            "catalog_url": CATALOG_URL,
            "root_type": type(data).__name__,
            "root_keys": (
                list(data.keys())
                if isinstance(data, dict)
                else []
            ),
            "product_ids_detected": len(product_ids),
            "first_product_ids": product_ids[:20],
            "pagination_candidates": pagination[:100],
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

        browser.close()

    print()
    print("=" * 60)
    print("RESULTADO")
    print("=" * 60)
    print(f"IDs de produtos detectados: {len(product_ids)}")
    print(f"Primeiros IDs: {product_ids[:20]}")
    print()
    print("Possíveis campos de paginação:")
    print(compact(pagination[:40], limit=8000))
    print()
    print(f"Resumo salvo em: {summary_file}")
    print(f"Resposta completa salva em: {raw_file}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
