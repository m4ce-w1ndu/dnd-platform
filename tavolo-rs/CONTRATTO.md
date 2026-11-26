# Contratto dell'API · Tavolo Virtuale

Questo documento descrive l'API che il client `tavolo/web/app.js` usa oggi con `tavolo/server.py`.
Il server Rust (`tavolo-rs/`) la rispetta identica: il client non cambia.
I test in `e2e/` sono la misura di «corretto»: `./e2e/run.sh` (Python) e `./e2e/run.sh target/release/tavolo` (Rust).

## Convenzioni

- Tutte le risposte JSON hanno `Content-Type: application/json; charset=utf-8` e `Cache-Control: no-store`.
- Errore applicativo: `{"ok": false, "errore": "testo per l'utente"}`. I rifiuti di permesso rispondono **200** con `ok:false`.
- **Credenziali**: `id` (12 esadecimali) + `secret` (token casuale), ottenuti da `/api/login` o dal callback OAuth.
  Il client le manda negli header `X-Client` / `X-Secret` (POST) oppure in query `?c=<id>&s=<secret>` (GET, SSE, download).
  Il server Rust accetta anche un cookie HttpOnly `tv_sess` (impostato da login/entra) — vedi «Novità del server Rust».
- **IP del client**: l'ultimo valore di `X-Forwarded-For` (lo aggiunge il proxy HTTPS), altrimenti l'IP della connessione.
- **Ruoli**: `role` è `giocatore` o `master` (al tavolo); `admin` e `master_ok` sono permessi dell'account.
- Intestazioni su ogni risposta: `Content-Security-Policy` (vedi sotto) e `X-Content-Type-Options: nosniff`.

CSP predefinita:
```
default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https:;
media-src 'self' data: blob:; connect-src 'self'; frame-src 'self'; object-src 'none'; base-uri 'none';
form-action 'self'; frame-ancestors 'self'
```

## Limiti di frequenza (token bucket)

| Chiave | Cosa | Ritmo | Raffica |
|---|---|---|---|
| IP | `/api/login`, `/api/entra` | 2/s | 10 |
| utente | `/api/op` con `pedina_muovi` o `righello` | 20/s | 30 |
| utente | ogni altra `/api/op` | 5/s | 15 |

Oltre il limite: **429** `{"ok": false, "errore": "..."}`. Corpo massimo di una richiesta: 80 MB (**413**).

## Endpoint

| Metodo e percorso | Chi | Cosa fa |
|---|---|---|
| `GET /api/info` | tutti | Stato pubblico: `avventura{id,titolo,sottotitolo,descrizione}` (vuoto se la sessione è `chiusa`), `personaggi[{id,nome,icona,razza,classe,colore,facoltativo}]`, `presi[]` (PG in mano a chi è collegato), `password_giocatori` (bool), `login[{id,nome}]` (provider OAuth attivi), `ospiti`, `versione` (impronta dei file web), `nome_tavolo`, `sessione`. |
| `POST /api/login` | tutti (limite IP) | `{"tipo":"ospite","nome","password"?}` o `{"tipo":"admin","utente","password"}`; con `id`+`secret` validi riusa l'utente. → `{ok,id,secret,nome}`. Errori: 400 nome vuoto/riservato/tipo errato, 403 ospiti spenti, password del tavolo o admin sbagliate. |
| `POST /api/entra` | con credenziali nel corpo (limite IP) | Si siede al tavolo: `{id,secret,ruolo,personaggio?,nome?,colore?}`. Master solo se `master_ok`/`admin`; colore validato (`#rgb…#rrggbbaa`, altrimenti quello precedente o `#c0392b`); PG inesistente ignorato; PG di un altro giocatore collegato → **409**. Crea/riassegna la pedina del PG. Annuncio in chat se la sessione non è `chiusa`. → `{ok,id,secret}`; 401 `{login:true}` senza credenziali. |
| `GET /api/io` | credenziali | `{ok,nome,admin,master,provider,avatar,char,colore,ruolo}`; 401 altrimenti. |
| `GET /api/stato` | credenziali | Partita filtrata per ruolo: `versione,avventura,scena,nebbia,pedine,log,iniziativa,schede,note_master` + `online[]`, `io{id,name,color,role,char,avatar,provider,admin}`, `avv` (avventura attiva filtrata), `sessione`; per Master/admin anche `catalogo[]` e `attiva`. |
| `GET /api/eventi` | credenziali (query) | Server-Sent Events: `retry: 2000`, poi `data: <json>` per evento, `: ping` ogni 15 s. Una nuova connessione dello stesso utente sostituisce la precedente. Aprire/chiudere manda `online` a tutti. |
| `POST /api/op` | credenziali | Un comando `{"op": "...", ...}` (vedi sotto). 400 se i dati non sono validi. |
| `POST /api/carica_avventura` | Master | Corpo = zip del pacchetto. → `{ok,id,titolo}`. Vedi «Pacchetti». |
| `POST /api/carica_mappa?nome&titolo&cella` | Master | Corpo = immagine (svg/png/jpg/jpeg/webp). Salvata in `mappe/` dell'avventura attiva con `<stem>.json` (`gruppo:"Caricate"`, `ordine:500`, griglia se `cella>0`). → `{ok,id}`. |
| `POST /api/carica_documento?nome&titolo&solo_master=0/1` | Master | Corpo = documento (html/htm/pdf/md/txt/immagini). Aggiunto ad `avventura.json`. → `{ok}`. |
| `GET /api/scarica_avventura?id` | Master | Zip della cartella dell'avventura (`<id>/...`). |
| `GET /api/esporta?id?` | Master | JSON della partita salvata (predefinita: quella attiva), `{}` se non c'è. |
| `POST /api/importa` | Master | Corpo = una partita esportata: sostituisce quella attiva (solo le chiavi note). Non-Master → 404. |
| `GET /api/backup` | admin | Copia coerente del database SQLite. |
| `GET /auth/<prov>/start` | tutti | 302 al provider (state + PKCE S256 per Google/Discord). 404 se il provider non è attivo. |
| `GET /auth/<prov>/callback` | tutti | Scambia il codice, crea/aggiorna l'utente `prov:uid`, e restituisce una pagina che salva le credenziali in `localStorage.tv_cred` e va a `/?accesso=1`. Errori: pagina con messaggio. |
| `GET /avventure/<id>/{mappe,documenti,immagini}/<file>` | tutti | File dell'avventura. Documenti `solo_master` → 403 senza credenziali da Master. Documenti non-PDF serviti con `Content-Security-Policy: sandbox allow-popups allow-popups-to-escape-sandbox allow-modals`. Traversal → 404. |
| `GET /`, `/admin`, `/<file>` | tutti | File di `web/`; in `index.html` `__VERSIONE__` è sostituito con la versione. |

## Comandi `/api/op`

Legenda chi: **T** tutti i seduti · **Prop** proprietario della pedina (o chi gioca quel PG) · **M** Master della partita · **A** amministratore.
Le risposte sono `{"ok": true}` salvo dove indicato.

| op | Chi | Dati | Effetto ed eventi |
|---|---|---|---|
| `tira` | T | `espr`, `etichetta?`, `segreto?`, `modo?`, `danni?` | Tiro di dadi (`NdF`, `d%`, `khN`/`klN`, numeri, `+`/`-`; max 120 caratteri, 100 dadi per gruppo, 200 in tutto, facce 2–1000). Col 20 naturale i dadi dei danni raddoppiano. Log `tiro`; → `{ok,tiro}`. |
| `chat` | T | `testo` (≤600), `segreto?` | Log `chat`. Testo vuoto → `ok:false`. |
| `ping` | T | `x`, `y`, `centra?` | Evento `ping` (`centra` solo dal Master). |
| `righello` | T | `punti` (lista di punti o null) | Evento `righello`. |
| `scegli_pg` | T | `pg` o null | Sceglie il personaggio; rifiutato se un altro giocatore collegato lo ha. Crea la pedina. Evento `online`. |
| `pedina_muovi` | Prop, M | `id`, `x`, `y`, `finale?` | Evento `pedina` (con `trascina` se non finale). |
| `pedina_salva` | Prop (solo `x,y,pf,condizioni`; PF limitati a 0…pfmax), M (tutto); nuove solo M | `pedina{...}` | Pulizia: nome ≤40, taglia 0.5–6, ≤12 condizioni da ≤20. PF della pedina di un PG → scheda. → `{ok,id}`. |
| `pedina_elimina` | Prop, M | `id` | Toglie la pedina anche dall'iniziativa. |
| `scheda` | chi gioca quel PG, M | `id`, `scheda{pf,pft,slot,usi,note,condizioni}` | Note ≤5000. PF copiati sulle pedine del PG. Evento `scheda`. |
| `iniziativa` `aggiungi` | T (pedina: Prop/M) | `nome` ≤40, `valore`, `pedina?`, `colore?`, `nascosta?` (solo M) | Una sola voce per pedina; ordine decrescente. |
| `iniziativa` `prossimo`/`precedente`/`rimuovi`/`valore`/`svuota` | M | `id?`, `valore?` | Turni e round; annuncio «Round N: tocca a X» se non nascosta. |
| `sessione_apri` | A | `id?` (predefinita: quella ricordata) | Attiva l'avventura e porta la sessione in `lobby`; evento `ricarica`. |
| `nomina_master` | A | `id`, `master?` (predefinito true) | Un solo Master: gli altri tornano giocatori (evento `ruolo`). |
| `sessione_inizia` | M, A | | Sessione `in_corso`. |
| `sessione_pausa` | M | | Sessione `lobby`. |
| `sessione_chiudi` | M, A | | Salva; sessione `chiusa`. |
| `imp_leggi` | A | | `{ok,config,utenti}` senza segreti. |
| `imp_salva` | A | `config{nome_tavolo,password_giocatori,public_url,ospiti,oauth{prov:{attivo,id,secret,rimuovi_secret}}}` | Validazione di URL e Client ID; → `{ok,config}`; evento `info`. |
| `imp_admin` | A | `attuale`, `utente?`, `nuova?` (≥8) | Cambia nome/password dell'admin. |
| `imp_partite` | A | | `{ok,partite[{id,titolo,aggiornata,pedine,tiri,round,in_gioco}]}`. |
| `imp_partita_azzera` | A | `id` | Cancella la partita salvata. |
| `imp_utente` | A | `id`, `master?`, `admin?`, `elimina?` | Non su se stessi per `admin`/`elimina`. Eliminato → evento `esci`. |
| `scena` | M | `id`, `porta_gruppo?` (predefinito true) | Cambia mappa; i PG vengono spostati (posizione azzerata). |
| `griglia` | M | `id`, `griglia{cella,ox,oy,mostra}` | Riscrive `<mappa>.json`. |
| `nebbia` | M | `scena?`, `attiva?`, `azione` `rivela`/`copri`/`copri_tutto`, `celle[]` | Evento `nebbia`. |
| `note_master` | M | `testo` (≤20000) | |
| `svuota_log` | M | | Evento `ricarica`. |
| `pulisci_scena` | M | `scena?` | Toglie le pedine non-PG dalla mappa. |
| `reset_partita` | M | | Partita vuota; evento `ricarica`. |
| `avventura_attiva` | M | `id` | Salva la partita e carica quella dell'altra avventura. |
| `avventura_nuova` | M | `titolo` | Crea un'avventura vuota; → `{ok,id}`. |
| `avventura_info` | M | `titolo,sottotitolo,descrizione,livello,giocatori,durata` (≤2000) | Aggiorna `avventura.json`. |
| `mappa_meta` | M | `id`, `titolo?,ordine?,note_master?,gruppo?` | Aggiorna `<mappa>.json`. |
| `mappa_elimina` | M | `id` | Non l'ultima mappa. |
| `documento_elimina` | M | `file` | Solo il nome del file (niente percorsi). |
| `avventura_elimina` | M | `id` | Non quella in gioco; cancella anche la partita. |

Un `op` sconosciuto → `ok:false`.

## Eventi SSE (`data: {"t": ...}`)

`pedina` `{pedina, da?, trascina?}` (ai non-Master una pedina nascosta arriva come `pedina_via`) · `pedina_via {id}` ·
`log {voce}` (le voci `segreto` solo all'autore e al Master) · `scena {id}` · `nebbia {scena, nebbia}` · `iniziativa {iniziativa}` ·
`scheda {id, scheda}` · `online {online[]}` · `catalogo` · `ping {x,y,colore,chi,centra}` · `righello {da,colore,punti}` ·
`ricarica` · `sessione {sessione, attiva}` · `ruolo {ruolo}` · `info` · `esci`.

## Pacchetti avventura (`carica_avventura`)

Zip con una cartella che contiene `avventura.json` (formato in `tavolo/FORMATO_AVVENTURE.md`). Id dal manifest o dalla
cartella, ripulito a `[a-z0-9_-]{1,61}`. Rifiutati con 400: non-zip, senza manifest, percorsi che escono dalla cartella,
più di 300 MB una volta estratto. Un id già presente viene sostituito (la partita salvata resta).

## Dati

SQLite in `$DATI_DIR/tavolo.db` (tabelle `impostazioni`, `utenti`, `account`, `partite`; ogni partita è un JSON in `partite.stato`).
Avventure in `$AVVENTURE_DIR/<id>/`. All'avvio la sessione è sempre `chiusa` e la partita dell'avventura ricordata viene ricaricata.
Il server ricontrolla la cartella avventure ogni 4 s e manda `catalogo` se cambia.

## Novità del server Rust (compatibili)

- Cookie `tv_sess` HttpOnly/SameSite=Lax in aggiunta a `id`+`secret` (il client attuale continua a usare id+secret).
- Password admin con Argon2id; il vecchio hash PBKDF2 viene accettato e convertito al primo accesso.
- `GET /healthz`, `GET /metrics` (Prometheus, solo da localhost o con token), registro di audit (accessi admin, cambi di permessi e impostazioni).
- Corpi JSON malformati o con tipi sbagliati → 400 invece di chiudere la connessione.
- Una nuova connessione SSE chiude subito quella vecchia; un giocatore che esce libera il suo PG subito, non al ping successivo.
