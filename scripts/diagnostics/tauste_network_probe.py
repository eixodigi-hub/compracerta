#!/usr/bin/env python3

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from playwright.sync_api import sync_playwright


PRODUCT_URL = (
    "https://tauste.com.br/marilia/"
    "arroz-tio-jo-o-tipo-1-pacote-5000g.html"
)

KEY_PATTERN = re.compile(
    r"(gtin|ean|barcode|bar.?code|codigo.*barra|cod.*barra)",
    re.IGNORECASE,
)

NUMBER_PATTERN = re.compile(r"(?<!\d)\d{8,14}(?!\d)")


def normalize_code(value: Any) -> str:
    return re.sub(r"\D", "", str(value or ""))


def valid_gtin(value: Any) -> bool:
    code = normalize_code(value)

    if len(code) not in (8, 12, 13, 14):
        return False

    if len(set(code)) == 1:
        return False

    body = code[:-1]
    expected = int(code[-1])

    total = 0

    for index, digit in enumerate(reversed(body)):
        multiplier = 3 if index % 2 == 0 else 1
        total += int(digit) * multiplier

    calculated = (10 - total % 10) % 10
    return calculated == expected


def walk_json(
    value: Any,
    path: str = "root",
    results: List[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    if results is None:
        results = []

    if isinstance(value, dict):
        for key, item in value.items():
            current_path = f"{path}.{key}"

            if KEY_PATTERN.search(str(key)):
                results.append(
                    {
                        "type": "explicit_key",
                        "path": current_path,
                        "value": item,
                        "normalized": normalize_code(item),
                        "valid_gtin": valid_gtin(item),
                    }
                )

            if isinstance(item, str) and KEY_PATTERN.search(item):
                results.append(
                    {
                        "type": "keyword_value",
                        "path": current_path,
                        "value": item[:500],
                        "normalized": "",
                        "valid_gtin": False,
                    }
                )

            walk_json(item, current_path, results)

    elif isinstance(value, list):
        for index, item in enumerate(value):
            walk_json(item, f"{path}[{index}]", results)

    return results


def main() -> int:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = Path("logs") / f"tauste_network_probe_{timestamp}.json"

    requests_found: List[Dict[str, Any]] = []
    candidate_results: List[Dict[str, Any]] = []

    print("=" * 72)
    print("CAPTURA DE REQUISIÇÕES INTERNAS DO TAUSTE")
    print("=" * 72)
    print(f"Produto: {PRODUCT_URL}")
    print("Abrindo Chromium em modo invisível...")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)

        context = browser.new_context(
            locale="pt-BR",
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/138.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 1000},
        )

        page = context.new_page()

        def process_response(response):
            request = response.request
            resource_type = request.resource_type
            content_type = response.headers.get("content-type", "")

            interesting = (
                resource_type in {"xhr", "fetch"}
                or "json" in content_type.lower()
                or "graphql" in response.url.lower()
                or "/rest/" in response.url.lower()
            )

            if not interesting:
                return

            record: Dict[str, Any] = {
                "url": response.url,
                "status": response.status,
                "resource_type": resource_type,
                "method": request.method,
                "content_type": content_type,
                "post_data": request.post_data,
                "body_size": 0,
                "body_preview": "",
                "candidates": [],
            }

            try:
                body = response.text()
            except Exception as error:
                record["read_error"] = str(error)
                requests_found.append(record)
                return

            record["body_size"] = len(body)
            record["body_preview"] = body[:1000]

            candidates: List[Dict[str, Any]] = []

            try:
                parsed = json.loads(body)
                candidates.extend(walk_json(parsed))
            except (json.JSONDecodeError, TypeError):
                pass

            for match in NUMBER_PATTERN.finditer(body):
                code = match.group(0)

                if not valid_gtin(code):
                    continue

                start = max(0, match.start() - 160)
                end = min(len(body), match.end() + 160)
                context_text = re.sub(r"\s+", " ", body[start:end])

                candidates.append(
                    {
                        "type": "valid_gtin_sequence",
                        "path": "response_text",
                        "value": code,
                        "normalized": code,
                        "valid_gtin": True,
                        "context": context_text,
                    }
                )

            unique_candidates = []
            seen = set()

            for candidate in candidates:
                signature = (
                    candidate.get("type"),
                    candidate.get("path"),
                    str(candidate.get("value")),
                )

                if signature in seen:
                    continue

                seen.add(signature)
                unique_candidates.append(candidate)

            record["candidates"] = unique_candidates

            if unique_candidates:
                candidate_results.append(
                    {
                        "url": response.url,
                        "method": request.method,
                        "status": response.status,
                        "resource_type": resource_type,
                        "post_data": request.post_data,
                        "candidates": unique_candidates,
                    }
                )

            requests_found.append(record)

        page.on("response", process_response)

        try:
            page.goto(
                PRODUCT_URL,
                wait_until="domcontentloaded",
                timeout=60000,
            )

            page.wait_for_timeout(12000)

            page.evaluate(
                """
                () => {
                    window.scrollTo(0, document.body.scrollHeight);
                }
                """
            )

            page.wait_for_timeout(5000)

        except Exception as error:
            print(f"Erro durante a navegação: {error}")

        page_title = page.title()
        final_url = page.url

        browser.close()

    result = {
        "product_url": PRODUCT_URL,
        "final_url": final_url,
        "page_title": page_title,
        "requests_count": len(requests_found),
        "requests": requests_found,
        "candidate_endpoints": candidate_results,
    }

    output_file.write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print()
    print("=" * 72)
    print("REQUISIÇÕES CAPTURADAS")
    print("=" * 72)
    print(f"Total: {len(requests_found)}")

    for index, item in enumerate(requests_found, start=1):
        print(
            f"{index:02d}. {item['method']} "
            f"{item['status']} "
            f"{item['resource_type']} "
            f"{item['url']}"
        )

    print()
    print("=" * 72)
    print("ENDPOINTS COM CANDIDATOS")
    print("=" * 72)

    if not candidate_results:
        print("Nenhum EAN/GTIN confiável foi localizado nas respostas.")
    else:
        for endpoint in candidate_results:
            print()
            print(f"URL: {endpoint['url']}")
            print(f"Método: {endpoint['method']}")
            print(f"Status: {endpoint['status']}")

            if endpoint.get("post_data"):
                print(f"Dados enviados: {endpoint['post_data'][:1000]}")

            for candidate in endpoint["candidates"]:
                print("-" * 50)
                print(f"Tipo: {candidate.get('type')}")
                print(f"Caminho: {candidate.get('path')}")
                print(f"Valor: {candidate.get('value')}")
                print(f"GTIN válido: {candidate.get('valid_gtin')}")

                if candidate.get("context"):
                    print(f"Contexto: {candidate['context']}")

    print()
    print("=" * 72)
    print("RESUMO")
    print("=" * 72)
    print(f"Título da página: {page_title}")
    print(f"URL final: {final_url}")
    print(f"Requisições analisadas: {len(requests_found)}")
    print(f"Endpoints com candidatos: {len(candidate_results)}")
    print(f"Arquivo completo: {output_file.resolve()}")

    if candidate_results:
        print("RESULTADO: encontramos respostas que precisam ser validadas.")
    else:
        print(
            "RESULTADO: o navegador também não recebeu um EAN evidente. "
            "Nesse caso, será necessário obter os códigos por outra fonte "
            "ou usar associação controlada por nome, marca e quantidade."
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
