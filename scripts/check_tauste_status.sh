#!/usr/bin/env bash

set -u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR" || exit 1

echo "============================================================"
echo "Status da coleta Tauste Marília"
echo "Data: $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================================"

echo ""
echo "Processos ativos:"

if ps aux | grep -E '[r]un_tauste_all\.sh|[t]auste_marilia\.py'; then
  echo ""
  echo "Existe uma coleta em execução."
else
  echo "Nenhuma coleta em execução."
fi

echo ""
echo "Status do launchd:"

launchctl print "gui/$(id -u)/com.compracerta.tauste" 2>/dev/null |
  grep -E '^[[:space:]]*state =|last exit code' ||
  echo "Agendamento não encontrado."

echo ""
echo "Último resumo:"

LATEST_SUMMARY="$(ls -t logs/resumo_*.log 2>/dev/null | head -1)"

if [[ -n "$LATEST_SUMMARY" ]]; then
  echo "Arquivo: $LATEST_SUMMARY"
  cat "$LATEST_SUMMARY"
else
  echo "Nenhum resumo encontrado."
fi

echo ""
echo "Últimos erros do launchd:"

if [[ -s logs/launchd_stderr.log ]]; then
  tail -n 30 logs/launchd_stderr.log
else
  echo "Nenhum erro registrado."
fi

echo ""
echo "Falhas recentes encontradas nos logs:"

RECENT_LOGS="$(ls -t logs/tauste_*.log 2>/dev/null | head -10)"

if [[ -n "$RECENT_LOGS" ]]; then
  RESULTS="$(grep -hEi \
    'Traceback|ERRO|FALHA|SiteRejected|HTTP 403|HTTP 429|falhas.: [1-9]' \
    $RECENT_LOGS 2>/dev/null || true)"

  if [[ -n "$RESULTS" ]]; then
    echo "$RESULTS"
  else
    echo "Nenhuma falha recente."
  fi
else
  echo "Nenhum log de categoria encontrado."
fi
