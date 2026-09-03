#!/usr/bin/env python3

import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlencode

from playwright.sync_api import Request, sync_playwright


HOST = "https://www.confianca.com.br"
SORT = "product.analytics.factorQuantitySold30d|1"

CATEGORY_PATH = "/c/matinais/s_matinais"
ROUTE_ID = "s_matinais"

STATE_FILE = Path(
    ".collector_state/confianca/browser_state.json"
)

LOG_DIR = Path("logs")


def replay_headers(
    captured: Dict[str, str],
    referer: str,
) -> Dict[str, str]:
    headers: Dict[str, str] = {}

    for key, value in captured.items():
        key_lower = key.lower()

        if key_lower.startswith("x-"):
            headers[key] = value

        elif key_lower in {
            "accept",
            "accept-language",
            "content-type",
        }:
            headers[key] = value

    headers["Accept"] = "application/json"
    headers["Referer"] = referer

    return headers


def find_navigation_ids(value: Any) -> List[str]:
    serialized = json.dumps(
        value,
        ensure_ascii=False,
    )

    return sorted(
        set(
            re.findall(
                r"\bN-\d+\b",
                serialized,
            )
        )
    )


def extract_candidate_product_ids(
    value: Any,
    path: str = "",
) -> Set[str]:
    results: Set[str] = set()

    if isinstance(value, dict):
        for key, nested in value.items():
            new_path = (
                f"{path}.{key}"
                if path
                else key
            )

            key_lower = key.lower()
            path_lower = new_path.lower()

            product_context = (
                "product" in key_lower
                or "product" in path_lower
            )

            if product_context:
                if isinstance(nested, int):
                    text = str(nested)

                    if 5 <= len(text) <= 12:
                        results.add(text)

                elif isinstance(nested, str):
                    results.update(
                        re.findall(
                            r"\b\d{5,12}\b",
                            nested,
                        )
                    )

                elif isinstance(nested, list):
                    for item in nested:
                        if isinstance(
                            item,
                            (str, int),
                        ):
                            results.update(
                                re.findall(
                                    r"\b\d{5,12}\b",
                                    str(item),
                                )
                            )

            results.update(
                extract_candidate_product_ids(
                    nested,
                    new_path,
                )
            )

    elif isinstance(value, list):
        for index, nested in enumerate(value):
            results.update(
                extract_candidate_product_ids(
                    nested,
                    f"{path}[{index}]",
                )
            )

    return results


def collect_relevant_fields(
    value: Any,
    path: str = "",
    output: Optional[List[Dict]] = None,
) -> List[Dict]:
    if output is None:
        output = []

    relevant_words = (
        "total",
        "count",
        "number",
        "num",
        "record",
        "page",
        "offset",
        "limit",
        "product",
        "category",
        "navigation",
        "repository",
        "route",
        "child",
    )

    if isinstance(value, dict):
        for key, nested in value.items():
            new_path = (
                f"{path}.{key}"
                if path
                else key
            )

            if any(
                word in key.lower()
                for word in relevant_words
            ):
                if isinstance(
                    nested,
                    (str, int, float, bool),
                ) or nested is None:
                    summary = nested

                elif isinstance(nested, list):
                    summary = (
                        f"lista com {len(nested)} itens"
                    )

                elif isinstance(nested, dict):
                    summary = (
                        "objeto com "
                        f"{len(nested)} campos"
                    )

                else:
                    summary = type(nested).__name__

                output.append(
                    {
                        "path": new_path,
                        "value": summary,
                    }
                )

            collect_relevant_fields(
                nested,
                new_path,
                output,
            )

    elif isinstance(value, list):
        for index, nested in enumerate(value):
            collect_relevant_fields(
                nested,
                f"{path}[{index}]",
                output,
            )

    return output


def inspect_response(
    name: str,
    response,
    output_dir: Path,
) -> Dict:
    status = response.status
    content_type = (
        response.headers.get("content-type", "")
    )

    try:
        body_text = response.text()
    except Exception as error:
        return {
            "name": name,
            "status": status,
            "content_type": content_type,
            "error": str(error),
        }

    body_hash = hashlib.sha256(
        body_text.encode("utf-8")
    ).hexdigest()

    raw_file = output_dir / f"{name}.txt"

    raw_file.write_text(
        body_text,
        encoding="utf-8",
    )

    try:
        data = json.loads(body_text)
    except json.JSONDecodeError:
        data = None

    result = {
        "name": name,
        "status": status,
        "content_type": content_type,
        "bytes": len(
            body_text.encode("utf-8")
        ),
        "sha256": body_hash,
        "raw_file": str(raw_file),
        "json": data is not None,
        "navigation_ids": [],
        "candidate_product_ids": [],
        "relevant_fields": [],
        "top_level_keys": [],
    }

    if data is not None:
        if isinstance(data, dict):
            result["top_level_keys"] = sorted(
                data.keys()
            )

        result["navigation_ids"] = (
            find_navigation_ids(data)
        )

        result["candidate_product_ids"] = sorted(
            extract_candidate_product_ids(data)
        )

        result["relevant_fields"] = (
            collect_relevant_fields(data)
        )

        json_file = output_dir / f"{name}.json"

        json_file.write_text(
            json.dumps(
                data,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    return result


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

    output_dir = LOG_DIR / (
        f"confianca_collection_probe_{timestamp}"
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    encoded_sort = SORT.replace(
        "|",
        "%7C",
    )

    category_url = (
        f"{HOST}/marilia"
        f"{CATEGORY_PATH}"
        f"?Ns={encoded_sort}"
    )

    captured_products_url = None
    captured_headers: Dict[str, str] = {}

    print("=" * 72)
    print("DIAGNÓSTICO DA COLEÇÃO — MATINAIS")
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
            nonlocal captured_headers

            if (
                "/ccstore/v1/products?"
                not in request.url
            ):
                return

            if "productIds=" not in request.url:
                return

            if captured_products_url is not None:
                return

            captured_products_url = request.url
            captured_headers = (
                request.all_headers()
            )

        page.on("request", handle_request)

        print(f"Abrindo: {category_url}")

        page.goto(
            category_url,
            wait_until="domcontentloaded",
            timeout=90_000,
        )

        page.wait_for_timeout(20_000)

        if (
            captured_products_url is None
            or not captured_headers
        ):
            browser.close()

            print(
                "ERRO: contexto da loja "
                "não foi capturado."
            )

            return 3

        headers = replay_headers(
            captured_headers,
            category_url,
        )

        probes = []

        collection_url = (
            f"{HOST}/ccstore/v1/"
            f"collections/{ROUTE_ID}"
        )

        probes.append(
            (
                "collection",
                collection_url,
            )
        )

        client_base = (
            f"{HOST}/ccstore/v1/"
            f"clientApplications/confianca/page"
            f"{CATEGORY_PATH}/"
        )

        for offset in (0, 60, 120):
            query = urlencode(
                {
                    "Ns": SORT,
                    "No": offset,
                    "Nrpp": 60,
                }
            )

            probes.append(
                (
                    f"client_offset_{offset}",
                    f"{client_base}?{query}",
                )
            )

        assembler_route_url = (
            f"{HOST}/ccstore/v1/"
            f"assembler/pages/Default/"
            f"osf/catalog/_/{ROUTE_ID}"
            f"?No=0"
            f"&Nrpp=60"
            f"&Ns={encoded_sort}"
        )

        probes.append(
            (
                "assembler_route_id",
                assembler_route_url,
            )
        )

        results = []

        for name, url in probes:
            print()
            print(f"Consultando: {name}")

            try:
                response = context.request.get(
                    url,
                    headers=headers,
                    timeout=90_000,
                )

                result = inspect_response(
                    name,
                    response,
                    output_dir,
                )

                result["url"] = url
                results.append(result)

                print(
                    f"  HTTP: {result['status']}"
                )

                print(
                    f"  Tamanho: "
                    f"{result.get('bytes', 0)} bytes"
                )

                print(
                    "  Navigation IDs: "
                    f"{result.get('navigation_ids', [])}"
                )

                print(
                    "  Possíveis IDs de produtos: "
                    f"{len(result.get('candidate_product_ids', []))}"
                )

            except Exception as error:
                print(f"  ERRO: {error}")

                results.append(
                    {
                        "name": name,
                        "url": url,
                        "error": str(error),
                    }
                )

        browser.close()

    summary_file = output_dir / "summary.json"

    summary_file.write_text(
        json.dumps(
            results,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print("=" * 72)
    print("CAMPOS RELEVANTES DA COLEÇÃO")
    print("=" * 72)

    collection_result = next(
        (
            item
            for item in results
            if item.get("name") == "collection"
        ),
        None,
    )

    if collection_result:
        relevant_fields = (
            collection_result.get(
                "relevant_fields",
                [],
            )
        )

        print(
            f"Total de campos relevantes: "
            f"{len(relevant_fields)}"
        )

        for item in relevant_fields[:120]:
            print(
                f"{item['path']} = "
                f"{item['value']}"
            )

    print()
    print("=" * 72)
    print("COMPARAÇÃO DOS OFFSETS")
    print("=" * 72)

    for result in results:
        if not result.get(
            "name",
            "",
        ).startswith("client_offset_"):
            continue

        print(
            f"{result['name']}: "
            f"HTTP {result.get('status')} | "
            f"bytes={result.get('bytes')} | "
            f"hash={result.get('sha256', '')[:16]} | "
            f"IDs={len(result.get('candidate_product_ids', []))}"
        )

    print()
    print("=" * 72)
    print("ARQUIVOS")
    print("=" * 72)
    print(f"Diretório: {output_dir.resolve()}")
    print(f"Resumo: {summary_file.resolve()}")
    print()
    print(
        "RESULTADO: somente diagnóstico. "
        "Banco não alterado."
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
