from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from playwright.sync_api import Request, sync_playwright


ROOT_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT_DIR / ".env"
STATE_FILE = (
    ROOT_DIR
    / ".collector_state"
    / "confianca"
    / "browser_state.json"
)
LOG_DIR = ROOT_DIR / "logs"

HOST = "https://www.confianca.com.br"
SORT = "product.analytics.factorQuantitySold30d|1"
PAGE_SIZE = 60

CATEGORIES = {
    "alimentos_basicos": {
        "path": "/c/alimentos-basicos/g_alimentos_basicos",
        "navigation_id": "N-776784396",
    },
    "matinais": {
        "path": "/c/matinais/s_matinais",
        "navigation_id": None,
    },
    "padaria": {
        "path": "/c/padaria/s_padaria",
        "navigation_id": None,
    },
    "hortifruti": {
        "path": "/c/hortifruti/s_hortifruti",
        "navigation_id": None,
    },
    "acougue": {
        "path": "/c/acougue/s_acougue",
        "navigation_id": None,
    },
    "emporium": {
        "path": (
            "/c/emporium-confianca-delivery-"
            "temperos-castanhas-graos/s_emporium"
        ),
        "navigation_id": None,
    },
    "bebidas": {
        "path": "/c/bebidas/s_bebidas",
        "navigation_id": None,
    },
    "higiene_beleza": {
        "path": (
            "/c/higiene-beleza/"
            "s_higiene_e_beleza"
        ),
        "navigation_id": None,
    },
    "marcas_exclusivas": {
        "path": (
            "/c/marcas-exclusivas/"
            "s_marcas_exclusivas"
        ),
        "navigation_id": None,
    },
    "pet_shop": {
        "path": "/c/pet-shop/s_pet_shop",
        "navigation_id": None,
    },
}

PRODUCT_FIELDS = ",".join(
    (
        "orderLimit",
        "active",
        "primarySmallImageURL",
        "primaryImageAltText",
        "id",
        "parentCategories",
        "defaultProductListingSku",
        "route",
        "primarySourceImageURL",
        "primaryThumbImageURL",
        "displayName",
        "primaryFullImageURL",
        "primaryLargeImageURL",
        "childSKUs",
        "salePrice",
        "salePrices",
        "listPrices",
        "defaultParentCategory",
        "listPrice",
        "parentCategory",
        "primaryImageTitle",
        "repositoryId",
        "x_unitOfMeasurement",
        "x_ProductWeightLiteracy",
    )
)


def load_env() -> None:
    if not ENV_FILE.exists():
        return

    for raw_line in ENV_FILE.read_text(
        encoding="utf-8"
    ).splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#"):
            continue

        if "=" not in line:
            continue

        key, value = line.split("=", 1)

        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key:
            os.environ.setdefault(key, value)


def as_number(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, str):
        normalized = value.strip().replace(",", ".")

        try:
            return float(normalized)
        except ValueError:
            return None

    return None


def absolute_url(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None

    value = value.strip()

    if not value:
        return None

    if value.startswith(("http://", "https://")):
        return value

    if value.startswith("/"):
        return HOST + value

    return HOST + "/" + value


def extract_numeric_values(value: Any) -> List[str]:
    found: List[str] = []

    if isinstance(value, int):
        found.append(str(value))

    elif isinstance(value, str):
        found.extend(
            re.findall(
                r"\b\d{5,12}\b",
                value,
            )
        )

    elif isinstance(value, list):
        for item in value:
            found.extend(
                extract_numeric_values(item)
            )

    return found


def extract_product_ids(data: Any) -> List[str]:
    if not isinstance(data, dict):
        return []

    results = data.get("results", {})

    if not isinstance(results, dict):
        return []

    records = results.get("records", [])

    if not isinstance(records, list):
        return []

    product_ids: List[str] = []
    seen: Set[str] = set()

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                key_lower = key.lower().replace(
                    "_",
                    "",
                )

                is_product_field = (
                    "product.repositoryid"
                    in key.lower()
                    or key_lower.endswith("productid")
                    or key_lower == "repositoryid"
                )

                if is_product_field:
                    candidates = extract_numeric_values(
                        nested
                    )

                    for candidate in candidates:
                        if candidate in seen:
                            continue

                        seen.add(candidate)
                        product_ids.append(candidate)

                walk(nested)

        elif isinstance(value, list):
            for nested in value:
                walk(nested)

    for record in records:
        walk(record)

    return product_ids


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


def build_products_url(
    captured_url: str,
    product_ids: List[str],
) -> str:
    parsed = urlparse(captured_url)

    query = parse_qs(
        parsed.query,
        keep_blank_values=True,
    )

    query["productIds"] = [
        ",".join(product_ids)
    ]

    query["continueOnMissingProduct"] = [
        "true"
    ]

    query["fields"] = [PRODUCT_FIELDS]

    encoded_query = urlencode(
        query,
        doseq=True,
    )

    return urlunparse(
        parsed._replace(
            query=encoded_query,
        )
    )


def stock_map(data: Any) -> Dict[str, float]:
    result: Dict[str, float] = {}

    if not isinstance(data, dict):
        return result

    items = data.get("items", [])

    if not isinstance(items, list):
        return result

    for item in items:
        if not isinstance(item, dict):
            continue

        details = item.get(
            "productSkuInventoryDetails",
            [],
        )

        if not isinstance(details, list):
            continue

        for detail in details:
            if not isinstance(detail, dict):
                continue

            product_id = str(
                detail.get("catRefId", "")
            ).strip()

            quantity = as_number(
                detail.get("inStockQuantity")
            )

            if product_id and quantity is not None:
                result[product_id] = quantity

    return result


def select_sku(
    product: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    child_skus = product.get("childSKUs") or []

    if not isinstance(child_skus, list):
        return None

    valid_skus = [
        sku
        for sku in child_skus
        if isinstance(sku, dict)
    ]

    for sku in valid_skus:
        if (
            sku.get(
                "x_activeConfiancaEsmeralda"
            )
            is True
        ):
            return sku

    if valid_skus:
        return valid_skus[0]

    return None


def normalize_product(
    product: Dict[str, Any],
    quantities: Dict[str, float],
    category_key: str,
    site_base_url: str,
) -> Tuple[
    Optional[Dict[str, Any]],
    Optional[str],
]:
    product_id = str(
        product.get("id")
        or product.get("repositoryId")
        or ""
    ).strip()

    if not product_id:
        return None, "sem_id"

    sku = select_sku(product)

    if sku is None:
        return None, "sem_sku"

    list_price = as_number(
        sku.get("listPrice")
    )

    sale_price = as_number(
        sku.get("salePrice")
    )

    if (
        list_price is not None
        and list_price <= 0
    ):
        list_price = None

    if (
        sale_price is not None
        and sale_price <= 0
    ):
        sale_price = None

    current_price = (
        sale_price
        if sale_price is not None
        else list_price
    )

    if current_price is None:
        return None, "sem_preco"

    if list_price is None:
        list_price = current_price

    promotional = (
        sale_price is not None
        and sale_price < list_price
    )

    stock_quantity = quantities.get(
        product_id,
        0.0,
    )

    active_esmeralda = (
        sku.get(
            "x_activeConfiancaEsmeralda"
        )
        is True
    )

    available = (
        active_esmeralda
        and stock_quantity > 0
    )

    image = (
        product.get(
            "primarySourceImageURL"
        )
        or product.get(
            "primaryLargeImageURL"
        )
        or product.get(
            "primaryFullImageURL"
        )
        or product.get(
            "primarySmallImageURL"
        )
    )

    route = product.get("route")
    product_url = None

    if isinstance(route, str) and route.strip():
        product_url = (
            site_base_url.rstrip("/")
            + "/"
            + route.strip().lstrip("/")
        )

    normalized = {
        "external_id": product_id,
        "name": product.get("displayName"),
        "barcode": sku.get("barcode"),
        "price": round(
            current_price,
            2,
        ),
        "regular_price": round(
            list_price,
            2,
        ),
        "sale_price": (
            round(sale_price, 2)
            if sale_price is not None
            else None
        ),
        "promotional": promotional,
        "available": available,
        "stock_quantity": stock_quantity,
        "image_url": absolute_url(image),
        "product_url": product_url,
        "unit_of_measurement": product.get(
            "x_unitOfMeasurement"
        ),
        "weight": product.get(
            "x_ProductWeightLiteracy"
        ),
        "source_category": category_key,
        "active_esmeralda": active_esmeralda,
    }

    return normalized, None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Coletor seguro do "
            "Confiança Marília."
        )
    )

    parser.add_argument(
        "--categoria",
        choices=sorted(CATEGORIES),
        default="alimentos_basicos",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Obrigatório nesta versão. "
            "Não envia dados."
        ),
    )

    parser.add_argument(
        "--visivel",
        action="store_true",
        help="Abre o navegador visível.",
    )

    parser.add_argument(
        "--limite",
        type=int,
        default=0,
        help=(
            "Limita os produtos no "
            "arquivo final."
        ),
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_env()

    if not args.dry_run:
        print(
            "ERRO: ingestão ainda "
            "não habilitada."
        )
        print("Execute com --dry-run.")
        return 2

    store_id = os.environ.get(
        "CONFIANCA_STORE_ID",
        "",
    ).strip()

    site_base_url = os.environ.get(
        "CONFIANCA_BASE_URL",
        "https://www.confianca.com.br/marilia",
    ).rstrip("/")

    if not store_id:
        print(
            "ERRO: CONFIANCA_STORE_ID "
            "não configurado."
        )
        return 2

    if not STATE_FILE.exists():
        print(
            "ERRO: sessão do Confiança "
            "não encontrada."
        )
        print(f"Esperado em: {STATE_FILE}")
        return 2

    category = CATEGORIES[
        args.categoria
    ]

    encoded_sort = SORT.replace(
        "|",
        "%7C",
    )

    category_url = (
        site_base_url
        + category["path"]
        + "?Ns="
        + encoded_sort
    )

    captured_products_url = None
    captured_catalog_navigation_id: Optional[str] = None
    captured_headers: Dict[str, str] = {}

    LOG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=not args.visivel,
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
            nonlocal captured_catalog_navigation_id
            nonlocal captured_headers

            catalog_match = re.search(
                (
                    r"/ccstore/v1/assembler/pages/"
                    r"Default/osf/catalog/_/(N-\\d+)"
                ),
                request.url,
            )

            if (
                catalog_match
                and captured_catalog_navigation_id is None
            ):
                captured_catalog_navigation_id = (
                    catalog_match.group(1)
                )

            if (
                "/ccstore/v1/products?"
                not in request.url
            ):
                return

            if "productIds=" not in request.url:
                return

            request_query = parse_qs(
                urlparse(request.url).query,
                keep_blank_values=True,
            )

            request_product_ids: List[str] = []

            for raw_value in request_query.get(
                "productIds",
                [],
            ):
                for product_id in raw_value.split(","):
                    product_id = product_id.strip()

                    if product_id.isdigit():
                        request_product_ids.append(
                            product_id
                        )

            if not request_product_ids:
                return

            if captured_products_url is not None:
                current_query = parse_qs(
                    urlparse(
                        captured_products_url
                    ).query,
                    keep_blank_values=True,
                )

                current_product_ids: List[str] = []

                for raw_value in current_query.get(
                    "productIds",
                    [],
                ):
                    for product_id in raw_value.split(","):
                        product_id = product_id.strip()

                        if product_id.isdigit():
                            current_product_ids.append(
                                product_id
                            )

                if (
                    len(request_product_ids)
                    <= len(current_product_ids)
                ):
                    return

            captured_products_url = request.url
            captured_headers = (
                request.all_headers()
            )

        page.on(
            "request",
            handle_request,
        )

        print(
            f"Abrindo categoria: "
            f"{args.categoria}"
        )

        page.goto(
            category_url,
            wait_until="domcontentloaded",
            timeout=90_000,
        )

        page.wait_for_timeout(20_000)

        if captured_products_url is None:
            page.evaluate(
                """
                window.scrollTo(
                    0,
                    document.body.scrollHeight
                )
                """
            )

            page.wait_for_timeout(10_000)

        if captured_products_url is None:
            page.reload(
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
                "ERRO: não foi possível "
                "capturar o contexto da loja."
            )

            return 3

        headers = replay_headers(
            captured_headers,
            category_url,
        )

        configured_navigation_id = category.get(
            "navigation_id"
        )

        all_product_ids: List[str] = []
        seen_ids: Set[str] = set()

        expected_total = None
        page_number = 0
        offset = 0

        def product_ids_from_url(
            products_url: Optional[str],
        ) -> List[str]:
            if not products_url:
                return []

            parsed_url = urlparse(
                products_url
            )

            query = parse_qs(
                parsed_url.query,
                keep_blank_values=True,
            )

            product_ids: List[str] = []
            local_seen: Set[str] = set()

            for raw_value in query.get(
                "productIds",
                [],
            ):
                for product_id in raw_value.split(","):
                    product_id = product_id.strip()

                    if not product_id.isdigit():
                        continue

                    if product_id in local_seen:
                        continue

                    local_seen.add(product_id)
                    product_ids.append(
                        product_id
                    )

            return product_ids

        if configured_navigation_id:
            navigation_id = (
                configured_navigation_id
                or captured_catalog_navigation_id
            )

            print(
                "Modo de paginação: "
                "catálogo assembler"
            )

            print(
                "Navigation ID utilizado: "
                f"{navigation_id}"
            )

            if (
                captured_catalog_navigation_id
                and captured_catalog_navigation_id
                != configured_navigation_id
            ):
                print(
                    "AVISO: o navigation_id "
                    "capturado é diferente "
                    "do configurado."
                )

            while True:
                page_number += 1

                catalog_url = (
                    f"{HOST}/ccstore/v1/"
                    f"assembler/pages/Default/"
                    f"osf/catalog/_/"
                    f"{navigation_id}"
                    f"?No={offset}"
                    f"&Nrpp={PAGE_SIZE}"
                    f"&Ns={encoded_sort}"
                )

                response = context.request.get(
                    catalog_url,
                    headers=headers,
                    timeout=90_000,
                )

                if not response.ok:
                    browser.close()

                    print(
                        "ERRO: catálogo retornou "
                        f"HTTP {response.status}."
                    )

                    return 4

                data = response.json()
                results = data.get(
                    "results",
                    {},
                )

                if not isinstance(
                    results,
                    dict,
                ):
                    results = {}

                if expected_total is None:
                    raw_total = results.get(
                        "totalNumRecs"
                    )

                    if isinstance(
                        raw_total,
                        int,
                    ):
                        expected_total = raw_total

                page_ids = extract_product_ids(
                    data
                )

                new_ids = 0

                for product_id in page_ids:
                    if product_id in seen_ids:
                        continue

                    seen_ids.add(product_id)
                    all_product_ids.append(
                        product_id
                    )
                    new_ids += 1

                print(
                    f"Página {page_number}: "
                    f"{len(page_ids)} IDs, "
                    f"{new_ids} novos, "
                    f"offset {offset}"
                )

                if not page_ids or new_ids == 0:
                    break

                if (
                    expected_total is not None
                    and len(all_product_ids)
                    >= expected_total
                ):
                    break

                if len(page_ids) < PAGE_SIZE:
                    break

                offset += PAGE_SIZE

                if page_number >= 100:
                    browser.close()

                    print(
                        "ERRO: limite de segurança "
                        "de páginas atingido."
                    )

                    return 5

        else:
            print(
                "Modo de paginação: "
                "páginas HTML da categoria"
            )

            products_url_template = (
                captured_products_url
            )

            while True:
                page_number += 1

                if offset == 0:
                    page_products_url = (
                        captured_products_url
                    )

                else:
                    captured_products_url = None

                    paginated_url = (
                        site_base_url
                        + category["path"]
                        + "?Ns="
                        + encoded_sort
                        + f"&No={offset}"
                        + f"&Nrpp={PAGE_SIZE}"
                    )

                    print(
                        "Abrindo página HTML: "
                        f"offset {offset}"
                    )

                    navigation_ok = False

                    for attempt in range(1, 4):
                        try:
                            print(
                                "Tentativa de navegação "
                                f"{attempt}/3"
                            )

                            page.goto(
                                paginated_url,
                                wait_until="commit",
                                timeout=120_000,
                            )

                            page.wait_for_timeout(
                                20_000
                            )

                            navigation_ok = True
                            break

                        except Exception as error:
                            print(
                                "AVISO: falha temporária "
                                "ao abrir a página."
                            )
                            print(
                                f"Tentativa {attempt}/3: "
                                f"{type(error).__name__}"
                            )

                            if attempt < 3:
                                try:
                                    page.goto(
                                        "about:blank",
                                        wait_until="commit",
                                        timeout=30_000,
                                    )
                                except Exception:
                                    pass

                                page.wait_for_timeout(
                                    5_000
                                )

                    if not navigation_ok:
                        browser.close()

                        print(
                            "ERRO: página não carregou "
                            "após 3 tentativas."
                        )
                        print(
                            f"Categoria: {args.categoria}"
                        )
                        print(
                            f"Offset: {offset}"
                        )

                        return 6

                    if captured_products_url is None:
                        page.evaluate(
                            """
                            window.scrollTo(
                                0,
                                document.body.scrollHeight
                            )
                            """
                        )

                        page.wait_for_timeout(
                            5_000
                        )

                    page_products_url = (
                        captured_products_url
                    )

                if not page_products_url:
                    print(
                        "Fim da paginação: "
                        "nenhuma requisição de "
                        "produtos foi encontrada."
                    )
                    break

                page_ids = product_ids_from_url(
                    page_products_url
                )

                new_ids = 0

                for product_id in page_ids:
                    if product_id in seen_ids:
                        continue

                    seen_ids.add(product_id)
                    all_product_ids.append(
                        product_id
                    )
                    new_ids += 1

                print(
                    f"Página {page_number}: "
                    f"{len(page_ids)} IDs, "
                    f"{new_ids} novos, "
                    f"offset {offset}"
                )

                if not page_ids:
                    break

                if new_ids == 0:
                    print(
                        "Fim da paginação: "
                        "a página repetiu produtos."
                    )
                    break

                if len(page_ids) < PAGE_SIZE:
                    break

                offset += PAGE_SIZE

                if page_number >= 100:
                    browser.close()

                    print(
                        "ERRO: limite de segurança "
                        "de páginas atingido."
                    )

                    return 5

            captured_products_url = (
                products_url_template
            )

        if (
            expected_total is not None
            and len(all_product_ids)
            != expected_total
        ):
            browser.close()

            print(
                "ERRO: quantidade coletada "
                "diferente do catálogo."
            )

            print(
                f"Esperado: {expected_total}"
            )

            print(
                "Encontrado: "
                f"{len(all_product_ids)}"
            )

            return 6

        products_by_id: Dict[
            str,
            Dict[str, Any],
        ] = {}

        quantities: Dict[str, float] = {}

        for start in range(
            0,
            len(all_product_ids),
            PAGE_SIZE,
        ):
            batch_ids = all_product_ids[
                start:start + PAGE_SIZE
            ]

            batch_number = (
                start // PAGE_SIZE
            ) + 1

            products_url = build_products_url(
                captured_products_url,
                batch_ids,
            )

            products_response = (
                context.request.get(
                    products_url,
                    headers=headers,
                    timeout=90_000,
                )
            )

            if not products_response.ok:
                browser.close()

                print(
                    "ERRO: consulta de produtos "
                    f"retornou HTTP "
                    f"{products_response.status}."
                )

                return 7

            products_data = (
                products_response.json()
            )

            product_items = (
                products_data.get(
                    "items",
                    [],
                )
            )

            if isinstance(
                product_items,
                list,
            ):
                for item in product_items:
                    if not isinstance(
                        item,
                        dict,
                    ):
                        continue

                    product_id = str(
                        item.get("id")
                        or item.get(
                            "repositoryId"
                        )
                        or ""
                    ).strip()

                    if product_id:
                        products_by_id[
                            product_id
                        ] = item

            stock_url = (
                f"{HOST}/ccstore/v1/"
                "stockStatus"
                "?fields="
                "productSkuInventoryDetails."
                "catRefId%2C"
                "productSkuInventoryDetails."
                "inStockQuantity"
                "&products="
                + ",".join(batch_ids)
                + "&expandStockDetails=true"
            )

            stock_response = (
                context.request.get(
                    stock_url,
                    headers=headers,
                    timeout=90_000,
                )
            )

            if not stock_response.ok:
                browser.close()

                print(
                    "ERRO: consulta de estoque "
                    f"retornou HTTP "
                    f"{stock_response.status}."
                )

                return 8

            quantities.update(
                stock_map(
                    stock_response.json()
                )
            )

            product_count = (
                len(product_items)
                if isinstance(
                    product_items,
                    list,
                )
                else 0
            )

            print(
                f"Lote {batch_number}: "
                f"{product_count} produtos"
            )

        browser.close()

    normalized: List[
        Dict[str, Any]
    ] = []

    skipped = {
        "sem_id": 0,
        "sem_sku": 0,
        "sem_preco": 0,
        "produto_nao_retornado": 0,
    }

    for product_id in all_product_ids:
        product = products_by_id.get(
            product_id
        )

        if product is None:
            skipped[
                "produto_nao_retornado"
            ] += 1
            continue

        item, reason = normalize_product(
            product,
            quantities,
            args.categoria,
            site_base_url,
        )

        if item is not None:
            normalized.append(item)

        elif reason in skipped:
            skipped[reason] += 1

    if args.limite > 0:
        normalized = normalized[
            :args.limite
        ]

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    output_file = (
        LOG_DIR
        / f"confianca_preview_{timestamp}.json"
    )

    available_products = sum(
        1
        for item in normalized
        if item["available"]
    )

    promotional_products = sum(
        1
        for item in normalized
        if item["promotional"]
    )

    output = {
        "generated_at": (
            datetime.now().isoformat()
        ),
        "dry_run": True,
        "store_id": store_id,
        "category": args.categoria,
        "category_url": category_url,
        "expected_total": expected_total,
        "ids_collected": len(
            all_product_ids
        ),
        "products_received": len(
            products_by_id
        ),
        "products_normalized": len(
            normalized
        ),
        "available_products": (
            available_products
        ),
        "promotional_products": (
            promotional_products
        ),
        "skipped": skipped,
        "products": normalized,
    }

    output_file.write_text(
        json.dumps(
            output,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print("=" * 60)
    print(
        "COLETA CONCLUÍDA "
        "EM MODO SEGURO"
    )
    print("=" * 60)

    print(
        "Total informado pelo catálogo: "
        f"{expected_total}"
    )

    print(
        f"IDs coletados: "
        f"{len(all_product_ids)}"
    )

    print(
        f"Produtos recebidos: "
        f"{len(products_by_id)}"
    )

    print(
        f"Produtos normalizados: "
        f"{len(normalized)}"
    )

    print(
        f"Disponíveis: "
        f"{available_products}"
    )

    print(
        f"Em promoção: "
        f"{promotional_products}"
    )

    print(f"Ignorados: {skipped}")
    print(f"Arquivo: {output_file}")

    print(
        "Nenhum dado foi enviado "
        "ao Lovable."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
