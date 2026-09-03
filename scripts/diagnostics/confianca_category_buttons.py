#!/usr/bin/env python3

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from playwright.sync_api import sync_playwright


BASE_URL = "https://www.confianca.com.br/marilia"

STATE_FILE = Path(
    ".collector_state/confianca/browser_state.json"
)


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def main() -> int:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    json_file = Path(
        f"logs/confianca_category_buttons_{timestamp}.json"
    )

    screenshot_file = Path(
        f"logs/confianca_category_buttons_{timestamp}.png"
    )

    json_file.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 72)
    print("DIAGNÓSTICO DO MENU DE CATEGORIAS")
    print("=" * 72)
    print(f"Página: {BASE_URL}")
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
            print(f"Estado utilizado: {STATE_FILE}")
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

            page.wait_for_timeout(8000)

            categories_button = page.get_by_role(
                "button",
                name=re.compile(
                    r"categorias",
                    re.IGNORECASE,
                ),
            )

            if categories_button.count() == 0:
                print(
                    "ERRO: botão Categorias não foi encontrado."
                )

                page.screenshot(
                    path=str(screenshot_file),
                    full_page=True,
                )

                browser.close()
                return 1

            print("Abrindo o menu Categorias...")

            categories_button.first.click(
                force=True,
                timeout=10000,
            )

            page.wait_for_timeout(4000)

            page.screenshot(
                path=str(screenshot_file),
                full_page=True,
            )

            buttons: List[Dict] = []

            locator = page.locator("button:visible")
            button_count = locator.count()

            for index in range(button_count):
                button = locator.nth(index)

                try:
                    text = clean_text(
                        button.inner_text(timeout=2000)
                    )
                except Exception:
                    text = ""

                aria_label = clean_text(
                    button.get_attribute("aria-label") or ""
                )

                title = clean_text(
                    button.get_attribute("title") or ""
                )

                value = clean_text(
                    button.get_attribute("value") or ""
                )

                effective_text = (
                    text
                    or aria_label
                    or title
                    or value
                )

                if not effective_text:
                    continue

                buttons.append(
                    {
                        "index": index,
                        "text": text,
                        "aria_label": aria_label,
                        "title": title,
                        "value": value,
                        "aria_expanded": (
                            button.get_attribute(
                                "aria-expanded"
                            )
                        ),
                        "data_testid": (
                            button.get_attribute(
                                "data-testid"
                            )
                        ),
                        "class": (
                            button.get_attribute("class")
                        ),
                    }
                )

            links: List[Dict] = []

            link_locator = page.locator("a[href]:visible")
            link_count = link_locator.count()

            for index in range(link_count):
                link = link_locator.nth(index)

                try:
                    text = clean_text(
                        link.inner_text(timeout=2000)
                    )
                except Exception:
                    text = ""

                href = link.get_attribute("href") or ""

                if not text and not href:
                    continue

                links.append(
                    {
                        "index": index,
                        "text": text,
                        "href": href,
                    }
                )

            result = {
                "page_url": page.url,
                "page_title": page.title(),
                "visible_buttons": buttons,
                "visible_links": links,
            }

            json_file.write_text(
                json.dumps(
                    result,
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            print()
            print("=" * 72)
            print("BOTÕES VISÍVEIS APÓS ABRIR CATEGORIAS")
            print("=" * 72)
            print(f"Total: {len(buttons)}")

            for number, item in enumerate(
                buttons,
                start=1,
            ):
                label = (
                    item["text"]
                    or item["aria_label"]
                    or item["title"]
                    or item["value"]
                )

                print(
                    f"{number:03d}. {label}"
                    f" | expanded={item['aria_expanded']}"
                )

            print()
            print("=" * 72)
            print("LINKS VISÍVEIS DO MENU")
            print("=" * 72)
            print(f"Total: {len(links)}")

            for number, item in enumerate(
                links,
                start=1,
            ):
                print(
                    f"{number:03d}. "
                    f"{item['text']} "
                    f"| {item['href']}"
                )

            print()
            print("=" * 72)
            print("ARQUIVOS")
            print("=" * 72)
            print(f"JSON: {json_file.resolve()}")
            print(
                f"Captura: {screenshot_file.resolve()}"
            )
            print()
            print(
                "RESULTADO: apenas diagnóstico. "
                "Banco não alterado."
            )

        except Exception as error:
            print(f"ERRO DURANTE O DIAGNÓSTICO: {error}")

            try:
                page.screenshot(
                    path=str(screenshot_file),
                    full_page=True,
                )
            except Exception:
                pass

            browser.close()
            return 1

        browser.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
