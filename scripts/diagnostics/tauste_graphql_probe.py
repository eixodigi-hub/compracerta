#!/usr/bin/env python3

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests


GRAPHQL_URL = "https://tauste.com.br/graphql"
SKU = "5884"

HEADERS_BASE = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/138.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Origin": "https://tauste.com.br",
    "Referer": (
        "https://tauste.com.br/marilia/"
        "arroz-tio-jo-o-tipo-1-pacote-5000g.html"
    ),
}


def executar(
    query: str,
    variables: Optional[Dict[str, Any]] = None,
    usar_store: bool = True,
) -> Dict[str, Any]:
    headers = dict(HEADERS_BASE)

    if usar_store:
        headers["Store"] = "marilia"

    resposta = requests.post(
        GRAPHQL_URL,
        headers=headers,
        json={
            "query": query,
            "variables": variables or {},
        },
        timeout=45,
    )

    print(
        f"HTTP {resposta.status_code} "
        f"| Store header: {'marilia' if usar_store else 'não'}"
    )

    try:
        dados = resposta.json()
    except ValueError:
        print("Resposta não é JSON:")
        print(resposta.text[:1000])
        return {
            "_http_status": resposta.status_code,
            "_raw": resposta.text,
        }

    dados["_http_status"] = resposta.status_code
    return dados


def tipo_base(tipo: Optional[Dict[str, Any]]) -> Optional[str]:
    atual = tipo

    while atual:
        if atual.get("kind") in {"SCALAR", "ENUM", "OBJECT", "INTERFACE"}:
            return atual.get("kind")

        atual = atual.get("ofType")

    return None


def possui_argumento_obrigatorio(campo: Dict[str, Any]) -> bool:
    for argumento in campo.get("args") or []:
        tipo = argumento.get("type") or {}

        if (
            tipo.get("kind") == "NON_NULL"
            and argumento.get("defaultValue") is None
        ):
            return True

    return False


def encontrar_campos_candidatos(
    tipos: List[Optional[Dict[str, Any]]],
) -> List[Dict[str, str]]:
    termos = re.compile(
        r"(gtin|ean|barcode|bar_code|codigo.*barras|cod.*barra)",
        re.IGNORECASE,
    )

    encontrados = []

    for tipo in tipos:
        if not tipo:
            continue

        nome_tipo = tipo.get("name") or "tipo_desconhecido"

        for campo in tipo.get("fields") or []:
            nome_campo = campo.get("name") or ""

            if not termos.search(nome_campo):
                continue

            encontrados.append(
                {
                    "tipo": nome_tipo,
                    "campo": nome_campo,
                    "tipo_base": tipo_base(campo.get("type")) or "desconhecido",
                    "argumento_obrigatorio": str(
                        possui_argumento_obrigatorio(campo)
                    ),
                }
            )

    return encontrados


def main() -> int:
    print("=" * 70)
    print("DIAGNÓSTICO GRAPHQL DO TAUSTE")
    print("=" * 70)
    print(f"Endpoint: {GRAPHQL_URL}")
    print(f"SKU interno testado: {SKU}")

    consulta_produto = """
    query ProductProbe($sku: String!) {
      products(
        filter: {sku: {eq: $sku}}
        pageSize: 1
      ) {
        total_count
        items {
          __typename
          uid
          sku
          name
          url_key
        }
      }
    }
    """

    resultado_produto = executar(
        consulta_produto,
        {"sku": SKU},
        usar_store=True,
    )

    if resultado_produto.get("errors"):
        print("\nConsulta com Store: marilia retornou erro.")
        print(json.dumps(resultado_produto["errors"], indent=2, ensure_ascii=False))

        print("\nTentando sem o cabeçalho Store...")
        resultado_produto = executar(
            consulta_produto,
            {"sku": SKU},
            usar_store=False,
        )

    print("\n" + "=" * 70)
    print("RESULTADO DA CONSULTA DO PRODUTO")
    print("=" * 70)
    print(json.dumps(resultado_produto, indent=2, ensure_ascii=False)[:5000])

    consulta_schema = """
    query SchemaProbe {
      productInterface: __type(name: "ProductInterface") {
        name
        fields {
          name
          args {
            name
            defaultValue
            type {
              kind
              name
              ofType {
                kind
                name
                ofType {
                  kind
                  name
                }
              }
            }
          }
          type {
            kind
            name
            ofType {
              kind
              name
              ofType {
                kind
                name
              }
            }
          }
        }
      }

      simpleProduct: __type(name: "SimpleProduct") {
        name
        fields {
          name
          args {
            name
            defaultValue
            type {
              kind
              name
              ofType {
                kind
                name
                ofType {
                  kind
                  name
                }
              }
            }
          }
          type {
            kind
            name
            ofType {
              kind
              name
              ofType {
                kind
                name
              }
            }
          }
        }
      }
    }
    """

    resultado_schema = executar(
        consulta_schema,
        usar_store=True,
    )

    print("\n" + "=" * 70)
    print("CAMPOS CANDIDATOS NO SCHEMA")
    print("=" * 70)

    candidatos = []

    if resultado_schema.get("data"):
        candidatos = encontrar_campos_candidatos(
            [
                resultado_schema["data"].get("productInterface"),
                resultado_schema["data"].get("simpleProduct"),
            ]
        )

    if not candidatos:
        print("Nenhum campo chamado EAN, GTIN ou barcode foi encontrado.")
    else:
        for candidato in candidatos:
            print(
                f"Tipo: {candidato['tipo']}\n"
                f"Campo: {candidato['campo']}\n"
                f"Tipo base: {candidato['tipo_base']}\n"
                f"Exige argumento: "
                f"{candidato['argumento_obrigatorio']}\n"
            )

    campos_consultaveis = sorted(
        {
            item["campo"]
            for item in candidatos
            if item["tipo_base"] in {"SCALAR", "ENUM"}
            and item["argumento_obrigatorio"] == "False"
        }
    )

    resultado_campos = None

    if campos_consultaveis:
        selecao = "\n".join(campos_consultaveis)

        consulta_campos = f"""
        query BarcodeProbe($sku: String!) {{
          products(
            filter: {{sku: {{eq: $sku}}}}
            pageSize: 1
          ) {{
            total_count
            items {{
              __typename
              sku
              name
              {selecao}
            }}
          }}
        }}
        """

        print("=" * 70)
        print("CONSULTANDO CAMPOS CANDIDATOS")
        print("=" * 70)
        print(f"Campos: {', '.join(campos_consultaveis)}")

        resultado_campos = executar(
            consulta_campos,
            {"sku": SKU},
            usar_store=True,
        )

        print(
            json.dumps(
                resultado_campos,
                indent=2,
                ensure_ascii=False,
            )[:5000]
        )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    arquivo = Path("logs") / f"tauste_graphql_probe_{timestamp}.json"

    arquivo.write_text(
        json.dumps(
            {
                "produto": resultado_produto,
                "schema": resultado_schema,
                "campos_candidatos": candidatos,
                "resultado_campos": resultado_campos,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print("\n" + "=" * 70)
    print("RESUMO")
    print("=" * 70)

    produtos = (
        resultado_produto
        .get("data", {})
        .get("products", {})
    )

    print(f"Produto encontrado: {produtos.get('total_count', 0)}")
    print(f"Campos candidatos: {len(candidatos)}")
    print(f"Arquivo completo: {arquivo.resolve()}")

    if candidatos:
        print("RESULTADO: há campo candidato para código de barras.")
    else:
        print(
            "RESULTADO: o GraphQL não expõe um campo evidente de "
            "EAN/GTIN. O próximo passo será capturar as requisições "
            "internas do navegador."
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
