"""Probe único: grava as chamadas de rede reais do spanionline.com.br
(VipCommerce) para descobrir o fluxo de autenticação/token usado pelo
app antes de escrevermos o coletor de verdade. Não faz parte do
pipeline de coleta.
"""

from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT_FILE = Path(__file__).resolve().parents[2] / "logs" / "spani_network_probe.json"


def main() -> int:
    captured: list[dict] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(locale="pt-BR")
        page = context.new_page()

        def handle_request(request):
            if "vipcommerce" in request.url:
                captured.append(
                    {
                        "type": "request",
                        "method": request.method,
                        "url": request.url,
                        "headers": dict(request.headers),
                        "post_data": request.post_data,
                    }
                )

        def handle_response(response):
            if "vipcommerce" in response.url:
                body = None
                try:
                    body = response.text()
                except Exception:
                    body = None
                captured.append(
                    {
                        "type": "response",
                        "status": response.status,
                        "url": response.url,
                        "body": (body or "")[:4000],
                    }
                )

        page.on("request", handle_request)
        page.on("response", handle_response)

        page.goto("https://www.spanionline.com.br/", wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(3000)

        browser.close()

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(
        json.dumps(captured, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Capturado(s) {len(captured)} evento(s). Arquivo: {OUT_FILE}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
