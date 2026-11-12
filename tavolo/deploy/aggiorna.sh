#!/usr/bin/env bash
# Installa o aggiorna il Tavolo Virtuale su telesky-pc (Podman Quadlet rootful).
# Uso:  ./deploy/aggiorna.sh            (dalla cartella tavolo/)
# La prima volta crea anche la password del Master in /etc/tavolo-virtuale/tavolo.env.
set -euo pipefail
HOST="${HOST:-immauri@192.168.0.2}"
cd "$(dirname "$0")/.."

echo "→ copio i sorgenti su $HOST"
tar --exclude='__pycache__' -czf - Containerfile server.py web deploy \
  | ssh "$HOST" 'sudo mkdir -p /opt/tavolo-virtuale && sudo tar -xzf - -C /opt/tavolo-virtuale'

ssh "$HOST" bash -s <<'REMOTE'
set -euo pipefail
sudo mkdir -p /etc/containers/systemd/tavolo-virtuale /etc/tavolo-virtuale /var/lib/tavolo-virtuale/dati /var/lib/tavolo-virtuale/avventure
sudo chown -R 1000:1000 /var/lib/tavolo-virtuale
sudo install -m 644 /opt/tavolo-virtuale/deploy/tavolo.build /opt/tavolo-virtuale/deploy/tavolo.container /etc/containers/systemd/tavolo-virtuale/
sudo systemctl daemon-reload
echo "→ costruisco l'immagine"
sudo systemctl restart tavolo-build.service
echo "→ (ri)avvio il servizio"
sudo systemctl restart tavolo.service
sleep 2
systemctl is-active tavolo.service
curl -fsS -o /dev/null -w "HTTP %{http_code}\n" http://127.0.0.1:8095/
# al primo avvio la password admin (se non data con MASTER_PASSWORD) compare nel registro
sudo journalctl -u tavolo.service -n 30 --no-pager | grep -o "password iniziale: .*" | tail -1 || true
REMOTE
echo "✓ Tavolo Virtuale attivo su http://192.168.0.2:8095 (e https://dnd.immovilli.trade)"
echo "  Avventure: python3 strumenti/crea_pacchetto.py <progetto> --pubblica   oppure dal pannello Master"
