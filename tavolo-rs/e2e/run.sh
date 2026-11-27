#!/usr/bin/env bash
# Test end-to-end del Tavolo Virtuale.
#   ./run.sh                               contro il server Python (tavolo/server.py)
#   ./run.sh ../target/release/tavolo      contro il server Rust
#   ./run.sh <server> test_gioco           solo un modulo (o test_gioco.TestDadi, …)
#   ./run.sh ../target/release/tavolo test_gui   client nuovo nel browser (vedi test_gui.py per i requisiti)
set -euo pipefail
if [ "${1:-python}" != python ]; then set -- "$(realpath "$1")" "${@:2}"; fi
cd "$(dirname "$0")"
SERVER="${1:-python}"
if [ "$SERVER" != python ]; then SERVER="$(realpath "$SERVER")"; fi
shift || true
if [ $# -eq 0 ]; then set -- test_accesso test_gioco test_permessi test_dati test_migrazione test_gui; fi
# test_gui (browser) usa Playwright dal venv e2e/.venv, se c'è; senza, quei test vengono saltati
PY=python3; [ -x .venv/bin/python ] && PY=.venv/bin/python
TAVOLO_SERVER="$SERVER" exec "$PY" -m unittest -v "$@" 2>&1
