"""
Coletor externo para Atacadão — loja de Marília/SP.

O site (atacadao.com.br) é uma loja VTEX (conta "atacadaobr630" — cada
loja física do Atacadão é seu próprio "seller" dentro do marketplace
VTEX, com preço e estoque específicos). Fala diretamente com a API
pública de busca (GraphQL) sem navegador e sem autenticação — o
endpoint aceita `operationName=ProductsQuery` com a query já
registrada no lado do servidor; não precisamos enviar o texto da
query, só `variables` (mesmo padrão observado em requisições reais do
site, capturadas por inspeção em 2026-09).

Uso rápido:

    export INGEST_SECRET="<segredo>"
    export ATACADAO_STORE_ID="<uuid do mercado Atacadão Marília>"
    python3 scripts/collectors/atacadao_marilia.py --dry-run --categoria mercearia --paginas 2

Este script:
- Não precisa de login — a API de busca do VTEX é pública; o preço
  específico da loja de Marília vem do parâmetro `channel` (seller
  "atacadaobr630", descoberto inspecionando
  https://www.atacadao.com.br/loja/marilia), sem depender de cookie
  de sessão.
- Coleta só os departamentos relevantes pra comparação de mercado
  (mercearia, bebidas, higiene, limpeza, pet, hortifrúti, carnes,
  padaria/matinais, frios/congelados, cafeteria) — o Atacadão também
  vende automotivo, eletrônicos, vestuário etc., fora do escopo do
  site.
- Aplica timeout e intervalo configurável entre requisições, com até 3
  tentativas em erros temporários (5xx / falha de rede).
- Interrompe a execução se a API rejeitar (403/429) — não tenta
  burlar bloqueio algum.
- Envia os produtos ao endpoint /api/public/ingest-products em lotes
  de 50 e finaliza cada categoria via /api/public/finalize-category-sync.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Iterable
from uuid import uuid4
from zoneinfo import ZoneInfo

import requests

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

BASE_SITE_URL = "https://www.atacadao.com.br"
API_URL = "https://www.atacadao.com.br/api/graphql"

# Identificadores da loja Atacadão Marília no VTEX, descobertos por
# inspeção da API pública em 2026-09 (GET
# apigw.cloud.carrefour.com.br/.../Store/marilia retorna storeId 630,
# extra01 "atacadaobr630" — o mesmo valor usado como `seller` nas
# buscas de produto feitas pelo próprio site quando em
# atacadao.com.br/loja/marilia). `regionId` é só o base64 de
# "SW#atacadaobr630" (não é segredo, o navegador de qualquer visitante
# calcula/recebe o mesmo valor).
SELLER_ID = "atacadaobr630"
SALES_CHANNEL = "1"
REGION_ID = "U1cjYXRhY2FkYW9icjYzMA=="

DEFAULT_INGEST_URL = (
    "https://compra-certa-mar-lia.vercel.app/api/public/ingest-products"
)
DEFAULT_FINALIZE_URL = (
    "https://compra-certa-mar-lia.vercel.app/api/public/finalize-category-sync"
)

USER_AGENT = (
    "Mozilla/5.0 (compatible; CompraCertaBot/0.1; "
    "+https://compracerta.local/bot; projeto Compra Certa)"
)
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
BATCH_SIZE = 50
PAGE_SIZE = 50
HARD_PAGE_LIMIT = 150
TZ_SP = ZoneInfo("America/Sao_Paulo")

# chave interna -> slug do departamento (facet "category-1"). Lista
# obtida em .../api/catalog_system/pub/category/tree/3. Só os
# departamentos relevantes pra um site de comparação de mercado —
# fora do escopo: automotivo, jardinagem, eletrônicos, papelaria,
# esporte e lazer, vestuário, utilidades domésticas, descartáveis.
CATEGORIES: dict[str, str] = {
    "mercearia": "mercearia",
    "bebidas": "bebidas",
    "perfumaria_higiene": "higiene-e-perfumaria",
    "limpeza": "limpeza",
    "pet_shop": "pet-shop",
    "hortifruti": "hortifruti",
    "carnes": "carnes-aves-e-peixes",
    "padaria_matinais": "padaria-e-matinais",
    "frios_congelados": "frios-e-congelados",
    "cafeteria": "cafeteria",
}

RE_QTY = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(kg|g|mg|l|ml|un|und|unid|unidades?|pacote|pct|cx|caixa)\b",
    re.IGNORECASE,
)

log = logging.getLogger("atacadao")


# ---------------------------------------------------------------------------
# Modelo de produto
# ---------------------------------------------------------------------------


@dataclass
class Produto:
    external_id: str
    external_name: str
    product_url: str | None
    image_url: str | None
    brand_raw: str | None
    quantity_raw: str | None
    unit_raw: str | None
    barcode_raw: str | None
    regular_price: float
    promotional_price: float | None
    effective_price: float
    promotion_text: str | None
    promotion_end_at: str | None
    available: bool
    collected_at: str
    # Metadado interno (não enviado ao endpoint).
    origin_category: str = field(default="", repr=False)

    def to_payload(self) -> dict:
        d = asdict(self)
        d["source_category"] = d.pop("origin_category", None)
        return d


# ---------------------------------------------------------------------------
# HTTP: requisições com retry (sem autenticação — a busca é pública)
# ---------------------------------------------------------------------------


class SiteRejectedError(RuntimeError):
    """Levantada quando a API sinaliza que a coleta automatizada foi rejeitada."""


def build_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Accept-Language": "pt-BR,pt;q=0.9",
        }
    )
    return s


def _channel_value() -> str:
    return json.dumps(
        {"salesChannel": SALES_CHANNEL, "seller": SELLER_ID, "regionId": REGION_ID}
    )


def get_json(
    session: requests.Session,
    variables: dict,
    delay: float,
) -> dict:
    """GET com retry exponencial. Aborta em 403/429."""
    last_exc: Exception | None = None
    params = {
        "operationName": "ProductsQuery",
        "variables": json.dumps(variables),
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.get(API_URL, params=params, timeout=REQUEST_TIMEOUT)

            if resp.status_code in (401, 403, 429):
                raise SiteRejectedError(
                    f"HTTP {resp.status_code} ao acessar {API_URL}. "
                    "Coleta rejeitada. Abortando."
                )
            if resp.status_code >= 500:
                raise requests.HTTPError(f"HTTP {resp.status_code}")

            resp.raise_for_status()
            data = resp.json()

            if data.get("errors"):
                raise requests.HTTPError(f"GraphQL errors: {data['errors']}")

            time.sleep(delay)
            return data
        except SiteRejectedError:
            raise
        except (requests.RequestException, ValueError) as e:
            last_exc = e
            backoff = delay * (2 ** (attempt - 1))
            log.warning(
                "Falha (%s/%s) em ProductsQuery: %s. Retentando em %.1fs",
                attempt, MAX_RETRIES, e, backoff,
            )
            time.sleep(backoff)

    assert last_exc is not None
    raise last_exc


# ---------------------------------------------------------------------------
# Normalização
# ---------------------------------------------------------------------------


def _extract_qty(name: str) -> tuple[str | None, str | None]:
    if not name:
        return None, None
    # Usa a ÚLTIMA ocorrência, não a primeira: nomes às vezes trazem
    # um número+unidade cedo que não é o tamanho da embalagem (ex.:
    # "Bebida Láctea Yopro 15g de Proteína ... 250ml" — "15g" é a
    # chamada nutricional, "250ml" no fim é o tamanho de verdade).
    matches = list(RE_QTY.finditer(name))
    if not matches:
        return None, None
    m = matches[-1]
    qty = m.group(1).replace(",", ".")
    unit = m.group(2).lower()
    return qty, unit


def normalize_product(node: dict, category_key: str) -> Produto | None:
    sku = node.get("sku")
    name = (node.get("name") or "").strip()
    if not sku or not name:
        return None

    offers = ((node.get("offers") or {}).get("offers")) or []
    if not offers:
        # Sem oferta de nenhum vendedor nesta busca (já filtrada pelo
        # seller da loja de Marília) = não vendido nesta loja agora.
        return None
    offer = offers[0]

    try:
        price = round(float(offer.get("price")), 2)
    except (TypeError, ValueError):
        return None
    if price <= 0:
        return None

    try:
        list_price = round(float(offer.get("listPrice")), 2)
    except (TypeError, ValueError):
        list_price = price

    promotional = None
    regular = price
    if list_price > price:
        regular = list_price
        promotional = price

    slug = node.get("slug") or ""
    product_url = f"{BASE_SITE_URL}/{slug}/p" if slug else None

    images = node.get("image") or []
    image_url = images[0].get("url") if images and images[0].get("url") else None

    brand = ((node.get("brand") or {}).get("brandName") or "").strip() or None
    barcode = (node.get("gtin") or "").strip() or None

    qty, unit = _extract_qty(name)
    now_iso = datetime.now(TZ_SP).isoformat()

    return Produto(
        external_id=str(sku),
        external_name=name,
        product_url=product_url,
        image_url=image_url,
        brand_raw=brand,
        quantity_raw=qty,
        unit_raw=unit,
        barcode_raw=barcode,
        regular_price=regular,
        promotional_price=promotional,
        effective_price=price,
        promotion_text=("Oferta Atacadão" if promotional is not None else None),
        promotion_end_at=None,
        available=True,
        collected_at=now_iso,
        origin_category=category_key,
    )


# ---------------------------------------------------------------------------
# Coleta de uma categoria (departamento)
# ---------------------------------------------------------------------------


def collect_category(
    session: requests.Session,
    key: str,
    category_slug: str,
    max_pages: int,
    delay: float,
) -> tuple[list[Produto], bool]:
    produtos: list[Produto] = []
    seen_ids: set[str] = set()
    page = 1
    offset = 0
    total_count: int | None = None

    while True:
        variables = {
            "first": PAGE_SIZE,
            "after": str(offset),
            "sort": "score_desc",
            "term": "",
            "selectedFacets": [
                {"key": "category-1", "value": category_slug},
                {"key": "channel", "value": _channel_value()},
                {"key": "locale", "value": "pt-BR"},
            ],
        }
        log.info("[%s] página %d (offset %d)", key, page, offset)
        data = get_json(session, variables, delay)

        search = (data.get("data") or {}).get("search") or {}
        products = search.get("products") or {}
        edges = products.get("edges") or []
        page_info = products.get("pageInfo") or {}
        total_count = page_info.get("totalCount", total_count)

        log.info(
            "[%s] página %d: %d produto(s) (total=%s)",
            key, page, len(edges), total_count,
        )

        if not edges:
            log.info("[%s] página %d vazia. Categoria concluída.", key, page)
            return produtos, True

        new_count = 0
        for edge in edges:
            node = edge.get("node") or {}
            produto = normalize_product(node, key)
            if produto is None or produto.external_id in seen_ids:
                continue
            seen_ids.add(produto.external_id)
            produtos.append(produto)
            new_count += 1

        offset += len(edges)

        if total_count is not None and offset >= total_count:
            log.info(
                "[%s] fim do catálogo (%d/%d) atingido. Categoria concluída.",
                key, offset, total_count,
            )
            return produtos, True

        if new_count == 0 and page > 1:
            log.info(
                "[%s] página %d sem produtos novos. Categoria concluída.",
                key, page,
            )
            return produtos, True

        if page >= max_pages or page >= HARD_PAGE_LIMIT:
            log.warning(
                "[%s] limite de %d página(s) atingido antes do fim real "
                "(total=%s). Categoria não será finalizada.",
                key, max_pages, total_count,
            )
            return produtos, False

        page += 1


# ---------------------------------------------------------------------------
# Envio ao endpoint
# ---------------------------------------------------------------------------


def dedupe(produtos: Iterable[Produto]) -> list[Produto]:
    seen: dict[tuple[str, str], Produto] = {}
    for produto in produtos:
        seen[(produto.origin_category, produto.external_id)] = produto
    return list(seen.values())


def send_batches(
    ingest_url: str,
    store_id: str,
    secret: str,
    produtos: list[Produto],
    dry_run: bool,
) -> dict:
    counts = {"batches": 0, "enviados": 0, "falhas": 0}
    if dry_run:
        log.info("DRY-RUN: %d produto(s) NÃO serão enviados.", len(produtos))
        for p in produtos[:5]:
            log.info(
                "  ex: id=%s nome=%s preço=%s",
                p.external_id, p.external_name[:60], p.effective_price,
            )
        return counts

    for i in range(0, len(produtos), BATCH_SIZE):
        chunk = produtos[i : i + BATCH_SIZE]
        payload = {
            "store_id": store_id,
            "products": [p.to_payload() for p in chunk],
        }
        try:
            resp = requests.post(
                ingest_url,
                headers={
                    "x-ingest-secret": secret,
                    "content-type": "application/json",
                },
                json=payload,
                timeout=120,
            )
            resp.raise_for_status()
            counts["batches"] += 1
            counts["enviados"] += len(chunk)
            log.info(
                "Lote %d enviado (%d itens): %s",
                counts["batches"], len(chunk), resp.json(),
            )
        except Exception as e:  # noqa: BLE001
            counts["falhas"] += 1
            log.error("Falha ao enviar lote: %s", e)
    return counts


def finalize_category_sync(
    finalize_url: str,
    store_id: str,
    secret: str,
    category_key: str,
    produtos: list[Produto],
) -> bool:
    seen_external_ids = sorted(
        {
            produto.external_id
            for produto in produtos
            if produto.origin_category == category_key
        }
    )

    if not seen_external_ids:
        log.warning(
            "[%s] finalização ignorada porque nenhum produto válido foi coletado.",
            category_key,
        )
        return False

    payload = {
        "store_id": store_id,
        "category_key": category_key,
        "seen_external_ids": seen_external_ids,
        "sync_token": f"{category_key}-{uuid4()}",
        "collected_at": datetime.now(TZ_SP).isoformat(),
    }

    try:
        response = requests.post(
            finalize_url,
            headers={
                "x-ingest-secret": secret,
                "content-type": "application/json",
            },
            json=payload,
            timeout=120,
        )
        response.raise_for_status()
        result = response.json()
        log.info("[%s] categoria finalizada: %s", category_key, result)
        return True
    except Exception as error:  # noqa: BLE001
        log.error("[%s] falha ao finalizar categoria: %s", category_key, error)
        return False


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def env_int(name: str, default: int) -> int:
    v = os.environ.get(name)
    try:
        return int(v) if v else default
    except ValueError:
        return default


def env_float(name: str, default: float) -> float:
    v = os.environ.get(name)
    try:
        return float(v) if v else default
    except ValueError:
        return default


def env_bool(name: str, default: bool = False) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "sim", "y", "s")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Coletor Atacadão Marília")
    p.add_argument(
        "--categoria", action="append", choices=list(CATEGORIES.keys()),
        help="Categoria a coletar (pode repetir). Sem valor = todas.",
    )
    p.add_argument(
        "--paginas", type=int, default=env_int("MAX_PAGES", 60),
        help="Máximo de páginas por categoria (default 60).",
    )
    p.add_argument(
        "--produtos", type=int, default=env_int("MAX_PRODUCTS", 0),
        help="Limite global de produtos (0 = sem limite).",
    )
    p.add_argument(
        "--categorias-limite", type=int, default=env_int("MAX_CATEGORIES", 0),
        help="Limite de categorias processadas (0 = sem limite).",
    )
    p.add_argument(
        "--dry-run", action="store_true", default=env_bool("DRY_RUN", False),
        help="Não envia nada ao endpoint.",
    )
    return p.parse_args()


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )
    args = parse_args()

    ingest_url = os.environ.get("INGEST_URL", DEFAULT_INGEST_URL)
    finalize_url = os.environ.get("FINALIZE_CATEGORY_URL", DEFAULT_FINALIZE_URL)
    store_id = os.environ.get("ATACADAO_STORE_ID", "")
    secret = os.environ.get("INGEST_SECRET", "")
    delay = env_float("REQUEST_DELAY_SECONDS", 1.0)

    if not args.dry_run and (not store_id or not secret):
        log.error(
            "Defina ATACADAO_STORE_ID e INGEST_SECRET no ambiente (ou use --dry-run)."
        )
        return 2

    cats = args.categoria or list(CATEGORIES.keys())
    if args.categorias_limite:
        cats = cats[: args.categorias_limite]

    session = build_session()

    all_products: list[Produto] = []
    category_complete: dict[str, bool] = {}
    encontrados = 0
    erros_categoria = 0

    for key in cats:
        try:
            items, completed = collect_category(
                session, key, CATEGORIES[key], args.paginas, delay,
            )
            category_complete[key] = completed
            encontrados += len(items)
            all_products.extend(items)
        except SiteRejectedError as error:
            log.error("BLOQUEIO detectado: %s", error)
            log.error("Encerrando execução conforme requisito de segurança.")
            return 3
        except Exception as error:  # noqa: BLE001
            category_complete[key] = False
            erros_categoria += 1
            log.exception("Erro ao coletar categoria %s: %s", key, error)

    antes = len(all_products)
    all_products = dedupe(all_products)
    ignorados = antes - len(all_products)

    limited_collection = args.produtos > 0
    if limited_collection:
        all_products = all_products[: args.produtos]

    log.info("=" * 60)
    log.info(
        "Resumo: encontrados=%d válidos=%d ignorados=%d categorias_com_erro=%d",
        encontrados, len(all_products), ignorados, erros_categoria,
    )

    counts = send_batches(ingest_url, store_id, secret, all_products, args.dry_run)
    log.info("Envio: %s", counts)

    if args.dry_run:
        log.info("DRY-RUN: nenhuma categoria será finalizada.")
        return 0

    if limited_collection:
        log.warning(
            "Finalização ignorada porque --produtos limita a coleta "
            "e não representa a categoria completa."
        )
        return 0

    if counts["falhas"] > 0:
        log.error("Finalização ignorada porque houve falha no envio de produtos.")
        return 1

    finalization_failures = 0
    for key in cats:
        produtos_categoria = [p for p in all_products if p.origin_category == key]

        if not category_complete.get(key, False):
            log.warning(
                "[%s] finalização ignorada porque a coleta não foi concluída.",
                key,
            )
            continue

        if not finalize_category_sync(
            finalize_url, store_id, secret, key, produtos_categoria,
        ):
            finalization_failures += 1

    if finalization_failures:
        log.error("Finalizações com falha: %d", finalization_failures)
        return 4

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
