# Formato Avventura · Tavolo Virtuale (versione 1)

Un'avventura è **un file `.zip`** che contiene una cartella con questo contenuto:

```
<id>/
├── avventura.json          ← obbligatorio: titolo, descrizione, elenco documenti
├── personaggi.json         ← personaggi pronti (schede interattive), anche []
├── mostri.json             ← bestiario del Master, anche []
├── mappe/
│   ├── 01_piazza.svg       ← immagine della mappa: .svg .png .jpg .jpeg .webp
│   ├── 01_piazza.json      ← facoltativo: titolo, griglia, punto di partenza…
│   └── …
└── documenti/
    ├── 1_Manuale_del_Master.html
    └── …
```

- **`<id>`** è un nome breve fatto di minuscole, numeri, `-` e `_` (es. `vermiglia`). Se carichi un pacchetto con un id già presente, l'avventura viene **aggiornata** e la partita in corso resta salvata.
- Si carica dal pannello **👑 Master → 📚 Avventure → Carica**, oppure con `python3 strumenti/crea_pacchetto.py <progetto> --pubblica`.
- Il server controlla la cartella `avventure/` ogni 4 secondi: se aggiungi o modifichi un file (anche via `scp`), tutti vedono il cambiamento **senza riavvii**.

## `avventura.json`

```json
{
  "id": "vermiglia",
  "titolo": "La Tana di Vermiglia",
  "sottotitolo": "One-shot di draghi per principianti",
  "descrizione": "Una giovane drago rossa rapisce Tilde…",
  "livello": "3",
  "giocatori": "5 (+1 facoltativo)",
  "durata": "1 sessione, circa 4 ore",
  "formato": 1,
  "documenti": [
    {"file": "1_Manuale_del_Master.html", "titolo": "Manuale del Master", "solo_master": true},
    {"file": "2_Guida_del_Giocatore.html", "titolo": "Guida del Giocatore"}
  ]
}
```

I documenti con `"solo_master": true` si aprono solo con le credenziali del Master. Dentro i documenti, le immagini delle mappe si richiamano con `../mappe/<file>`.

## Mappe: formato unificato

Ogni mappa è **un'immagine** e, accanto, un **file `.json` con lo stesso nome**. Il `.json` è facoltativo: senza, la mappa compare con il nome del file e senza griglia.

```json
{
  "titolo": "Piazza di Pietracalda",
  "ordine": 1,
  "gruppo": "",
  "griglia": {"cella": 32, "ox": 40, "oy": 92, "mostra": false},
  "inizio": [2, 3],
  "note_master": "I coboldi escono dalla grata P6."
}
```

| Campo | Significato |
|---|---|
| `titolo` | Nome mostrato nell'elenco e nella barra in alto. |
| `ordine` | Ordine nell'elenco (la prima mappa è quella iniziale di una nuova partita). |
| `gruppo` | Intestazione facoltativa per raggruppare le mappe nell'elenco del Master. |
| `griglia.cella` | Lato di un quadretto **in pixel dell'immagine** (1 quadretto = 1,5 m). `0` o assente = mappa senza griglia (es. mappe regionali). |
| `griglia.ox`, `griglia.oy` | Dove inizia la griglia (pixel dall'angolo in alto a sinistra). |
| `griglia.mostra` | `true` = il tavolo disegna la griglia sopra l'immagine (per mappe che non ce l'hanno già). |
| `inizio` | `[colonna, riga]` dove compaiono le pedine dei personaggi quando si arriva sulla mappa. |
| `note_master` | Promemoria visibile solo al Master. |

Larghezza e altezza vengono lette dall'immagine (si possono forzare con `larghezza`/`altezza`). Quando il Master corregge la griglia dal pannello «📐 Griglia della mappa», il server riscrive direttamente questo `.json`.

**Aggiornare solo le mappe sul server**: copia l'immagine e il suo `.json` in
`/var/lib/tavolo-virtuale/avventure/<id>/mappe/`: compaiono da sole entro pochi secondi.

## `personaggi.json`

Un elenco di personaggi. I campi principali (vedi `avventure/vermiglia/strumenti/dati/personaggi.json` per esempi completi):

```json
{
  "id": "rocco", "nome": "Rocco Martelli", "icona": "🛡️", "colore": "#b03a2e",
  "razza": "Umano", "classe": "Guerriero (Campione)", "background": "Soldato", "livello": 3,
  "facoltativo": false, "sottotitolo": "Il più facile da giocare",
  "chi": "…", "personalita": "…", "perche": "…", "legame": "…", "consiglio": "…", "equip": "…",
  "ca": 19, "ca_note": "", "pf": 28, "vel": "9 m", "iniz": 2, "dadivita": "3d10", "comp": 2,
  "car": {"FOR": 16, "DES": 14, "COS": 15, "INT": 9, "SAG": 13, "CAR": 11},
  "ts": ["FOR", "COS"],
  "abilita": {"Atletica": 5, "Percezione": 3},
  "factotum": 0, "sensi": "", "extra": "",
  "attacchi": [{"nome": "Spada lunga", "bonus": 5, "danni": "1d8+3", "tipo": "taglienti", "note": "mischia"}],
  "capacita": [{"nome": "Recuperare energie", "testo": "…", "tiro": "1d10+3", "usi": 1}],
  "magia": {"cd": 13, "att": 5, "slot": {"1": 4, "2": 2}, "nota": "",
            "incantesimi": [{"nome": "Dardo tracciante", "liv": 1, "testo": "…", "tiro": "4d6", "attacco": true}]}
}
```

- `abilita` elenca **solo** le abilità in cui il personaggio è addestrato, con il bonus totale; le altre si calcolano dalle caratteristiche (+ `factotum`).
- Un attacco con `"bonus": null` tira solo i danni (es. Attacco furtivo).
- `tiro` su capacità e incantesimi rende il nome cliccabile; `"attacco": true` tira prima d20 + `att`, poi i danni.
- `usi` crea delle caselle da spuntare (si azzerano col riposo lungo 🌙).

## `mostri.json`

```json
{
  "id": "vermiglia", "nome": "Vermiglia", "tipo": "Drago Grande", "icona": "🐉", "colore": "#c0392b",
  "ca": 17, "pf": 70, "vel": "9 m, volo 18 m", "gs": "4", "des": 0, "taglia": 2, "alleato": false,
  "attacchi": [{"nome": "Morso", "bonus": 6, "danni": "1d10+4+1d6", "note": "perforanti + fuoco"}],
  "tratti": [{"nome": "Soffio di fuoco", "testo": "…", "tiro": "6d6"}]
}
```

`des` è il bonus d'iniziativa, `taglia` il numero di quadretti per lato (2 = Grande). I mostri con `"alleato": true` sono visibili anche ai giocatori.

## Sorgente (per chi genera le avventure)

In ogni cartella `avventure/<id>/` del repository c'è un file `pacchetto.json` che descrive come costruire lo zip: stessi campi di `avventura.json`, più i percorsi `personaggi`, `mostri`, `mappe_cartella` e un dizionario `mappe` con i metadati di ogni mappa (le chiavi sono i nomi dei file senza estensione). Le immagini delle mappe stanno in `asset/mappe/<id>/` (`mappe_cartella`). `tavolo/strumenti/crea_pacchetto.py` produce il pacchetto in `tavolo/pacchetti/<id>.zip` e, con `--pubblica`, lo installa sul server.
