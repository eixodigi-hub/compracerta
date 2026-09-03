from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Response, sync_playwright


ROOT_DIR = Path(__file__).resolve().parents[2]
STATE_DIR = ROOT_DIR / ".collector_state" / "confianca"
LOG_DIR = ROOT_DIR / "logs"

STATE_FILE = STATE_DIR / "browser_state.json"

TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

NETWORK_FILE = LOG_DIR / f"confianca_network_{TIMESTAMP}.jsonl"
HTML_FILE = LOG_DIR / f"confianca_page_{TIMESTAMP}.html"
SCREENSHOT_FILE = LOG_DIR / f"confianca_page_{TIMESTAMP}.png"

BASE_URL = os.environ.get(
    "CONFIANCA_BASE_URL",
    "https://www.confianca.com.br/marilia",
)

STATE_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

network_records: list[dict[str, object]] = []


def response_handler(response: Response) -> None:
    content_type = response.headers.get("content-type", "")
    resource_type = response.request.resource_type
    url_lower = response.url.lower()

    terms = (
        "product",
        "produto",
        "catalog",
        "categoria",
        "category",
        "search",
        "busca",
        "price",
        "preco",
        "store",
        "loja",
        "location",
        "cep",
        "graphql",
        "api",
    )

    interesting = (
        "json" in content_type.lower()
        or resource_type in {"xhr", "fetch"}
        or any(term in url_lower for term in terms)
    )

    if not interesting:
        return

    network_records.append(
        {
            "status": response.status,
            "resource_type": resource_type,
            "content_type": content_type,
            "url": response.url,
        }
    )


def save_network_log() -> None:
    with NETWORK_FILE.open("w", encoding="utf-8") as file:
        for record in network_records:
            file.write(
                json.dumps(record, ensure_ascii=False) + "\n"
            )


def main() -> int:
    print("=" * 60)
    print("Diagnóstico do Confiança Marília")
    print("=" * 60)
    print(f"URL inicial: {BASE_URL}")
    print("Nenhum produto será enviado ao Lovable.")
    print()

    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(
                headless=False,
            )
        except PlaywrightError as error:
            print("ERRO: não foi possível abrir o Google Chrome.")
            print(error)
            return 1

        context_options: dict[str, object] = {
            "locale": "pt-BR",
            "timezone_id": "America/Sao_Paulo",
            "viewport": {
                "width": 1440,
                "height": 900,
            },
        }

        if STATE_FILE.exists():
            context_options["storage_state"] = str(STATE_FILE)
            print("Sessão anterior carregada.")

        context = browser.new_context(**context_options)
        page = context.new_page()
        page.on("response", response_handler)

        try:
            page.goto(
                BASE_URL,
                wait_until="domcontentloaded",
                timeout=90_000,
            )
        except PlaywrightError as error:
            print(f"AVISO ao abrir a página: {error}")

        print()
        print("No navegador:")
        print("1. Confirme que está no catálogo de Marília.")
        print("2. Escolha entrega ou retirada, se necessário.")
        print("3. Informe um CEP de Marília, se solicitado.")
        print("4. Abra uma categoria, como arroz.")
        print("5. Aguarde os produtos e preços aparecerem.")
        print()

        input(
            "Depois, volte ao Terminal e pressione Enter..."
        )

        page.wait_for_timeout(3000)

        context.storage_state(path=str(STATE_FILE))

        HTML_FILE.write_text(
            page.content(),
            encoding="utf-8",
        )

        page.screenshot(
            path=str(SCREENSHOT_FILE),
            full_page=True,
        )

        save_network_log()
        browser.close()

    print()
    print("=" * 60)
    print("Diagnóstico salvo")
    print("=" * 60)
    print(f"HTML: {HTML_FILE}")
    print(f"Captura: {SCREENSHOT_FILE}")
    print(f"Rede: {NETWORK_FILE}")
    print(
        f"Respostas técnicas registradas: "
        f"{len(network_records)}"
    )

    candidates: list[str] = []
    seen_urls: set[str] = set()

    for record in network_records:
        url = str(record["url"])

        if url in seen_urls:
            continue

        seen_urls.add(url)

        parsed = urlparse(url)
        url_lower = url.lower()

        relevant = (
            record["resource_type"] in {"xhr", "fetch"}
            or "json" in str(record["content_type"]).lower()
            or any(
                term in url_lower
                for term in (
                    "product",
                    "produto",
                    "catalog",
                    "category",
                    "categoria",
                    "search",
                    "graphql",
                    "api",
                )
            )
        )

        if relevant:
            candidates.append(
                f'{record["status"]} '
                f'{record["resource_type"]} '
                f'{parsed.scheme}://{parsed.netloc}{parsed.path}'
            )

    print()
    print("Possíveis endpoints encontrados:")

    if candidates:
        for candidate in candidates[:50]:
            print(candidate)
    else:
        print("Nenhum endpoint candidato foi identificado.")

    print()
    print("Não compartilhe o arquivo browser_state.json.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
