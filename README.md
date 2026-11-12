# 🐉 Tavolo Virtuale D&D

Una piattaforma per giocare a **Dungeons & Dragons 5ª edizione** dal browser, con avventure pronte in italiano pensate per **giocatori e Master alle prime armi**.

- **Tavolo virtuale** (`tavolo/`): mappe con griglia, pedine trascinabili, nebbia di guerra, righello, ping, dadi tirati dal server con animazioni, schede dei personaggi interattive, iniziativa, sala d'attesa, accesso con Discord/Google/GitHub. Funziona anche da telefono.
- **Avventure** in un formato a pacchetto (`.zip`) che si carica dal browser: mappe, personaggi, mostri e documenti.

Nessuna dipendenza da installare: il server usa solo la libreria standard di Python, l'interfaccia è HTML/CSS/JavaScript senza framework.

---

## Struttura del repository

```
.
├── tavolo/                         la piattaforma web
│   ├── server.py                   server HTTP + Server-Sent Events + SQLite (solo stdlib)
│   ├── web/                        interfaccia (index.html, app.js, style.css)
│   ├── strumenti/crea_pacchetto.py crea (e pubblica) i pacchetti avventura .zip
│   ├── deploy/                     Podman Quadlet + script di aggiornamento
│   ├── Containerfile
│   ├── FORMATO_AVVENTURE.md        specifica dei pacchetti e del formato delle mappe
│   └── LEGGIMI.txt                 guida rapida per chi gestisce il server
│
├── avventure/
│   ├── vermiglia/                  «La Tana di Vermiglia» · one-shot originale · 5 giocatori · 3° livello
│   ├── brumaria/                   «Le Campane di Brumaria» · campagna originale · livelli 1-4 · 8 sessioni
│   └── pinebrook/                  «Pericolo a Pinebrook» · adattamento dell'avventura ufficiale (vedi «Copyright»)
│
└── asset/
    └── mappe/                      tutte le mappe generate, pronte da usare
        ├── vermiglia/              *.svg (stampa) + png/ (Roll20, Foundry, Owlbear Rodeo)
        ├── brumaria/
        └── pinebrook/              + alternative/ (le mie caverne, sostituite dalle mappe Calos)
```

Ogni cartella in `avventure/<id>/` contiene:

| Percorso | Cosa |
|---|---|
| `pacchetto.json` | descrizione del pacchetto: titolo, mappe (con griglia e note del Master), documenti |
| `1_Manuale_del_Master.html`, `2_Guida_del_Giocatore.html`, `3_Schede_dei_Personaggi.html` | documenti stampabili (Brumaria e Vermiglia) |
| `strumenti/` | script che generano mappe e documenti, sorgenti HTML, dati di personaggi e mostri in JSON |

Le **mappe** sono in `asset/mappe/<id>/`: le SVG sono vettoriali e si stampano nitide a qualsiasi grandezza, le PNG (`png/`, 64 pixel per quadretto) sono pronte per qualsiasi tavolo virtuale. Le mappe a griglia hanno 1 quadretto = 1,5 m (5 ft).

---

## Avvio rapido (sul proprio PC)

Serve solo **Python 3.9+**.

```bash
cd tavolo
python3 server.py                 # → http://localhost:8000
```

Al primo avvio il server crea l'account **admin** e stampa la password iniziale. Poi:

1. Apri `http://localhost:8000/admin` ed entra come amministratore.
2. Crea un pacchetto e caricalo dal pannello **👑 Master → 📚 Avventure**:
   ```bash
   python3 tavolo/strumenti/crea_pacchetto.py avventure/vermiglia
   # → tavolo/pacchetti/vermiglia.zip
   ```
3. Nella **sala d'attesa** scegli l'avventura, nomina il Master, e quando tutti hanno scelto il personaggio premi **▶ Inizia la partita**.

Tutte le impostazioni (account admin, accesso con Discord/Google/GitHub, ospiti, password del tavolo, utenti) si gestiscono dal browser nella scheda **⚙️ Impostazioni**. Non ci sono file di configurazione o variabili d'ambiente da toccare: tutto è salvato nel database SQLite `tavolo/dati/tavolo.db`, che **non** è nel repository.

---

## Come si gioca una serata

1. **Accesso**: tutti entrano (Discord, Google, GitHub, oppure come ospiti se ammessi). L'amministratore ha sempre l'ingresso di riserva `/admin`.
2. **Sala d'attesa**: l'admin sceglie l'avventura e nomina il Master; i giocatori scelgono il personaggio.
3. **Partita**: il Master preme «▶ Inizia la partita» e tutti vedono la mappa.
4. **Fine**: «🔒 Chiudi il tavolo». Ogni avventura conserva la propria partita salvata.

---

## Pubblicazione su un server

La cartella `tavolo/deploy/` contiene un'installazione con **Podman Quadlet** (rootful):

- `tavolo.build`: costruisce l'immagine da `Containerfile`;
- `tavolo.container`: servizio sulla porta 8095, dati in `/var/lib/tavolo-virtuale/{dati,avventure}`;
- `aggiorna.sh`: copia i sorgenti sul server, ricostruisce l'immagine e riavvia il servizio. Modifica la variabile `HOST` (o l'host predefinito nello script) per il tuo server.

```bash
./tavolo/deploy/aggiorna.sh                                            # aggiorna il programma
python3 tavolo/strumenti/crea_pacchetto.py avventure/vermiglia --pubblica   # pubblica un'avventura
```

Il server legge l'indirizzo pubblico dalle impostazioni (serve per l'accesso con account). Le Redirect URI da registrare sui provider sono `https://<tuo-dominio>/auth/{discord,google,github}/callback` e sono mostrate nella scheda ⚙️.

---

## Creare nuove avventure

Il formato dei pacchetti è descritto in **[`tavolo/FORMATO_AVVENTURE.md`](tavolo/FORMATO_AVVENTURE.md)**. In breve: un `.zip` con `avventura.json`, `personaggi.json`, `mostri.json`, una cartella `mappe/` (immagine + `.json` con griglia, titolo e note del Master) e una cartella `documenti/` (HTML o PDF).

Per rigenerare i contenuti delle avventure di questo repository:

```bash
python3 avventure/brumaria/strumenti/genera_mappe.py       # mappe della campagna     → asset/mappe/brumaria/
python3 avventure/brumaria/strumenti/componi.py            # documenti della campagna
python3 avventure/vermiglia/strumenti/mappe_oneshot.py     # mappe del one-shot       → asset/mappe/vermiglia/
python3 avventure/vermiglia/strumenti/componi_oneshot.py   # documenti e schede del one-shot
python3 avventure/pinebrook/strumenti/mappe_pinebrook.py   # mappe di Pinebrook       → asset/mappe/pinebrook/
```

Gli script sono deterministici: rigenerando si ottengono le stesse mappe. Le esportazioni PNG richiedono `rsvg-convert` (librsvg); tutto il resto solo Python.

---

## Copyright

- **La Tana di Vermiglia** e **Le Campane di Brumaria**, con le loro mappe, sono contenuti originali. Le regole di gioco si basano sul *System Reference Document 5.1* (CC-BY-4.0, Wizards of the Coast).
- **Pericolo a Pinebrook** è un adattamento per uso personale dell'avventura ufficiale *Peril in Pinebrook* (© Wizards of the Coast, «solo per uso personale e non commerciale; vietata la ridistribuzione»). Le mappe della tana sono di **Calos Pro Maps**. Per questo **il PDF e le mappe di Calos non sono nel repository** (vedi `.gitignore`): per ricostruire il pacchetto copia a mano
  - `avventure/pinebrook/documenti/Pericolo_a_Pinebrook_completo.pdf`, `Schede_e_regole_per_i_giocatori.pdf`, `Pagina_della_guida_ai_draghi.pdf` (dal PDF dell'avventura: pagine 17-22 e 14);
  - `asset/mappe/pinebrook/02_la_tana_di_rorn.webp` e `03_la_tana_di_rorn_scivoli.webp` (dalle mappe Calos «GRID 40x35» e «Slides GRID 40x35»).

  Anche i dati dei personaggi e dei mostri di Pinebrook derivano dall'avventura ufficiale: tieni il repository **privato**.
