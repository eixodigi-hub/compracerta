#!/usr/bin/env python3

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup


BARCODE_KEYS = (
    "gtin",
    "ean",
    "barcode",
    "bar_code",
    "codigo_de_barras",
    "codigoBarras",
)


def normalizar_codigo(valor: Any) -> str:
    return re.sub(r"\D", "", str(valor or ""))


def gtin_valido(codigo: str) -> bool:
    codigo = normalizar_codigo(codigo)

    if len(codigo) not in (8, 12, 13, 14):
        return False

    corpo = codigo[:-1]
    verificador = int(codigo[-1])

    soma = 0
    for indice, caractere in enumerate(reversed(corpo)):
        peso = 3 if indice % 2 == 0 else 1
        soma += int(caractere) * peso

    calculado = (10 - soma % 10) % 10
    return calculado == verificador


def percorrer_json(valor: Any, caminho: str = "root"):
    encontrados = []

    if isinstance(valor, dict):
        for chave, item in valor.items():
            novo_caminho = f"{caminho}.{chave}"
            chave_normalizada = str(chave).lower().replace("-", "_")

            if any(termo.lower() in chave_normalizada for termo in BARCODE_KEYS):
                codigo = normalizar_codigo(item)

                encontrados.append(
                    {
                        "origem": novo_caminho,
                        "valor": str(item),
                        "codigo": codigo,
                        "valido": gtin_valido(codigo),
                    }
                )

            encontrados.extend(percorrer_json(item, novo_caminho))

    elif isinstance(valor, list):
        for indice, item in enumerate(valor):
            encontrados.extend(
                percorrer_json(item, f"{caminho}[{indice}]")
            )

    return encontrados


def contexto_html(html: str, codigo: str, margem: int = 100) -> str:
    posicao = html.find(codigo)

    if posicao < 0:
        return ""

    inicio = max(0, posicao - margem)
    fim = min(len(html), posicao + len(codigo) + margem)

    trecho = html[inicio:fim]
    trecho = re.sub(r"\s+", " ", trecho)

    return trecho


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Procura EAN, GTIN e barcode em uma página do Tauste."
    )
    parser.add_argument("url", help="URL pública de um produto do Tauste")
    args = parser.parse_args()

    sessao = requests.Session()
    sessao.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/138.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;"
                "q=0.9,image/avif,image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        }
    )

    print("=" * 70)
    print("DIAGNÓSTICO DE CÓDIGO DE BARRAS DO TAUSTE")
    print("=" * 70)
    print(f"URL: {args.url}")

    try:
        resposta = sessao.get(args.url, timeout=45)
        resposta.raise_for_status()
    except requests.RequestException as erro:
        print(f"\nERRO AO ABRIR A PÁGINA: {erro}")
        return 1

    html = resposta.text

    print(f"Status HTTP: {resposta.status_code}")
    print(f"Tamanho recebido: {len(html)} caracteres")
    print(f"Content-Type: {resposta.headers.get('content-type')}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    arquivo_html = Path("logs") / f"tauste_barcode_probe_{timestamp}.html"
    arquivo_html.write_text(html, encoding="utf-8")

    print(f"HTML salvo em: {arquivo_html.resolve()}")

    soup = BeautifulSoup(html, "html.parser")

    resultados_json = []

    for indice, script in enumerate(
        soup.find_all("script", attrs={"type": "application/ld+json"})
    ):
        conteudo = script.string or script.get_text(" ", strip=True)

        if not conteudo:
            continue

        try:
            dados = json.loads(conteudo)
        except json.JSONDecodeError:
            continue

        resultados_json.extend(
            percorrer_json(dados, f"json_ld[{indice}]")
        )

    padrao_chaves = re.compile(
        r"""(?ix)
        ["']?
        (gtin(?:8|12|13|14)?|ean(?:8|13)?|barcode|bar_code|
        codigo[_\-\s]?de[_\-\s]?barras|codigoBarras)
        ["']?
        \s*[:=]\s*
        ["']?
        ([0-9]{8,14})
        """
    )

    resultados_regex = []

    for correspondencia in padrao_chaves.finditer(html):
        codigo = normalizar_codigo(correspondencia.group(2))

        resultados_regex.append(
            {
                "origem": f"html.{correspondencia.group(1)}",
                "valor": correspondencia.group(2),
                "codigo": codigo,
                "valido": gtin_valido(codigo),
            }
        )

    todos_numeros = set(re.findall(r"(?<!\d)\d{8,14}(?!\d)", html))

    candidatos_validos = sorted(
        codigo
        for codigo in todos_numeros
        if gtin_valido(codigo)
    )

    consolidados = {}

    for item in resultados_json + resultados_regex:
        chave = (
            item["origem"],
            item["codigo"],
        )
        consolidados[chave] = item

    print("\n" + "=" * 70)
    print("CAMPOS EXPLÍCITOS ENCONTRADOS")
    print("=" * 70)

    if not consolidados:
        print("Nenhum campo explícito de EAN, GTIN ou barcode encontrado.")
    else:
        for item in consolidados.values():
            print(
                f"Origem: {item['origem']}\n"
                f"Valor: {item['valor']}\n"
                f"Código normalizado: {item['codigo']}\n"
                f"Checksum válido: {item['valido']}\n"
            )

    print("=" * 70)
    print("SEQUÊNCIAS NUMÉRICAS COM CHECKSUM GTIN VÁLIDO")
    print("=" * 70)

    if not candidatos_validos:
        print("Nenhum candidato com checksum válido encontrado no HTML.")
    else:
        for codigo in candidatos_validos[:50]:
            print(f"\nCandidato: {codigo}")
            print(f"Contexto: {contexto_html(html, codigo)}")

    print("\n" + "=" * 70)
    print("RESUMO")
    print("=" * 70)
    print(f"Campos explícitos: {len(consolidados)}")
    print(f"Candidatos GTIN válidos: {len(candidatos_validos)}")

    if consolidados or candidatos_validos:
        print("RESULTADO: existe informação candidata no código da página.")
    else:
        print(
            "RESULTADO: o EAN não aparece diretamente no HTML. "
            "Será necessário investigar as requisições internas da página."
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
