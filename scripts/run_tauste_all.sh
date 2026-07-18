#!/usr/bin/env bash

set -u
set -o pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR" || exit 1

if [[ ! -f ".env" ]]; then
  echo "ERRO: arquivo .env não encontrado."
  exit 1
fi

set -a
source .env
set +a

for variable in INGEST_URL INGEST_SECRET STORE_ID; do
  if [[ -z "${!variable:-}" ]]; then
    echo "ERRO: variável $variable não configurada."
    exit 1
  fi
done

mkdir -p logs

# Limpeza automática de logs antigos
find logs -type f -name "*.log" -mtime +30 -delete 2>/dev/null || true

LOCK_DIR=".tauste_collection.lock"
LOCK_PID_FILE="$LOCK_DIR/pid"

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  OLD_PID=""

  if [[ -f "$LOCK_PID_FILE" ]]; then
    OLD_PID="$(cat "$LOCK_PID_FILE" 2>/dev/null || true)"
  fi

  if [[ -n "$OLD_PID" ]] && kill -0 "$OLD_PID" 2>/dev/null; then
    echo "ERRO: já existe uma coleta em execução, PID $OLD_PID."
    exit 1
  fi

  echo "AVISO: bloqueio antigo encontrado. Removendo automaticamente."
  rm -rf "$LOCK_DIR"

  if ! mkdir "$LOCK_DIR"; then
    echo "ERRO: não foi possível recriar o bloqueio."
    exit 1
  fi
fi

echo "$$" > "$LOCK_PID_FILE"

cleanup_lock() {
  rm -rf "$LOCK_DIR"
}

trap cleanup_lock EXIT INT TERM HUP

if [[ -x ".venv/bin/python" ]]; then
  PYTHON_BIN=".venv/bin/python"
else
  PYTHON_BIN="python3"
fi

CATEGORIES=(
  arroz
  feijao
  cafe
  leite
  oleo
  acucar
  macarrao
  refrigerante
  papel_higienico
  detergente
  farinha
  sal
  biscoitos
  conservas_enlatados
  creme_de_leite
  leite_condensado
  azeite_vinagre
  creme_dental
  fraldas
  iogurtes
)

PAGES="${PAGES:-1}"
CATEGORY_DELAY="${CATEGORY_DELAY:-5}"

START_TIME="$(date '+%Y-%m-%d %H:%M:%S')"
RUN_TIMESTAMP="$(date '+%Y%m%d_%H%M%S')"
SUMMARY_FILE="logs/resumo_${RUN_TIMESTAMP}.log"

SUCCESS_COUNT=0
FAILURE_COUNT=0

{
  echo "============================================================"
  echo "Coleta Tauste Marília"
  echo "Início: $START_TIME"
  echo "Páginas por categoria: $PAGES"
  echo "============================================================"
} | tee "$SUMMARY_FILE"

for category in "${CATEGORIES[@]}"; do
  LOG_FILE="logs/tauste_${category}_${RUN_TIMESTAMP}.log"

  echo ""
  echo "Iniciando categoria: $category"
  echo "Log: $LOG_FILE"

  "$PYTHON_BIN" scripts/collectors/tauste_marilia.py \
    --categoria "$category" \
    --paginas "$PAGES" \
    2>&1 | tee "$LOG_FILE"

  STATUS=${PIPESTATUS[0]}

  if [[ "$STATUS" -eq 0 ]]; then
    echo "SUCESSO: $category" | tee -a "$SUMMARY_FILE"
    SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
  else
    echo "FALHA: $category, código $STATUS" | tee -a "$SUMMARY_FILE"
    FAILURE_COUNT=$((FAILURE_COUNT + 1))
  fi

  sleep "$CATEGORY_DELAY"
done

END_TIME="$(date '+%Y-%m-%d %H:%M:%S')"

{
  echo ""
  echo "============================================================"
  echo "Resumo final"
  echo "Fim: $END_TIME"
  echo "Categorias concluídas: $SUCCESS_COUNT"
  echo "Categorias com falha: $FAILURE_COUNT"
  echo "============================================================"
} | tee -a "$SUMMARY_FILE"

if [[ "$FAILURE_COUNT" -gt 0 ]]; then
  exit 1
fi

exit 0
