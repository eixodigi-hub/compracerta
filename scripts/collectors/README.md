# Coletor Tauste Marília

Coletor externo em Python para o **Tauste Delivery — Marília/SP**
(<https://tauste.com.br/marilia/>). Envia os produtos coletados para o
endpoint `/api/public/ingest-products` do projeto Compra Certa Marília.

O coletor **não roda** no frontend, em componentes React ou dentro de Edge
Functions — é um script standalone pensado para rodar em uma máquina do
mantenedor (Windows, Linux ou macOS) ou em um agendador.

## O que ele faz

- Percorre categorias públicas do site (arroz, feijão, café, leite, óleo,
  açúcar, macarrão, refrigerante, papel higiênico, detergente/lava-louça).
- Extrai nome, marca, URL, imagem, preço e código externo dos produtos.
- Deduplica por `external_id`, valida preços > 0 e envia em lotes de até
  50 produtos ao endpoint de ingestão.
- Suporta **dry-run**, limite de páginas/produtos/categorias e uma amostra
  opcional de enriquecimento pela página individual do produto.

## O que ele NÃO faz

- Não usa Selenium/Playwright.
- Não faz login no site.
- Não contorna CAPTCHA, bloqueios ou anti-bot. Se o site rejeitar o acesso
  (redirecionar para a home, retornar 403/429), o script **aborta**.
- Não associa produtos canônicos — isso é feito no painel administrativo
  em `/admin/pendentes`.

## Requisitos

- Python 3.11+ (usa `zoneinfo`).
- Windows: instale a base de fusos com `pip install tzdata` se necessário.

Instalação de dependências:

```powershell
python -m pip install -r scripts/collectors/requirements.txt
```

## Variáveis de ambiente

O script lê **exclusivamente** do ambiente. Nunca escreva os valores
reais no código ou no repositório.

| Variável                | Obrigatória | Descrição                                                                 |
| ----------------------- | ----------- | ------------------------------------------------------------------------- |
| `INGEST_SECRET`         | sim¹        | Segredo do endpoint `/api/public/ingest-products`.                        |
| `STORE_ID`              | sim¹        | UUID do mercado Tauste Marília (copie em `/admin/mercados`).              |
| `INGEST_URL`            | não         | Sobrescreve a URL padrão do endpoint (útil para ambiente dev).            |
| `REQUEST_DELAY_SECONDS` | não         | Intervalo entre requisições (default `1.5`).                              |
| `MAX_PRODUCTS`          | não         | Limite global de produtos por execução.                                   |
| `MAX_PAGES`             | não         | Máximo de páginas por categoria (default `20`).                           |
| `MAX_CATEGORIES`        | não         | Máximo de categorias processadas por execução.                            |
| `DRY_RUN`               | não         | `1`/`true` para não enviar nada ao backend.                               |

¹ Não obrigatórias em `--dry-run`.

## Uso (Windows / PowerShell)

Configure o ambiente uma vez:

```powershell
setx INGEST_SECRET "<segredo_do_backend>"
setx STORE_ID      "<uuid_do_mercado>"
```

Abra um **novo** terminal (o `setx` só afeta terminais novos) e rode:

```powershell
# Dry-run com uma categoria, 1 página e 5 produtos
$env:DRY_RUN="1"
python scripts\collectors\tauste_marilia.py --categoria arroz --paginas 1 --produtos 5

# Coleta real, todas as categorias, até 20 páginas cada
Remove-Item Env:DRY_RUN
python scripts\collectors\tauste_marilia.py

# Uma categoria específica com enriquecimento (amostra de 10 produtos)
python scripts\collectors\tauste_marilia.py --categoria feijao --enriquecer 10
```

## Uso (Linux / macOS)

```bash
export INGEST_SECRET="<segredo>"
export STORE_ID="<uuid>"
python3 scripts/collectors/tauste_marilia.py --dry-run --categoria arroz --paginas 1 --produtos 5
```

## Argumentos de linha de comando

```
--categoria NOME       Categoria (repita para várias). Sem valor = todas.
--paginas N            Máximo de páginas por categoria.
--produtos N           Limite global de produtos (0 = sem limite).
--categorias-limite N  Máximo de categorias processadas.
--enriquecer N         Enriquece N produtos consultando a página individual.
--dry-run              Não envia ao endpoint; apenas coleta e resume.
```

Categorias disponíveis: `arroz`, `feijao`, `cafe`, `leite`, `oleo`,
`acucar`, `macarrao`, `refrigerante`, `papel_higienico`, `detergente`.

## Comportamento em caso de bloqueio

Se o site responder redirecionando as páginas de categoria para a home
(`https://tauste.com.br/`) ou devolver `403`/`429`, o script:

1. registra um `ERROR` no log identificando a URL rejeitada,
2. encerra com código de saída **3** sem enviar nada,
3. **não** tenta trocar User-Agent, IP ou burlar a proteção.

## Observações técnicas descobertas na inspeção

- O Tauste roda **Magento 2**. Os produtos aparecem em `<li class="product-item">`.
- Nome: `strong.product-item-name a.product-item-link` (o texto interno é o
  nome completo; o `href` é a URL do produto).
- Marca: `strong.product-item-brand a.product-item-link`.
- Imagem: `img.product-image-photo` (`src` + `alt` com o SKU numérico).
- Preço final: `[data-price-type="finalPrice"] .price`.
- Preço "de" (quando em promoção): `[data-price-type="oldPrice"] .price`.
- Paginação: parâmetro `?p=N`; próxima página em `.pages-item-next a`.
- O código externo (`external_id`) sai do prefixo numérico da URL do
  produto (`/165317-arroz-...html`) **ou**, quando a URL é apenas o slug
  sem prefixo, do atributo `alt` da imagem — que o Magento preenche com o
  SKU numérico.

## Segurança

- Não commite `.env`, `INGEST_SECRET` ou `STORE_ID`.
- O `User-Agent` é transparente e identifica o projeto.
- O script obedece `REQUEST_DELAY_SECONDS` entre requisições; comece com
  valores conservadores (≥ 1.5s) para não sobrecarregar o site.
