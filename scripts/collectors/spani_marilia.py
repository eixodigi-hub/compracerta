"""
Coletor externo para Spani Atacadista — loja de Marília/SP.

O site (spanionline.com.br) é uma SPA Angular sobre a plataforma
VipCommerce; não expõe HTML com os produtos, mas usa uma API JSON
pública em services-beta.vipcommerce.com.br. Este coletor fala
diretamente com essa API (sem navegador).

Uso rápido:

    export INGEST_SECRET="<segredo>"
    export SPANI_STORE_ID="<uuid do mercado Spani Marília>"
    python3 scripts/collectors/spani_marilia.py --dry-run --categoria hortifruti --paginas 2

Este script:
- Faz login com a chave pública do app da loja (o mesmo valor que
  qualquer visitante do site recebe embutido no bundle JS — não é um
  segredo de conta, é a credencial "app" do storefront).
- Coleta apenas o catálogo da filial de Marília (centro de distribuição
  23), identificada por inspeção da própria API pública.
- Aplica timeout e intervalo configurável entre requisições, com até 3
  tentativas em erros temporários (5xx / falha de rede).
- Interrompe a execução se a API rejeitar (401 além de uma nova
  tentativa de login, 403 ou 429) — não tenta burlar bloqueio algum.
- Envia os produtos ao endpoint /api/public/ingest-products em lotes
  de 50 e finaliza cada categoria via /api/public/finalize-category-sync.
"""

from __future__ import annotations

import argparse
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

BASE_SITE_URL = "https://www.spanionline.com.br"
API_BASE_URL = "https://services-beta.vipcommerce.com.br/api-admin/v1"
IMAGE_BASE_URL = (
    "https://produto-assets-vipcommerce-com-br.br-se1.magaluobjects.com/250x250"
)

# Identificadores da loja Spani Marília no VipCommerce, descobertos por
# inspeção da API pública em 2026-09 (GET .../loja/centros_distribuicoes/23
# retorna "Spani Marília", Av. João Ramalho 2400). "LOGIN_KEY" é a chave
# pública do app do storefront — o mesmo valor que o navegador de qualquer
# visitante busca e usa automaticamente; não é uma credencial de conta.
DOMAIN_KEY = "spanionline.com.br"
ORGANIZATION_ID = "67"
FILIAL_ID = "1"
CENTRO_DISTRIBUICAO_ID = "23"
LOGIN_USERNAME = "loja"
LOGIN_KEY = "df072f85df9bf7dd71b6811c34bdbaa4f219d98775b56cff9dfa5f8ca1bf8469"

DEFAULT_INGEST_URL = (
    "https://compra-certa-mar-lia.vercel.app/api/public/ingest-products"
)
DEFAULT_FINALIZE_URL = (
    "https://compra-certa-mar-lia.vercel.app/api/public/finalize-category-sync"
)

USER_AGENT = (
    "Mozilla/5.0 (compatible; CompraCertaMariliaBot/0.1; "
    "+https://compracertamarilia.local/bot; projeto Compra Certa Marília)"
)
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
BATCH_SIZE = 50
# Piso de segurança: nenhum departamento tinha mais de ~40 páginas na
# inspeção inicial. Se algum dia passar disso é sinal de algo errado
# (loop infinito, paginação quebrada), não catálogo legítimo.
HARD_PAGE_LIMIT = 150
TZ_SP = ZoneInfo("America/Sao_Paulo")

# classificacao_mercadologica_id (departamento) -> chave interna.
# Lista obtida em .../classificacoes_mercadologicas/departamentos/arvore.
CATEGORIES: dict[str, int] = {
    "pet": 1,
    "bazar_utilidades": 2,
    "bebidas": 3,
    "biscoitos_chocolates": 4,
    "carnes": 5,
    "cereais_farinaceos": 6,
    "congelados": 7,
    "frios_laticinios": 8,
    "hortifruti": 9,
    "limpeza": 10,
    "matinais_sobremesas": 11,
    "mercearia": 12,
    "padaria": 13,
    "perfumaria_higiene": 14,
}

RE_QTY = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(kg|g|mg|l|ml|un|und|unid|unidades?|pacote|pct|cx|caixa)\b",
    re.IGNORECASE,
)

log = logging.getLogger("spani")


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
# HTTP: autenticação e requisições com retry
# ---------------------------------------------------------------------------


class SiteRejectedError(RuntimeError):
    """Levantada quando a API sinaliza que a coleta automatizada foi rejeitada."""


class AuthError(RuntimeError):
    """Levantada quando o login na API pública falha."""


def build_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Accept-Language": "pt-BR,pt;q=0.9",
            "Content-Type": "application/json",
            "domainkey": DOMAIN_KEY,
            "organizationid": ORGANIZATION_ID,
        }
    )
    return s


def login(session: requests.Session) -> str:
    url = f"{API_BASE_URL}/org/{ORGANIZATION_ID}/auth/loja/login"
    resp = session.post(
        url,
        json={
            "domain": DOMAIN_KEY,
            "username": LOGIN_USERNAME,
            "key": LOGIN_KEY,
        },
        timeout=REQUEST_TIMEOUT,
    )
    if resp.status_code != 200:
        raise AuthError(
            f"Falha no login ({resp.status_code}): {resp.text[:300]}"
        )
    data = resp.json()
    token = data.get("data")
    if not token or not isinstance(token, str):
        raise AuthError("Resposta de login sem token utilizável.")
    return token


def get_json(
    session: requests.Session,
    url: str,
    params: dict,
    delay: float,
    relogin_once: bool = True,
) -> dict:
    """GET com retry exponencial. Reautentica uma vez em 401; aborta em 403/429."""
    last_exc: Exception | None = None
    tried_relogin = False

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.get(url, params=params, timeout=REQUEST_TIMEOUT)

            if resp.status_code == 401 and relogin_once and not tried_relogin:
                log.info("Token expirado, reautenticando...")
                token = login(session)
                session.headers["Authorization"] = f"Bearer {token}"
                tried_relogin = True
                continue

            if resp.status_code in (401, 403, 429):
                raise SiteRejectedError(
                    f"HTTP {resp.status_code} ao acessar {url}. "
                    "Coleta rejeitada. Abortando."
                )
            if resp.status_code >= 500:
                raise requests.HTTPError(f"HTTP {resp.status_code}")

            resp.raise_for_status()
            data = resp.json()

            if not data.get("success", True):
                raise requests.HTTPError(f"success=false: {data}")

            time.sleep(delay)
            return data
        except SiteRejectedError:
            raise
        except requests.RequestException as e:
            last_exc = e
            backoff = delay * (2 ** (attempt - 1))
            log.warning(
                "Falha (%s/%s) em %s: %s. Retentando em %.1fs",
                attempt, MAX_RETRIES, url, e, backoff,
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
    m = RE_QTY.search(name)
    if not m:
        return None, None
    qty = m.group(1).replace(",", ".")
    unit = m.group(2).lower()
    return qty, unit


def normalize_product(raw: dict, category_key: str) -> Produto | None:
    produto_id = raw.get("produto_id")
    name = (raw.get("descricao") or "").strip()
    if produto_id is None or not name:
        return None

    try:
        effective = round(float(raw.get("preco")), 2)
    except (TypeError, ValueError):
        return None
    if effective <= 0:
        return None

    regular = effective
    promotional = None
    if raw.get("em_oferta"):
        try:
            original = round(float(raw.get("preco_original")), 2)
        except (TypeError, ValueError):
            original = None
        if original and original > effective:
            regular = original
            promotional = effective

    link = raw.get("link") or ""
    product_url = f"{BASE_SITE_URL}/produto/{produto_id}/{link}" if link else None

    imagem = raw.get("imagem")
    image_url = f"{IMAGE_BASE_URL}/{imagem}" if imagem else None

    qty, unit = _extract_qty(name)
    now_iso = datetime.now(TZ_SP).isoformat()

    return Produto(
        external_id=str(produto_id),
        external_name=name,
        product_url=product_url,
        image_url=image_url,
        brand_raw=None,
        quantity_raw=qty,
        unit_raw=unit,
        barcode_raw=(raw.get("codigo_barras") or None),
        regular_price=regular,
        promotional_price=promotional,
        effective_price=effective,
        promotion_text=("Oferta Spani" if promotional is not None else None),
        promotion_end_at=None,
        available=bool(raw.get("disponivel", True)),
        collected_at=now_iso,
        origin_category=category_key,
    )


# ---------------------------------------------------------------------------
# Coleta de uma categoria (departamento)
# ---------------------------------------------------------------------------


def collect_category(
    session: requests.Session,
    key: str,
    departamento_id: int,
    max_pages: int,
    delay: float,
) -> tuple[list[Produto], bool]:
    url = (
        f"{API_BASE_URL}/org/{ORGANIZATION_ID}/filial/{FILIAL_ID}"
        f"/centro_distribuicao/{CENTRO_DISTRIBUICAO_ID}/loja"
        f"/classificacoes_mercadologicas/departamentos/{departamento_id}/produtos"
    )

    produtos: list[Produto] = []
    seen_ids: set[str] = set()
    page = 1
    total_pages: int | None = None

    while True:
        log.info("[%s] página %d -> %s", key, page, url)
        data = get_json(session, url, {"page": page}, delay)

        items = data.get("data") or []
        paginator = data.get("paginator") or {}
        total_pages = paginator.get("total_pages", total_pages)

        log.info(
            "[%s] página %d: %d produto(s) (total_pages=%s)",
            key, page, len(items), total_pages,
        )

        if not items:
            log.info("[%s] página %d vazia. Categoria concluída.", key, page)
            return produtos, True

        new_count = 0
        for raw in items:
            produto = normalize_product(raw, key)
            if produto is None or produto.external_id in seen_ids:
                continue
            seen_ids.add(produto.external_id)
            produtos.append(produto)
            new_count += 1

        if new_count == 0:
            log.info(
                "[%s] página %d sem produtos novos. Categoria concluída.",
                key, page,
            )
            return produtos, True

        if total_pages is not None and page >= total_pages:
            log.info(
                "[%s] última página (%d/%d) atingida. Categoria concluída.",
                key, page, total_pages,
            )
            return produtos, True

        if page >= max_pages or page >= HARD_PAGE_LIMIT:
            log.warning(
                "[%s] limite de %d página(s) atingido antes do fim real "
                "(total_pages=%s). Categoria não será finalizada.",
                key, max_pages, total_pages,
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
    p = argparse.ArgumentParser(description="Coletor Spani Marília")
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
    store_id = os.environ.get("SPANI_STORE_ID", "")
    secret = os.environ.get("INGEST_SECRET", "")
    delay = env_float("REQUEST_DELAY_SECONDS", 1.0)

    if not args.dry_run and (not store_id or not secret):
        log.error(
            "Defina SPANI_STORE_ID e INGEST_SECRET no ambiente (ou use --dry-run)."
        )
        return 2

    cats = args.categoria or list(CATEGORIES.keys())
    if args.categorias_limite:
        cats = cats[: args.categorias_limite]

    session = build_session()
    try:
        token = login(session)
    except AuthError as error:
        log.error("Falha de autenticação: %s", error)
        return 5
    session.headers["Authorization"] = f"Bearer {token}"

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
