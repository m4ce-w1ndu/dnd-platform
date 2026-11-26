# Tavolo Virtuale · server Rust

Riscrittura di `tavolo/server.py`: stessa API, stesso database, stesso client (`tavolo/web/`).
Contratto: [CONTRATTO.md](CONTRATTO.md) · Regole (chi può fare cosa): [REGOLE.md](REGOLE.md)

## Provarlo sul PC

```bash
cargo build --release
DATI_DIR=/tmp/prova/dati AVVENTURE_DIR=/tmp/prova/avventure WEB_DIR=../tavolo/web \
  MASTER_PASSWORD=una-password ./target/release/tavolo --porta 8080
```

## Test

| Comando | Cosa prova |
|---|---|
| `cargo test --release` | unità, matrice dei permessi, fuzzing leggero (comandi, dadi, zip, logica di gioco) |
| `./e2e/run.sh` | i 69 test end-to-end contro il server **Python** (il riferimento) |
| `./e2e/run.sh target/release/tavolo` | gli stessi test contro il server **Rust** (+ migrazione Python → Rust → Python) |
| `python3 e2e/carico.py target/release/tavolo` | prova di carico: 40 giocatori × 10 azioni al secondo |
| `cargo +nightly fuzz run comandi` (in `fuzz/`) | fuzzing guidato dalla copertura |

Prova di carico (40 giocatori, 20 s, stesso PC): Rust p50 2,6 ms, p99 18 ms, max 0,17 s, 0 errori, 46 MB ·
Python p50 6,9 ms, p99 40 ms, max 1,3 s, 7 connessioni perse, 48 MB.

## Sul server (telesky-pc)

```bash
./tavolo-rs/deploy/aggiorna.sh      # installa/aggiorna il server Rust (dalla radice del repository)
./tavolo/deploy/aggiorna.sh         # piano B: rimette il server Python, stessi dati e stessa porta
```

`aggiorna.sh` costruisce l'immagine, fa una copia del database (`dati/tavolo-<data>.db`), la verifica con
`tavolo verifica-db` e solo se è tutto a posto riavvia il servizio. Comandi utili nel container:

- `tavolo verifica-db <file.db>`: legge una copia del database e segnala qualsiasi perdita o differenza;
- `tavolo copia-db <da.db> <a.db>`: copia coerente anche a server acceso;
- `GET /healthz`, `GET /metrics` (da localhost, o con `Authorization: Bearer $METRICS_TOKEN`);
- `GET /api/audit?c=…&s=…` (admin): registro di accessi admin, permessi, impostazioni, cancellazioni.

## Com'è fatto

- `tavolo.rs`: **un solo task** possiede tutto lo stato del tavolo e gestisce i comandi in ordine da una coda
  (niente lock); se un comando ha un bug il task registra l'errore e va avanti.
- `comandi.rs`: i comandi di `/api/op` come enum `serde`, validati all'ingresso (tipi sbagliati → 400).
- `permessi.rs`: **una tabella** con il livello richiesto da ogni comando, testata per ogni ruolo.
- `gioco.rs`, `impostazioni.rs`, `contenuti.rs`: la logica; `web.rs`: HTTP (axum), SSE, file, sicurezza.
- `db.rs` + `migrations/`: SQLite con sqlx, stesso schema del Python più la tabella `audit`.
- `password.rs`: Argon2id; il vecchio PBKDF2 viene accettato, convertito e tenuto aggiornato per il piano B.
