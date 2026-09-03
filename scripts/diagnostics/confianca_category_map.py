#!/usr/bin/env python3

import csv
import html
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict
from urllib.parse import urljoin, urlparse

from playwright.sync_api import sync_playwright


BASE_URL = "https://www.confianca.com.br/marilia"
STATE_FILE = Path(
    ".collector_state/confianca/browser_state.json"
)


def clean_text(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def normalize_url(value: str) -> str:
    absolute = urljoin(BASE_URL, html.unescape(value))
    parsed = urlparse(absolute)

    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def is_category_url(value: str) -> bool:
    return (
        "confianca.com.br" in value
        and "/marilia/c/" in value
    )


def main() -> int:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    json_file = Path(
        f"logs/confianca_categories_{timestamp}.json"
    )
    csv_file = Path(
        f"logs/confianca_categories_{timestamp}.csv"
    )

    json_file.parent.mkdir(parents=True, exist_ok=True)

    categories: Dict[str, Dict] = {}

    print("=" * 72)
    print("MAPEAMENTO DE CATEGORIAS DO CONFIANÇA MARÍLIA")
    print("=" * 72)
    print(f"Página inicial: {BASE_URL}")
    print("Nenhum dado será enviado ao banco.")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)

        context_options = {
            "locale": "pt-BR",
            "viewport": {
                "width": 1440,
                "height": 1100,
            },
            "user_agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/138.0.0.0 Safari/537.36"
            ),
        }

        if STATE_FILE.exists():
            context_options["storage_state"] = str(STATE_FILE)
            print(f"Estado do navegador: {STATE_FILE}")
        else:
            print(
                "Aviso: browser_state.json não encontrado. "
                "Tentando acesso público."
            )

        context = browser.new_context(**context_options)
        page = context.new_page()

        try:
            page.goto(
                BASE_URL,
                wait_until="domcontentloaded",
                timeout=60000,
            )

            page.wait_for_timeout(10000)

            # Tenta abrir menus que podem conter os departamentos.
            possible_buttons = [
                "Categorias",
                "Departamentos",
                "Todos os departamentos",
                "Todos os produtos",
                "Menu",
            ]

            for label in possible_buttons:
                try:
                    locator = page.get_by_text(
                        label,
                        exact=False,
                    ).first

                    if locator.count() > 0:
                        locator.click(
                            timeout=2500,
                            force=True,
                        )
                        page.wait_for_timeout(1500)
                except Exception:
                    pass

            # Coleta links presentes no DOM.
            dom_links = page.locator("a[href]").evaluate_all(
                """
                elements => elements.map(element => ({
                    href: element.href || element.getAttribute('href') || '',
                    text: (
                        element.innerText ||
                        element.textContent ||
                        element.getAttribute('aria-label') ||
                        element.getAttribute('title') ||
                        ''
                    ).trim()
                }))
                """
            )

            for item in dom_links:
                raw_url = item.get("href") or ""

                if not raw_url:
                    continue

                url = normalize_url(raw_url)

                if not is_category_url(url):
                    continue

                text = clean_text(item.get("text") or "")

                category = categories.setdefault(
                    url,
                    {
                        "url": url,
                        "texts": [],
                        "sources": [],
                    },
                )

                if text and text not in category["texts"]:
                    category["texts"].append(text)

                if "dom" not in category["sources"]:
                    category["sources"].append("dom")

            # Também procura rotas de categoria escondidas no HTML.
            page_html = page.content()

            patterns = [
                r'https?://www\.confianca\.com\.br/marilia/c/'
                r'[A-Za-z0-9À-ÿ_./%?=&|+-]+',

                r'["\'](/marilia/c/'
                r'[A-Za-z0-9À-ÿ_./%?=&|+-]+)["\']',
            ]

            for pattern in patterns:
                for match in re.finditer(pattern, page_html):
                    raw_url = (
                        match.group(1)
                        if match.lastindex
                        else match.group(0)
                    )

                    raw_url = raw_url.replace("\\u002F", "/")
                    raw_url = raw_url.replace("\\/", "/")
                    raw_url = raw_url.replace("&amp;", "&")

                    url = normalize_url(raw_url)

                    if not is_category_url(url):
                        continue

                    category = categories.setdefault(
                        url,
                        {
                            "url": url,
                            "texts": [],
                            "sources": [],
                        },
                    )

                    if "html" not in category["sources"]:
                        category["sources"].append("html")

        except Exception as error:
            print(f"Erro durante a navegação: {error}")
            browser.close()
            return 1

        browser.close()

    results = []

    for url, item in categories.items():
        parsed = urlparse(url)
        parts = [
            part
            for part in parsed.path.split("/")
            if part
        ]

        slug = parts[-2] if len(parts) >= 2 else ""
        route_id = parts[-1] if parts else ""

        display_name = (
            item["texts"][0]
            if item["texts"]
            else slug.replace("-", " ").replace("_", " ")
        )

        results.append(
            {
                "name": display_name,
                "slug": slug,
                "route_id": route_id,
                "url": url,
                "texts": item["texts"],
                "sources": item["sources"],
            }
        )

    results.sort(
        key=lambda item: (
            item["name"].lower(),
            item["url"],
        )
    )

    json_file.write_text(
        json.dumps(
            results,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    with csv_file.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:
        writer = csv.writer(file, delimiter=";")

        writer.writerow(
            [
                "name",
                "slug",
                "route_id",
                "url",
                "texts",
                "sources",
            ]
        )

        for item in results:
            writer.writerow(
                [
                    item["name"],
                    item["slug"],
                    item["route_id"],
                    item["url"],
                    " | ".join(item["texts"]),
                    " | ".join(item["sources"]),
                ]
            )

    print()
    print("=" * 72)
    print("CATEGORIAS ENCONTRADAS")
    print("=" * 72)
    print(f"Total de rotas únicas: {len(results)}")

    for index, item in enumerate(results, start=1):
        print(
            f"{index:03d}. "
            f"{item['name']} "
            f"| {item['slug']} "
            f"| {item['route_id']}"
        )

    print()
    print("=" * 72)
    print("ARQUIVOS GERADOS")
    print("=" * 72)
    print(f"JSON: {json_file.resolve()}")
    print(f"CSV:  {csv_file.resolve()}")
    print()
    print("RESULTADO: somente diagnóstico. Banco não alterado.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
