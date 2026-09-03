#!/usr/bin/env python3

import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List
from urllib.parse import urljoin, urlparse

from playwright.sync_api import sync_playwright


BASE_URL = "https://www.confianca.com.br/marilia"

STATE_FILE = Path(
    ".collector_state/confianca/browser_state.json"
)


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def latest_buttons_file() -> Path:
    files = sorted(
        Path("logs").glob(
            "confianca_category_buttons_*.json"
        ),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )

    if not files:
        raise SystemExit(
            "Nenhum arquivo confianca_category_buttons_*.json "
            "foi encontrado em logs/."
        )

    return files[0]


def normalize_to_marilia(raw_url: str) -> str:
    absolute = urljoin(BASE_URL, raw_url)
    parsed = urlparse(absolute)

    path = re.sub(
        r"^/(bauru|botucatu|jau|sorocaba|marilia)/c/",
        "/marilia/c/",
        parsed.path,
        flags=re.IGNORECASE,
    )

    query = parsed.query

    if not query:
        query = (
            "Ns="
            "product.analytics.factorQuantitySold30d%7C1"
        )

    return (
        f"https://www.confianca.com.br"
        f"{path}?{query}"
    )


def extract_navigation_id(urls: List[str]) -> str:
    for url in urls:
        match = re.search(
            r"/(N-[0-9]+)(?:[/?]|$)",
            url,
        )

        if match:
            return match.group(1)

    return ""


def route_parts(url: str):
    parsed = urlparse(url)

    parts = [
        part
        for part in parsed.path.split("/")
        if part
    ]

    try:
        category_index = parts.index("c")

        return (
            parts[category_index + 1],
            parts[category_index + 2],
        )
    except (ValueError, IndexError):
        return None, None


def main() -> int:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    json_file = Path(
        f"logs/confianca_categories_full_{timestamp}.json"
    )

    csv_file = Path(
        f"logs/confianca_categories_full_{timestamp}.csv"
    )

    json_file.parent.mkdir(parents=True, exist_ok=True)

    source_file = latest_buttons_file()

    print("=" * 72)
    print("MAPEAMENTO COMPLETO DE CATEGORIAS")
    print("=" * 72)
    print(f"Arquivo de origem: {source_file}")
    print("Nenhum dado será enviado ao banco.")

    source_data = json.loads(
        source_file.read_text(encoding="utf-8")
    )

    candidates: Dict[str, Dict] = {}

    visible_links = source_data.get("visible_links") or []

    for item in visible_links:
        name = clean_text(item.get("text") or "")
        href = item.get("href") or ""

        if not name or "/c/" not in href:
            continue

        marilia_url = normalize_to_marilia(href)

        slug, route_id = route_parts(marilia_url)

        if not slug or not route_id:
            continue

        key = f"{slug}/{route_id}".lower()

        if key not in candidates:
            candidates[key] = {
                "name": name,
                "slug": slug,
                "route_id": route_id,
                "original_url": href,
                "marilia_url": marilia_url,
            }

    # Esta categoria já foi validada anteriormente.
    alimentos_url = (
        "https://www.confianca.com.br"
        "/marilia/c/alimentos-basicos/g_alimentos_basicos"
        "?Ns=product.analytics.factorQuantitySold30d%7C1"
    )

    candidates["alimentos-basicos/g_alimentos_basicos"] = {
        "name": "Alimentos Básicos",
        "slug": "alimentos-basicos",
        "route_id": "g_alimentos_basicos",
        "original_url": alimentos_url,
        "marilia_url": alimentos_url,
    }

    print(
        f"Categorias candidatas encontradas: "
        f"{len(candidates)}"
    )

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)

        context_options = {
            "locale": "pt-BR",
            "viewport": {
                "width": 1440,
                "height": 1000,
            },
            "user_agent": (
                "Mozilla/5.0 "
                "(Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/138.0.0.0 Safari/537.36"
            ),
        }

        if STATE_FILE.exists():
            context_options["storage_state"] = str(
                STATE_FILE
            )

            print(f"Estado utilizado: {STATE_FILE}")

        context = browser.new_context(**context_options)

        results = []

        candidate_list = list(candidates.values())

        for position, item in enumerate(
            candidate_list,
            start=1,
        ):
            print()
            print(
                f"[{position}/{len(candidate_list)}] "
                f"{item['name']}"
            )

            page = context.new_page()

            assembler_urls = []
            client_application_urls = []

            def capture_response(response):
                url = response.url

                if (
                    "/ccstore/v1/assembler/pages/"
                    in url
                    and "/catalog/" in url
                ):
                    assembler_urls.append(url)

                if (
                    "/ccstore/v1/clientApplications/"
                    in url
                    and "/page/c/" in url
                ):
                    client_application_urls.append(url)

            page.on("response", capture_response)

            status = "erro"
            navigation_id = ""
            final_url = ""
            page_title = ""
            page_status = None
            product_links = 0
            error_message = ""

            try:
                response = page.goto(
                    item["marilia_url"],
                    wait_until="domcontentloaded",
                    timeout=60000,
                )

                page.wait_for_timeout(8000)

                final_url = page.url
                page_title = page.title()

                if response is not None:
                    page_status = response.status

                product_links = page.locator(
                    'a[href*="/p/"]'
                ).count()

                navigation_id = extract_navigation_id(
                    assembler_urls
                )

                if navigation_id:
                    status = "validada"
                elif page_status == 200:
                    status = "pagina_200_sem_navigation_id"
                else:
                    status = "nao_validada"

            except Exception as error:
                error_message = str(error)

            result = {
                **item,
                "status": status,
                "page_status": page_status,
                "navigation_id": navigation_id,
                "final_url": final_url,
                "page_title": page_title,
                "product_links_visible": product_links,
                "assembler_urls": assembler_urls,
                "client_application_urls": (
                    client_application_urls
                ),
                "error": error_message,
            }

            results.append(result)

            print(f"  Status: {status}")

            print(
                "  Navigation ID: "
                f"{navigation_id or 'não identificado'}"
            )

            print(
                f"  Produtos visíveis: {product_links}"
            )

            page.close()

        browser.close()

    results.sort(
        key=lambda item: item["name"].lower()
    )

    json_file.write_text(
        json.dumps(
            results,
            ensure_ascii=False,
            indent=2,
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
                "navigation_id",
                "status",
                "page_status",
                "product_links_visible",
                "marilia_url",
                "final_url",
                "error",
            ]
        )

        for item in results:
            writer.writerow(
                [
                    item["name"],
                    item["slug"],
                    item["route_id"],
                    item["navigation_id"],
                    item["status"],
                    item["page_status"],
                    item["product_links_visible"],
                    item["marilia_url"],
                    item["final_url"],
                    item["error"],
                ]
            )

    valid = [
        item
        for item in results
        if item["status"] == "validada"
    ]

    print()
    print("=" * 72)
    print("CATEGORIAS VALIDADAS")
    print("=" * 72)
    print(f"Total validado: {len(valid)}")

    for index, item in enumerate(valid, start=1):
        print(
            f"{index:03d}. "
            f"{item['name']} "
            f"| {item['slug']} "
            f"| {item['route_id']} "
            f"| {item['navigation_id']} "
            f"| produtos visíveis: "
            f"{item['product_links_visible']}"
        )

    not_valid = [
        item
        for item in results
        if item["status"] != "validada"
    ]

    print()
    print("=" * 72)
    print("ROTAS NÃO VALIDADAS")
    print("=" * 72)
    print(f"Total: {len(not_valid)}")

    for item in not_valid:
        print(
            f"- {item['name']} "
            f"| {item['status']} "
            f"| HTTP {item['page_status']} "
            f"| {item['marilia_url']}"
        )

    print()
    print("=" * 72)
    print("ARQUIVOS GERADOS")
    print("=" * 72)
    print(f"JSON: {json_file.resolve()}")
    print(f"CSV:  {csv_file.resolve()}")
    print()
    print(
        "RESULTADO: apenas diagnóstico. "
        "Banco não alterado."
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
