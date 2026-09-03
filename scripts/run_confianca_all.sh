#!/bin/bash

set -Eeuo pipefail

PROJECT_DIR="$HOME/Projects/compra-certa-mar-lia"
PYTHON="$PROJECT_DIR/.venv/bin/python"

LOG_DIR="$PROJECT_DIR/logs"
LOCK_DIR="$PROJECT_DIR/.confianca_collection.lock"

TIMESTAMP="$(date '+%Y%m%d_%H%M%S')"
LOG_FILE="$LOG_DIR/confianca_${TIMESTAMP}.log"
SUMMARY_FILE="$LOG_DIR/resumo_confianca_${TIMESTAMP}.log"

mkdir -p "$LOG_DIR"
cd "$PROJECT_DIR"

remove_lock() {
    rm -rf "$LOCK_DIR"
}

fail() {
    local exit_code=$?
    local line_number="${1:-desconhecida}"

    {
        echo
        echo "============================================================"
        echo "FALHA NA COLETA DO CONFIANÇA"
        echo "Linha: $line_number"
        echo "Código de saída: $exit_code"
        echo "Fim: $(date '+%Y-%m-%d %H:%M:%S')"
        echo "============================================================"
    } | tee -a "$LOG_FILE" "$SUMMARY_FILE"

    exit "$exit_code"
}

trap 'fail $LINENO' ERR
trap remove_lock EXIT INT TERM

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

if [[ ! -x "$PYTHON" ]]; then
    echo "ERRO: Python do ambiente virtual não encontrado."
    exit 11
fi

{
    echo "============================================================"
    echo "Coleta Confiança Marília"
    echo "Início: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "Categoria: alimentos_basicos"
    echo "============================================================"
} | tee "$LOG_FILE" "$SUMMARY_FILE"

echo | tee -a "$LOG_FILE"
echo "ETAPA 1: coleta e geração da prévia" | tee -a "$LOG_FILE"

"$PYTHON" \
    scripts/collectors/confianca_marilia.py \
    --categoria alimentos_basicos \
    --dry-run \
    2>&1 | tee -a "$LOG_FILE"

echo | tee -a "$LOG_FILE"
echo "ETAPA 2: ingestão completa" | tee -a "$LOG_FILE"

"$PYTHON" \
    scripts/diagnostics/confianca_full_ingest.py \
    --enviar \
    2>&1 | tee -a "$LOG_FILE"

echo | tee -a "$LOG_FILE"
echo "ETAPA 3: finalização da categoria" | tee -a "$LOG_FILE"

"$PYTHON" \
    scripts/diagnostics/confianca_finalize_category.py \
    --enviar \
    2>&1 | tee -a "$LOG_FILE"

{
    echo
    echo "============================================================"
    echo "SUCESSO: alimentos_basicos"
    echo "Fim: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "Último código de saída: 0"
    echo "============================================================"
} | tee -a "$LOG_FILE" "$SUMMARY_FILE"

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

exit 0
