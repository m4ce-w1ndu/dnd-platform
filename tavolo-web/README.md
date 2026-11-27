# Tavolo Virtuale · client nuovo (Angular + TypeScript)

Riscrittura di `tavolo/web/app.js` con lo stesso aspetto (stesso foglio di stile) e la stessa API.
In produzione è la pagina principale (`/`) del server Rust; il client vecchio resta su **`/vecchio/`** come ripiego
(`/beta/`, l'indirizzo provvisorio, rimanda a `/`).

- **Tipi generati dal server**: `src/app/api/generati/` viene scritto da `cargo test esporta_tipi_typescript`
  in `tavolo-rs/` (ts-rs). Se il server cambia un campo, il client non compila più. Non modificare a mano.
- **Stato**: un solo store a signal (`stato/tavolo.store.ts`) aggiornato dagli eventi SSE; i componenti leggono valori derivati.
- **Servizi**: `api/api.service.ts` (HTTP tipizzato), `core/connessione.service.ts` (accesso, SSE, riconnessione,
  ricarica alla nuova versione), `stato/azioni.service.ts` (azioni di gioco condivise).
- **Logica pura** in `util/` (geometria, nebbia, dadi, scheda) con test Vitest.

```bash
npm ci
npx ng test --watch=false     # test unitari
npx ng build                  # dist/tavolo-web/browser
npx ng serve                  # sviluppo su :4200, con /api inoltrato al server su :8080 (proxy.conf.json)
```

**Test nel browser** (Playwright + Chromium, in `tavolo-rs/e2e/test_gui.py`): percorrono tutti i flussi dei
ruoli (sistema, amministratore del tavolo, Master, giocatori, telefono) contro il server Rust con questa build.

```bash
npx ng build
cd ../tavolo-rs && cargo build --release
python3 -m venv e2e/.venv && e2e/.venv/bin/pip install playwright && e2e/.venv/bin/playwright install chromium   # una volta
e2e/run.sh target/release/tavolo test_gui
```

Novità rispetto al client vecchio: l'account di sistema «Admin» ha una sua pagina (impostazioni, permessi,
partite, backup, registro di audit) invece della mappa; la sala d'attesa mostra apertura del tavolo e scelta del
Master solo agli amministratori del tavolo; le note non perdono testo se arriva un aggiornamento mentre si scrive.
