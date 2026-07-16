"""
Coletor externo para Tauste Delivery — loja de Marília/SP.

Uso rápido (Windows PowerShell):

    setx INGEST_SECRET "<segredo>"
    setx STORE_ID "<uuid do mercado Tauste Marília>"
    setx DRY_RUN "1"
    python scripts/collectors/tauste_marilia.py --categoria arroz --paginas 1 --produtos 5

Este script:
- Coleta apenas páginas públicas (sem login, sem burlar CAPTCHA/anti-bot).
- Usa User-Agent transparente identificando o projeto.
- Aplica timeout e intervalo configurável entre requisições.
- Faz até 3 tentativas em erros temporários (5xx / falha de rede).
- Interrompe a execução se o site rejeitar (redirecionar para a home).
- Envia os produtos ao endpoint /api/public/ingest-products em lotes de 50.
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Iterable
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

BASE_URL = "https://tauste.com.br/marilia/"
DEFAULT_INGEST_URL = (
    "https://project--0848491c-2052-4001-80d7-0f52822c8772.lovable.app"
    "/api/public/ingest-products"
)
USER_AGENT = (
    "Mozilla/5.0 (compatible; CompraCertaMariliaBot/0.1; "
    "+https://compracertamarilia.local/bot; projeto Compra Certa Marília)"
)
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
BATCH_SIZE = 50
TZ_SP = ZoneInfo("America/Sao_Paulo")

# Categorias suportadas nesta primeira versão.
# Caminhos confirmados por inspeção do HTML público em 2026-07.
CATEGORIES: dict[str, str] = {
    "arroz": "mercearia/alimentos-basicos/arroz.html",
    "feijao": "mercearia/alimentos-basicos/feij-o.html",
    "cafe": "mercearia/matinais/cafes.html",
    "leite": "leites/leite-longa-vida.html",
    "oleo": "mercearia/alimentos-basicos/oleo.html",
    "acucar": "mercearia/alimentos-basicos/acucar.html",
    "macarrao": "mercearia/massas/macarr-o-geral.html",
    "refrigerante": "bebidas-n-o-alcoolicas/sucos-refrescos-e-refrigerantes/refrigerantes.html",
    "papel_higienico": "higiene-e-beleza/higiene/papel-higi-nico.html",
    "detergente": "limpeza/cozinha/lava-louca.html",
    # obs.: o Tauste não expõe uma categoria única chamada "Detergente".
    # "lava-louca" agrupa detergentes de louça; ajuste caso queira outro recorte.
}

# Regex utilitárias.
RE_URL_ID = re.compile(r"/(\d+)-[^/]+\.html$")
RE_NUM = re.compile(r"^\d+$")
RE_QTY = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(kg|g|mg|l|ml|un|und|unid|unidades?|pacote|pct|cx|caixa)\b",
    re.IGNORECASE,
)

log = logging.getLogger("tauste")


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
    # Metadados internos (não enviados ao endpoint).
    origin_category: str = field(default="", repr=False)
    origin_page: int = field(default=0, repr=False)

    def to_payload(self) -> dict:
        d = asdict(self)
        d.pop("origin_category", None)
        d.pop("origin_page", None)
        return d


# ---------------------------------------------------------------------------
# HTTP com retry e detecção de bloqueio
# ---------------------------------------------------------------------------


class SiteRejectedError(RuntimeError):
    """Levantada quando o site sinaliza que a coleta automatizada foi rejeitada."""


def build_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "pt-BR,pt;q=0.9",
        }
    )
    return s


def get_html(session: requests.Session, url: str, delay: float) -> str:
    """GET com retry exponencial. Aborta se o servidor redirecionar para a home."""
    last_exc: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            # Bloqueio silencioso: o Tauste responde 200 mas redireciona pedidos
            # de categoria para "https://tauste.com.br/" quando o cliente é
            # identificado como automatizado. Trate isso como rejeição.
            final = resp.url.rstrip("/")
            requested_path = urlparse(url).path.rstrip("/")
            final_path = urlparse(final).path.rstrip("/")
            if requested_path and final_path != requested_path and final_path in ("", "/marilia"):
                raise SiteRejectedError(
                    f"O site redirecionou {url} para {resp.url}. "
                    "Coleta automatizada aparentemente rejeitada. Abortando."
                )
            if resp.status_code >= 500:
                raise requests.HTTPError(f"HTTP {resp.status_code}")
            if resp.status_code == 403 or resp.status_code == 429:
                raise SiteRejectedError(
                    f"HTTP {resp.status_code} ao acessar {url}. Coleta rejeitada. Abortando."
                )
            resp.raise_for_status()
            time.sleep(delay)
            return resp.text
        except SiteRejectedError:
            raise
        except (requests.RequestException,) as e:
            last_exc = e
            backoff = delay * (2 ** (attempt - 1))
            log.warning("Falha (%s/%s) em %s: %s. Retentando em %.1fs",
                        attempt, MAX_RETRIES, url, e, backoff)
            time.sleep(backoff)
    assert last_exc is not None
    raise last_exc


# ---------------------------------------------------------------------------
# Extração
# ---------------------------------------------------------------------------


def _text(node) -> str | None:
    if node is None:
        return None
    t = node.get_text(" ", strip=True)
    return t or None


def _parse_price(txt: str | None) -> float | None:
    if not txt:
        return None
    m = re.search(r"([\d\.]+,\d{2}|\d+\.\d{2}|\d+)", txt.replace("\xa0", " "))
    if not m:
        return None
    raw = m.group(1)
    # "1.234,56" -> "1234.56"
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    try:
        return round(float(raw), 2)
    except ValueError:
        return None


def _extract_id(product_url: str | None, img_alt: str | None) -> str | None:
    if product_url:
        m = RE_URL_ID.search(urlparse(product_url).path)
        if m:
            return m.group(1)
    # Fallback: o Tauste coloca o SKU numérico no atributo alt da imagem
    # quando a URL do produto não tem prefixo numérico.
    if img_alt and RE_NUM.match(img_alt.strip()):
        return img_alt.strip()
    return None


def _extract_qty(name: str) -> tuple[str | None, str | None]:
    if not name:
        return None, None
    m = RE_QTY.search(name)
    if not m:
        return None, None
    qty = m.group(1).replace(",", ".")
    unit = m.group(2).lower()
    return qty, unit


def parse_category_page(html: str, page: int, category: str) -> list[Produto]:
    soup = BeautifulSoup(html, "lxml")
    items = soup.select("li.product-item")
    now_iso = datetime.now(TZ_SP).isoformat()
    out: list[Produto] = []
    for it in items:
        name_a = it.select_one("strong.product-item-name a.product-item-link")
        brand_a = it.select_one("strong.product-item-brand a.product-item-link")
        photo_a = it.select_one("a.product-item-photo")
        img = it.select_one("img.product-image-photo")

        product_url = None
        if name_a and name_a.get("href"):
            product_url = name_a["href"]
        elif photo_a and photo_a.get("href"):
            product_url = photo_a["href"]
        if product_url:
            product_url = urljoin(BASE_URL, product_url)

        name = _text(name_a)
        if not name:
            continue

        img_url = img.get("src") if img else None
        if img_url:
            img_url = urljoin(BASE_URL, img_url)
        img_alt = img.get("alt") if img else None

        ext_id = _extract_id(product_url, img_alt)
        if not ext_id:
            log.warning("Produto sem código numérico identificável: %s", product_url)
            continue

        # Preços: Magento expõe finalPrice/oldPrice via data-price-type.
        final_el = it.select_one("[data-price-type=finalPrice] .price")
        old_el = it.select_one("[data-price-type=oldPrice] .price")
        # Fallback geral quando o box tem apenas um preço.
        any_price_el = it.select_one(".price-box .price")

        final_price = _parse_price(_text(final_el)) or _parse_price(_text(any_price_el))
        old_price = _parse_price(_text(old_el))

        if final_price is None or final_price <= 0:
            log.debug("Ignorado sem preço válido: %s", product_url)
            continue

        if old_price and old_price > final_price:
            regular = old_price
            promotional = final_price
            effective = final_price
        else:
            regular = final_price
            promotional = None
            effective = final_price

        qty, unit = _extract_qty(name)
        brand = _text(brand_a)

        out.append(
            Produto(
                external_id=ext_id,
                external_name=name,
                product_url=product_url,
                image_url=img_url,
                brand_raw=brand,
                quantity_raw=qty,
                unit_raw=unit,
                barcode_raw=None,
                regular_price=regular,
                promotional_price=promotional,
                effective_price=effective,
                promotion_text=None,
                promotion_end_at=None,
                available=True,
                collected_at=now_iso,
                origin_category=category,
                origin_page=page,
            )
        )
    return out


# ---------------------------------------------------------------------------
# Enriquecimento opcional pela página do produto
# ---------------------------------------------------------------------------


def enrich_from_product_page(
    session: requests.Session, produto: Produto, delay: float
) -> tuple[Produto, str | None]:
    """
    Confirma dados na página individual. Retorna (produto_ajustado, conflito|None).

    Se o COD da página divergir do external_id, retorna um aviso e o produto
    NÃO deve ser enviado até revisão.
    """
    if not produto.product_url:
        return produto, None
    try:
        html = get_html(session, produto.product_url, delay)
    except Exception as e:  # noqa: BLE001
        log.warning("Falha ao enriquecer %s: %s", produto.product_url, e)
        return produto, None

    soup = BeautifulSoup(html, "lxml")

    # COD: o Tauste mostra "COD: 12345" na ficha do produto.
    cod_text = None
    for node in soup.find_all(string=re.compile(r"\bCOD\b", re.IGNORECASE)):
        m = re.search(r"COD[:\s]*([0-9]+)", node, re.IGNORECASE)
        if m:
            cod_text = m.group(1)
            break
    conflito = None
    if cod_text and cod_text != produto.external_id:
        conflito = (
            f"COD divergente: url={produto.external_id} pagina={cod_text} "
            f"({produto.product_url})"
        )

    # Estoque: procura por "Em estoque" / "Fora de estoque".
    stock_span = soup.select_one(".stock, .product-info-stock-sku .stock")
    stock_txt = _text(stock_span) or ""
    if "fora" in stock_txt.lower() or "indisponível" in stock_txt.lower():
        produto.available = False

    # Preço/imagem/marca da página individual — apenas complementam.
    final_el = soup.select_one("[data-price-type=finalPrice] .price")
    price = _parse_price(_text(final_el))
    if price and price > 0:
        produto.effective_price = price
        if produto.promotional_price is None:
            produto.regular_price = price

    return produto, conflito


# ---------------------------------------------------------------------------
# Coleta de uma categoria
# ---------------------------------------------------------------------------


def collect_category(
    session: requests.Session,
    key: str,
    path: str,
    max_pages: int,
    delay: float,
) -> list[Produto]:
    url_base = urljoin(BASE_URL, path)
    produtos: list[Produto] = []
    page = 1
    while page <= max_pages:
        url = url_base if page == 1 else f"{url_base}?p={page}"
        log.info("[%s] página %d -> %s", key, page, url)
        html = get_html(session, url, delay)
        page_items = parse_category_page(html, page, key)
        log.info("[%s] página %d: %d produtos", key, page, len(page_items))
        if not page_items:
            break
        produtos.extend(page_items)
        # Detecta próxima página.
        soup = BeautifulSoup(html, "lxml")
        next_link = soup.select_one(".pages-item-next a, a.action.next")
        if not next_link:
            break
        page += 1
    return produtos


# ---------------------------------------------------------------------------
# Envio ao endpoint
# ---------------------------------------------------------------------------


def dedupe(produtos: Iterable[Produto]) -> list[Produto]:
    seen: dict[str, Produto] = {}
    for p in produtos:
        seen[p.external_id] = p  # mantém a última ocorrência
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
                "  ex: id=%s nome=%s preço=%s marca=%s",
                p.external_id, p.external_name[:60], p.effective_price, p.brand_raw,
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
            log.info("Lote %d enviado (%d itens): %s",
                     counts["batches"], len(chunk), resp.json())
        except Exception as e:  # noqa: BLE001
            counts["falhas"] += 1
            log.error("Falha ao enviar lote: %s", e)
    return counts


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
    p = argparse.ArgumentParser(description="Coletor Tauste Marília")
    p.add_argument("--categoria", action="append", choices=list(CATEGORIES.keys()),
                   help="Categoria a coletar (pode repetir). Sem valor = todas.")
    p.add_argument("--paginas", type=int, default=env_int("MAX_PAGES", 20),
                   help="Máximo de páginas por categoria (default 20).")
    p.add_argument("--produtos", type=int, default=env_int("MAX_PRODUCTS", 0),
                   help="Limite global de produtos (0 = sem limite).")
    p.add_argument("--categorias-limite", type=int,
                   default=env_int("MAX_CATEGORIES", 0),
                   help="Limite de categorias processadas (0 = sem limite).")
    p.add_argument("--enriquecer", type=int, default=0,
                   help="Enriquece N produtos pela página individual (amostra).")
    p.add_argument("--dry-run", action="store_true",
                   default=env_bool("DRY_RUN", False),
                   help="Não envia nada ao endpoint.")
    return p.parse_args()


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )
    args = parse_args()

    ingest_url = os.environ.get("INGEST_URL", DEFAULT_INGEST_URL)
    store_id = os.environ.get("STORE_ID", "")
    secret = os.environ.get("INGEST_SECRET", "")
    delay = env_float("REQUEST_DELAY_SECONDS", 1.5)

    if not args.dry_run and (not store_id or not secret):
        log.error("Defina STORE_ID e INGEST_SECRET no ambiente (ou use --dry-run).")
        return 2

    cats = args.categoria or list(CATEGORIES.keys())
    if args.categorias_limite:
        cats = cats[: args.categorias_limite]

    session = build_session()
    all_products: list[Produto] = []
    encontrados = ignorados = 0
    erros_categoria = 0

    for key in cats:
        try:
            items = collect_category(
                session, key, CATEGORIES[key], args.paginas, delay
            )
            encontrados += len(items)
            all_products.extend(items)
        except SiteRejectedError as e:
            log.error("BLOQUEIO detectado: %s", e)
            log.error("Encerrando execução conforme requisito de segurança.")
            return 3
        except Exception as e:  # noqa: BLE001
            erros_categoria += 1
            log.exception("Erro ao coletar categoria %s: %s", key, e)

    # Dedup e validações finais.
    antes = len(all_products)
    all_products = dedupe(all_products)
    ignorados += antes - len(all_products)
    all_products = [p for p in all_products if p.effective_price > 0]
    ignorados += (antes - len(all_products)) - ignorados

    if args.produtos > 0:
        all_products = all_products[: args.produtos]

    # Enriquecimento opcional (amostra) — apenas para novos/desconhecidos.
    conflitos: list[str] = []
    if args.enriquecer > 0:
        amostra = all_products[: args.enriquecer]
        log.info("Enriquecendo %d produto(s) pela página individual...", len(amostra))
        for p in amostra:
            _, conflito = enrich_from_product_page(session, p, delay)
            if conflito:
                conflitos.append(conflito)
        if conflitos:
            log.warning("Conflitos de COD detectados: %d", len(conflitos))
            for c in conflitos:
                log.warning("  %s", c)
            # Remove produtos com conflito da fila de envio.
            bad_ids = {c.split("url=")[1].split(" ")[0] for c in conflitos}
            all_products = [p for p in all_products if p.external_id not in bad_ids]

    log.info("=" * 60)
    log.info("Resumo: encontrados=%d válidos=%d ignorados=%d categorias_com_erro=%d conflitos=%d",
             encontrados, len(all_products), ignorados, erros_categoria, len(conflitos))

    counts = send_batches(ingest_url, store_id, secret, all_products, args.dry_run)
    log.info("Envio: %s", counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
