#!/usr/bin/env bash
# Installa o aggiorna il Tavolo Virtuale (server Rust) su telesky-pc, al posto di quello Python.
# Uso (dalla radice del repository):  ./tavolo-rs/deploy/aggiorna.sh
# Ritorno al server Python:           ./tavolo/deploy/aggiorna.sh   (stessi dati, stessa porta)
#
# Prima di riavviare: copia di sicurezza del database e verifica della copia con la nuova immagine.
# Se la verifica non passa, il servizio NON viene toccato.
set -euo pipefail
HOST="${HOST:-immauri@192.168.0.2}"
cd "$(dirname "$0")/../.."

echo "→ copio i sorgenti su $HOST"
tar --exclude='target' --exclude='__pycache__' --exclude='node_modules' --exclude='dist' -czf - \
    tavolo-rs/Cargo.toml tavolo-rs/Cargo.lock tavolo-rs/Containerfile tavolo-rs/migrations tavolo-rs/src tavolo-rs/deploy tavolo/web \
    tavolo-web/package.json tavolo-web/package-lock.json tavolo-web/angular.json tavolo-web/tsconfig.json tavolo-web/tsconfig.app.json \
    tavolo-web/public tavolo-web/src \
  | ssh "$HOST" 'sudo rm -rf /opt/tavolo-virtuale-rs.new && sudo mkdir -p /opt/tavolo-virtuale-rs.new && sudo tar -xzf - -C /opt/tavolo-virtuale-rs.new \
                 && sudo rm -rf /opt/tavolo-virtuale-rs && sudo mv /opt/tavolo-virtuale-rs.new /opt/tavolo-virtuale-rs'

ssh "$HOST" bash -s <<'REMOTE'
set -euo pipefail
DATI=/var/lib/tavolo-virtuale/dati
QUANDO=$(date +%Y%m%d-%H%M%S)
echo "→ costruisco l'immagine (prima volta: alcuni minuti)"
sudo podman build --network=host -f tavolo-rs/Containerfile -t localhost/tavolo-virtuale-rs:latest /opt/tavolo-virtuale-rs

echo "→ copia di sicurezza del database: $DATI/tavolo-$QUANDO.db"
if sudo podman exec tavolo-virtuale python3 -V >/dev/null 2>&1; then
  # oggi gira il server Python: copia coerente con l'API di backup di SQLite
  sudo podman exec tavolo-virtuale python3 -c "import sqlite3;s=sqlite3.connect('/app/dati/tavolo.db');d=sqlite3.connect('/app/dati/tavolo-$QUANDO.db');s.backup(d);d.close()"
else
  # gira già il server Rust (o nessuno): VACUUM INTO, sicuro anche a server acceso
  sudo podman run --rm --network=none -v "$DATI:/app/dati:Z" localhost/tavolo-virtuale-rs:latest copia-db /app/dati/tavolo.db "/app/dati/tavolo-$QUANDO.db"
fi

echo "→ verifico la copia con il nuovo server (nessuna modifica ai dati veri)"
sudo podman run --rm --network=none -v "$DATI:/app/dati:Z" localhost/tavolo-virtuale-rs:latest verifica-db "/app/dati/tavolo-$QUANDO.db"

echo "→ installo le unità Quadlet e riavvio"
sudo mkdir -p /etc/containers/systemd/tavolo-virtuale
sudo rm -f /etc/containers/systemd/tavolo-virtuale/tavolo.build     # l'immagine Rust è già costruita qui sopra
sudo install -m 644 /opt/tavolo-virtuale-rs/tavolo-rs/deploy/tavolo.container /etc/containers/systemd/tavolo-virtuale/
sudo systemctl daemon-reload
sudo systemctl restart tavolo.service
for i in $(seq 1 30); do
  if curl -fsS -o /dev/null http://127.0.0.1:8095/healthz; then break; fi
  sleep 1
done
systemctl is-active tavolo.service
curl -fsS -o /dev/null -w "healthz HTTP %{http_code}\n" http://127.0.0.1:8095/healthz
curl -fsS -o /dev/null -w "pagina HTTP %{http_code}\n" http://127.0.0.1:8095/
sudo journalctl -u tavolo.service -n 15 --no-pager
REMOTE
echo "✓ Tavolo Virtuale (Rust) attivo su http://192.168.0.2:8095 (e https://dnd.immovilli.trade)"
echo "  Se qualcosa non va: ./tavolo/deploy/aggiorna.sh rimette il server Python sugli stessi dati."
