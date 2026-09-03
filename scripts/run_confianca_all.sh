#!/bin/bash

set -u
set -o pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -x "$PROJECT_DIR/.venv/bin/python" ]]; then
    PYTHON="$PROJECT_DIR/.venv/bin/python"
else
    PYTHON="python3"
fi

LOG_DIR="$PROJECT_DIR/logs"
LOCK_DIR="$PROJECT_DIR/.confianca_collection.lock"

mkdir -p "$LOG_DIR"
cd "$PROJECT_DIR" || exit 1

remove_lock() {
    rm -rf "$LOCK_DIR"
}

if [[ -d "$LOCK_DIR" ]]; then
    OLD_PID=""

    if [[ -f "$LOCK_DIR/pid" ]]; then
        OLD_PID="$(cat "$LOCK_DIR/pid" 2>/dev/null || true)"
    fi

    if [[ -n "$OLD_PID" ]] && kill -0 "$OLD_PID" 2>/dev/null; then
        echo "Já existe uma coleta do Confiança em execução."
        echo "PID: $OLD_PID"
        exit 10
    fi

    echo "Removendo trava antiga do Confiança."
    rm -rf "$LOCK_DIR"
fi

mkdir "$LOCK_DIR"
echo "$$" > "$LOCK_DIR/pid"
trap remove_lock EXIT INT TERM

if ! command -v "$PYTHON" >/dev/null 2>&1; then
    echo "ERRO: nenhum interpretador Python encontrado ($PYTHON)."
    exit 11
fi

# Mesmas chaves de scripts/collectors/confianca_marilia.py::CATEGORIES.
CATEGORIES=(
    alimentos_basicos
    matinais
    padaria
    hortifruti
    acougue
    emporium
    bebidas
    higiene_beleza
    marcas_exclusivas
    pet_shop
)

CATEGORY_DELAY="${CATEGORY_DELAY:-5}"

RUN_TIMESTAMP="$(date '+%Y%m%d_%H%M%S')"
SUMMARY_FILE="$LOG_DIR/resumo_confianca_${RUN_TIMESTAMP}.log"

SUCCESS_COUNT=0
FAILURE_COUNT=0

{
    echo "============================================================"
    echo "Coleta Confiança Marília"
    echo "Início: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "Categorias: ${CATEGORIES[*]}"
    echo "============================================================"
} | tee "$SUMMARY_FILE"

for category in "${CATEGORIES[@]}"; do
    LOG_FILE="$LOG_DIR/confianca_${category}_${RUN_TIMESTAMP}.log"

    {
        echo "============================================================"
        echo "Categoria: $category"
        echo "Início: $(date '+%Y-%m-%d %H:%M:%S')"
        echo "============================================================"
        echo
        echo "ETAPA 1: coleta e geração da prévia"
    } | tee "$LOG_FILE"

    "$PYTHON" \
        scripts/collectors/confianca_marilia.py \
        --categoria "$category" \
        --dry-run \
        2>&1 | tee -a "$LOG_FILE"

    STATUS=${PIPESTATUS[0]}

    if [[ "$STATUS" -ne 0 ]]; then
        echo "FALHA: $category (coleta), código $STATUS" | tee -a "$LOG_FILE" "$SUMMARY_FILE"
        FAILURE_COUNT=$((FAILURE_COUNT + 1))
        sleep "$CATEGORY_DELAY"
        continue
    fi

    echo | tee -a "$LOG_FILE"
    echo "ETAPA 2: ingestão completa" | tee -a "$LOG_FILE"

    "$PYTHON" \
        scripts/diagnostics/confianca_full_ingest.py \
        --categoria "$category" \
        --enviar \
        2>&1 | tee -a "$LOG_FILE"

    STATUS=${PIPESTATUS[0]}

    if [[ "$STATUS" -ne 0 ]]; then
        echo "FALHA: $category (ingestão), código $STATUS" | tee -a "$LOG_FILE" "$SUMMARY_FILE"
        FAILURE_COUNT=$((FAILURE_COUNT + 1))
        sleep "$CATEGORY_DELAY"
        continue
    fi

    echo | tee -a "$LOG_FILE"
    echo "ETAPA 3: finalização da categoria" | tee -a "$LOG_FILE"

    "$PYTHON" \
        scripts/diagnostics/confianca_finalize_category.py \
        --categoria "$category" \
        --enviar \
        2>&1 | tee -a "$LOG_FILE"

    STATUS=${PIPESTATUS[0]}

    if [[ "$STATUS" -ne 0 ]]; then
        echo "FALHA: $category (finalização), código $STATUS" | tee -a "$LOG_FILE" "$SUMMARY_FILE"
        FAILURE_COUNT=$((FAILURE_COUNT + 1))
        sleep "$CATEGORY_DELAY"
        continue
    fi

    echo "SUCESSO: $category" | tee -a "$LOG_FILE" "$SUMMARY_FILE"
    SUCCESS_COUNT=$((SUCCESS_COUNT + 1))

    sleep "$CATEGORY_DELAY"
done

{
    echo
    echo "============================================================"
    echo "Resumo final"
    echo "Fim: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "Categorias concluídas: $SUCCESS_COUNT"
    echo "Categorias com falha: $FAILURE_COUNT"
    echo "============================================================"
} | tee -a "$SUMMARY_FILE"

find "$LOG_DIR" \
    -type f \
    \( \
        -name 'confianca_*.log' \
        -o -name 'resumo_confianca_*.log' \
        -o -name 'confianca_preview_*.json' \
        -o -name 'confianca_full_ingest_*.json' \
        -o -name 'confianca_finalize_*.json' \
    \) \
    -mtime +30 \
    -delete

if [[ "$FAILURE_COUNT" -gt 0 ]]; then
    exit 1
fi

exit 0
