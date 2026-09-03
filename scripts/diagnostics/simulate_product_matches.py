#!/usr/bin/env python3

import csv
import json
import os
import re
import sys
import unicodedata
from collections import defaultdict
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from dotenv import load_dotenv
import requests


CONFIANCA_STORE_ID = "4f97f5d6-6a17-46ab-bf63-b3724abef9ff"
TAUSTE_STORE_ID = "9cc4a9b1-5bc1-48e8-b3ff-c89fa7009b02"

STOPWORDS = {
    "de", "da", "do", "das", "dos",
    "com", "para", "por", "em",
    "pacote", "pct", "embalagem",
    "unidade", "unidades", "und",
    "produto",
}

FLAVORS = {
    "morango", "chocolate", "baunilha", "coco",
    "natural", "banana", "maracuja", "uva",
    "laranja", "limao", "frutas",
}


def env_first(*names: str) -> Optional[str]:
    for name in names:
        value = os.getenv(name)

        if value:
            return value.strip()

    return None


def normalize_text(value: Any) -> str:
    text = str(value or "").lower().strip()

    text = unicodedata.normalize("NFKD", text)
    text = "".join(
        char for char in text
        if not unicodedata.combining(char)
    )

    replacements = {
        "ç": "c",
        " lt ": " l ",
        " litro ": " l ",
        " litros ": " l ",
        " gramas ": " g ",
        " grama ": " g ",
        " quilos ": " kg ",
        " quilo ": " kg ",
        " unidades ": " un ",
        " unidade ": " un ",
    }

    text = f" {text} "

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def normalize_brand(value: Any) -> str:
    return normalize_text(value)


def extract_quantity(
    product: Dict[str, Any],
) -> Optional[Tuple[float, str]]:
    def convert_to_base(
        number: float,
        unit: str,
    ) -> Tuple[float, str]:
        unit = unit.lower()

        if unit in {"kg", "quilo", "quilos"}:
            return round(number * 1000, 3), "g"

        if unit in {"g", "grama", "gramas"}:
            return round(number, 3), "g"

        if unit in {"l", "lt", "litro", "litros"}:
            return round(number * 1000, 3), "ml"

        if unit == "ml":
            return round(number, 3), "ml"

        if unit in {"un", "und", "unidade", "unidades"}:
            return round(number, 3), "un"

        raise ValueError(f"Unidade desconhecida: {unit}")

    name = str(product.get("external_name") or "")
    quantity_raw = str(product.get("quantity_raw") or "")
    unit_raw = str(product.get("unit_raw") or "")

    # O nome tem prioridade porque pode revelar multipacks como 40X5g.
    sources = [
        name,
        f"{quantity_raw} {unit_raw}",
    ]

    multipack_pattern = re.compile(
        r"(?<!\d)"
        r"(\d+)\s*[xX]\s*"
        r"(\d+(?:[.,]\d+)?)\s*"
        r"(kg|quilo|quilos|g|grama|gramas|"
        r"l|lt|litro|litros|ml|"
        r"un|und|unidade|unidades)"
        r"\b",
        re.IGNORECASE,
    )

    single_pattern = re.compile(
        r"(?<!\d)"
        r"(\d+(?:[.,]\d+)?)\s*"
        r"(kg|quilo|quilos|g|grama|gramas|"
        r"l|lt|litro|litros|ml|"
        r"un|und|unidade|unidades)"
        r"\b",
        re.IGNORECASE,
    )

    for source in sources:
        source = unicodedata.normalize("NFKD", source)
        source = "".join(
            char
            for char in source
            if not unicodedata.combining(char)
        )

        multipack = multipack_pattern.search(source)

        if multipack:
            pack_count = int(multipack.group(1))
            amount_each = float(
                multipack.group(2).replace(",", ".")
            )
            unit = multipack.group(3)

            base_amount, base_unit = convert_to_base(
                amount_each,
                unit,
            )

            return (
                round(pack_count * base_amount, 3),
                base_unit,
            )

        single = single_pattern.search(source)

        if single:
            number = float(
                single.group(1).replace(",", ".")
            )
            unit = single.group(2)

            return convert_to_base(number, unit)

    return None


def name_without_quantity(value: Any) -> str:
    text = normalize_text(value)

    text = re.sub(
        r"\b\d+(?:[.,]\d+)?\s*"
        r"(kg|g|mg|l|lt|ml|un|und)\b",
        " ",
        text,
    )

    tokens = [
        token
        for token in text.split()
        if token not in STOPWORDS
    ]

    return " ".join(tokens)


def token_set(value: str) -> Set[str]:
    return {
        token
        for token in value.split()
        if token and token not in STOPWORDS
    }


def variant_tags(value: Any) -> Set[str]:
    text = normalize_text(value)
    tokens = set(text.split())
    tags: Set[str] = set()

    if "integral" in tokens:
        tags.add("integral")

    if "desnatado" in tokens:
        tags.add("desnatado")

    if "semidesnatado" in tokens:
        tags.add("semidesnatado")

    if "parboilizado" in tokens:
        tags.add("parboilizado")

    if "extraforte" in tokens or (
        "extra" in tokens and "forte" in tokens
    ):
        tags.add("extraforte")

    if "tradicional" in tokens:
        tags.add("tradicional")

    if "gourmet" in tokens:
        tags.add("gourmet")

    if "light" in tokens:
        tags.add("light")

    if "diet" in tokens:
        tags.add("diet")

    if (
        "zero" in tokens and "lactose" in tokens
    ) or (
        "sem" in tokens and "lactose" in tokens
    ):
        tags.add("zero_lactose")

    if "sem" in tokens and "sal" in tokens:
        tags.add("sem_sal")

    if "com" in tokens and "sal" in tokens:
        tags.add("com_sal")

    if re.search(r"\btipo\s*1\b", text):
        tags.add("tipo_1")

    if re.search(r"\btipo\s*2\b", text):
        tags.add("tipo_2")

    for flavor in FLAVORS:
        if flavor in tokens:
            tags.add(f"sabor_{flavor}")

    return tags


def variants_conflict(name_a: Any, name_b: Any) -> bool:
    tags_a = variant_tags(name_a)
    tags_b = variant_tags(name_b)

    groups = [
        {"integral", "desnatado", "semidesnatado"},
        {"parboilizado", "integral"},
        {"tradicional", "extraforte", "gourmet"},
        {"sem_sal", "com_sal"},
        {"tipo_1", "tipo_2"},
    ]

    for group in groups:
        selected_a = tags_a & group
        selected_b = tags_b & group

        if selected_a and selected_b and selected_a != selected_b:
            return True

    flavors_a = {
        tag for tag in tags_a
        if tag.startswith("sabor_")
    }

    flavors_b = {
        tag for tag in tags_b
        if tag.startswith("sabor_")
    }

    if flavors_a and flavors_b and flavors_a != flavors_b:
        return True

    if "zero_lactose" in tags_a and "zero_lactose" not in tags_b:
        return True

    if "zero_lactose" in tags_b and "zero_lactose" not in tags_a:
        return True

    return False


def calculate_score(
    confianca: Dict[str, Any],
    tauste: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    name_c = name_without_quantity(confianca.get("external_name"))
    name_t = name_without_quantity(tauste.get("external_name"))

    if not name_c or not name_t:
        return None

    quantity_c = extract_quantity(confianca)
    quantity_t = extract_quantity(tauste)

    if quantity_c and quantity_t and quantity_c != quantity_t:
        return None

    brand_c = normalize_brand(confianca.get("brand_raw"))
    brand_t = normalize_brand(tauste.get("brand_raw"))

    if brand_c and brand_t and brand_c != brand_t:
        return None

    if variants_conflict(
        confianca.get("external_name"),
        tauste.get("external_name"),
    ):
        return None

    tokens_c = token_set(name_c)
    tokens_t = token_set(name_t)

    intersection = tokens_c & tokens_t
    union = tokens_c | tokens_t

    if not intersection:
        return None

    sequence_score = SequenceMatcher(
        None,
        name_c,
        name_t,
    ).ratio()

    token_score = (
        len(intersection) / len(union)
        if union else 0.0
    )

    score = (
        sequence_score * 0.68
        + token_score * 0.32
    )

    brand_same = bool(
        brand_c and brand_t and brand_c == brand_t
    )

    quantity_same = bool(
        quantity_c and quantity_t and quantity_c == quantity_t
    )

    if brand_same:
        score += 0.06

    if quantity_same:
        score += 0.08

    score = min(score, 1.0)

    return {
        "score": round(score, 4),
        "sequence_score": round(sequence_score, 4),
        "token_score": round(token_score, 4),
        "brand_same": brand_same,
        "quantity_same": quantity_same,
        "quantity_confianca": quantity_c,
        "quantity_tauste": quantity_t,
        "name_confianca_normalized": name_c,
        "name_tauste_normalized": name_t,
    }


def build_rest_headers(supabase_key: str) -> Dict[str, str]:
    headers = {
        "apikey": supabase_key,
        "Accept": "application/json",
    }

    # Chaves antigas service_role/anon são JWTs.
    # Chaves novas sb_secret/sb_publishable devem ir em apikey.
    if not supabase_key.startswith("sb_"):
        headers["Authorization"] = f"Bearer {supabase_key}"

    return headers


def fetch_store_products(
    supabase_url: str,
    supabase_key: str,
    store_id: str,
) -> List[Dict[str, Any]]:
    fields = (
        "id,store_id,canonical_product_id,"
        "external_id,external_name,image_url,"
        "brand_raw,quantity_raw,unit_raw,"
        "barcode_raw,active,available"
    )

    endpoint = (
        f"{supabase_url.rstrip('/')}/rest/v1/store_products"
    )

    headers = build_rest_headers(supabase_key)

    products: List[Dict[str, Any]] = []
    page_size = 1000
    offset = 0

    while True:
        response = requests.get(
            endpoint,
            headers=headers,
            params={
                "select": fields,
                "store_id": f"eq.{store_id}",
                "limit": str(page_size),
                "offset": str(offset),
            },
            timeout=60,
        )

        if not response.ok:
            raise RuntimeError(
                "Erro ao consultar store_products: "
                f"HTTP {response.status_code} "
                f"{response.text[:500]}"
            )

        batch = response.json()

        if not isinstance(batch, list):
            raise RuntimeError(
                "Resposta inesperada do Supabase: "
                f"{str(batch)[:500]}"
            )

        products.extend(batch)

        if len(batch) < page_size:
            break

        offset += page_size

    return products


def main() -> int:
    load_dotenv()

    supabase_url = env_first(
        "SUPABASE_URL",
        "VITE_SUPABASE_URL",
    )

    supabase_key = env_first(
        "SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_SERVICE_KEY",
        "SUPABASE_KEY",
        "VITE_SUPABASE_PUBLISHABLE_KEY",
        "VITE_SUPABASE_ANON_KEY",
        "SUPABASE_ANON_KEY",
    )

    if not supabase_url or not supabase_key:
        print(
            "ERRO: não encontrei URL e chave do Supabase no .env."
        )
        print(
            "Variáveis aceitas: SUPABASE_URL, VITE_SUPABASE_URL, "
            "SUPABASE_SERVICE_ROLE_KEY, SUPABASE_KEY, "
            "VITE_SUPABASE_PUBLISHABLE_KEY ou SUPABASE_ANON_KEY."
        )
        return 1

    print("=" * 72)
    print("SIMULAÇÃO DE ASSOCIAÇÃO DE PRODUTOS")
    print("=" * 72)
    print("Nenhuma alteração será feita no banco.")

    print("\nCarregando produtos do Confiança...")
    confianca_products = fetch_store_products(
        supabase_url,
        supabase_key,
        CONFIANCA_STORE_ID,
    )

    print("Carregando produtos do Tauste...")
    tauste_products = fetch_store_products(
        supabase_url,
        supabase_key,
        TAUSTE_STORE_ID,
    )

    print(f"Confiança: {len(confianca_products)} produtos")
    print(f"Tauste: {len(tauste_products)} produtos")

    quantity_index: Dict[
        Optional[Tuple[float, str]],
        List[Dict[str, Any]],
    ] = defaultdict(list)

    for product in tauste_products:
        quantity_index[extract_quantity(product)].append(product)

    proposals: List[Dict[str, Any]] = []

    for index, confianca in enumerate(confianca_products, start=1):
        quantity = extract_quantity(confianca)

        if quantity:
            candidates = quantity_index.get(quantity, [])
        else:
            candidates = tauste_products

        scored = []

        for tauste in candidates:
            result = calculate_score(confianca, tauste)

            if not result:
                continue

            scored.append(
                {
                    "tauste": tauste,
                    **result,
                }
            )

        scored.sort(
            key=lambda item: item["score"],
            reverse=True,
        )

        best = scored[0] if scored else None
        second = scored[1] if len(scored) > 1 else None

        if not best:
            proposals.append(
                {
                    "status": "sem_correspondencia",
                    "confianca": confianca,
                    "tauste": None,
                    "score": 0,
                    "margin": 0,
                    "details": {},
                }
            )
            continue

        margin = (
            best["score"] - second["score"]
            if second else best["score"]
        )

        quantity_confianca = best.get("quantity_confianca")
        quantity_tauste = best.get("quantity_tauste")

        quantities_complete = (
            quantity_confianca is not None
            and quantity_tauste is not None
            and quantity_confianca == quantity_tauste
        )

        if (
            best["score"] >= 0.90
            and margin >= 0.05
            and quantities_complete
        ):
            status = "alta_confianca"
        elif best["score"] >= 0.78:
            status = "revisao_manual"
        else:
            status = "sem_correspondencia"

        proposals.append(
            {
                "status": status,
                "confianca": confianca,
                "tauste": best["tauste"],
                "score": best["score"],
                "margin": round(margin, 4),
                "details": {
                    key: value
                    for key, value in best.items()
                    if key != "tauste"
                },
                "second_score": (
                    second["score"] if second else None
                ),
            }
        )

        if index % 50 == 0:
            print(
                f"Analisados: {index}/{len(confianca_products)}"
            )

    tauste_best_for: Dict[str, Dict[str, Any]] = {}

    for proposal in proposals:
        tauste = proposal.get("tauste")

        if not tauste:
            continue

        tauste_id = tauste["id"]
        current = tauste_best_for.get(tauste_id)

        if (
            current is None
            or proposal["score"] > current["score"]
        ):
            tauste_best_for[tauste_id] = proposal

    for proposal in proposals:
        if proposal["status"] != "alta_confianca":
            continue

        tauste_id = proposal["tauste"]["id"]

        if tauste_best_for.get(tauste_id) is not proposal:
            proposal["status"] = "revisao_manual"
            proposal["motivo"] = (
                "mais de um produto do Confiança apontou "
                "para o mesmo produto do Tauste"
            )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_file = Path(
        f"logs/product_match_simulation_{timestamp}.json"
    )
    csv_file = Path(
        f"logs/product_match_simulation_{timestamp}.csv"
    )

    json_file.write_text(
        json.dumps(
            proposals,
            indent=2,
            ensure_ascii=False,
            default=str,
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
                "status",
                "score",
                "margem",
                "confianca_id",
                "confianca_nome",
                "confianca_marca",
                "confianca_quantidade",
                "tauste_id",
                "tauste_nome",
                "tauste_marca",
                "tauste_quantidade",
            ]
        )

        for proposal in proposals:
            confianca = proposal["confianca"]
            tauste = proposal.get("tauste") or {}

            writer.writerow(
                [
                    proposal["status"],
                    proposal["score"],
                    proposal["margin"],
                    confianca.get("id"),
                    confianca.get("external_name"),
                    confianca.get("brand_raw"),
                    extract_quantity(confianca),
                    tauste.get("id"),
                    tauste.get("external_name"),
                    tauste.get("brand_raw"),
                    extract_quantity(tauste) if tauste else None,
                ]
            )

    totals = defaultdict(int)

    for proposal in proposals:
        totals[proposal["status"]] += 1

    print("\n" + "=" * 72)
    print("RESUMO DA SIMULAÇÃO")
    print("=" * 72)
    print(f"Produtos do Confiança: {len(confianca_products)}")
    print(f"Produtos do Tauste: {len(tauste_products)}")
    print(
        f"Alta confiança: {totals['alta_confianca']}"
    )
    print(
        f"Revisão manual: {totals['revisao_manual']}"
    )
    print(
        f"Sem correspondência: "
        f"{totals['sem_correspondencia']}"
    )

    print("\nEXEMPLOS DE ALTA CONFIANÇA")
    print("-" * 72)

    examples = [
        proposal
        for proposal in proposals
        if proposal["status"] == "alta_confianca"
    ][:20]

    if not examples:
        print("Nenhuma associação de alta confiança encontrada.")
    else:
        for proposal in examples:
            print(
                f"\nConfiança: "
                f"{proposal['confianca']['external_name']}"
            )
            print(
                f"Tauste: "
                f"{proposal['tauste']['external_name']}"
            )
            print(
                f"Score: {proposal['score']} "
                f"| Margem: {proposal['margin']}"
            )

    print("\nArquivos:")
    print(f"JSON: {json_file.resolve()}")
    print(f"CSV:  {csv_file.resolve()}")
    print("\nRESULTADO: SOMENTE SIMULAÇÃO. BANCO NÃO ALTERADO.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
