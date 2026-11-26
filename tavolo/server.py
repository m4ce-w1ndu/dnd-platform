#!/usr/bin/env python3
"""Tavolo Virtuale · piattaforma di gioco per D&D (solo libreria standard di Python 3.9+).

Il server ospita un catalogo di AVVENTURE (pacchetti .zip, vedi FORMATO_AVVENTURE.md):
ognuna ha mappe, personaggi, mostri e documenti, e conserva la propria partita salvata.
Il Master sceglie dall'interfaccia a quale avventura si gioca.

Avvio:
    python3 server.py                      # porta 8000; al primo avvio crea l'account admin
    python3 server.py --porta 8080

Tutte le impostazioni (account admin, accesso con Discord/Google/GitHub, ospiti, password del
tavolo, indirizzo pubblico) si modificano dal browser: scheda ⚙️ Impostazioni (solo admin).
Sono salvate in dati/config.json. Al primo avvio la password admin è MASTER_PASSWORD
(variabile d'ambiente) oppure una casuale stampata a video; l'utente admin si chiama «admin».
"""
import argparse
import base64
import hashlib
import io
import json
import mimetypes
import os
import queue
import re
import secrets
import shutil
import signal
import socket
import sqlite3
import struct
import threading
import time
import uuid
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import urllib.error
import urllib.request
from urllib.parse import parse_qs, quote, unquote, urlencode, urlparse

QUI = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(QUI, "web")
AVV_DIR = os.environ.get("AVVENTURE_DIR", os.path.join(QUI, "avventure"))
DATI = os.environ.get("DATI_DIR", os.path.join(QUI, "dati"))
PARTITE = os.path.join(DATI, "partite")
TAVOLO_FILE = os.path.join(DATI, "tavolo.json")
CONFIG_FILE = os.path.join(DATI, "config.json")   # solo per migrare le vecchie installazioni
DB_FILE = os.path.join(DATI, "tavolo.db")
DB = None
MAX_LOG = 400
MAX_BODY = 80 * 1024 * 1024
IMG_EXT = (".svg", ".png", ".jpg", ".jpeg", ".webp")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_\-]{0,60}$")

mimetypes.add_type("image/svg+xml", ".svg")
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("image/webp", ".webp")

LOCK = threading.RLock()
CLIENTS = {}       # client_id -> {"q": Queue, "role": ...}
USERS = {}         # client_id -> {"secret", "name", "color", "role", "char"}
ATTIVA = None      # id dell'avventura in gioco
STATE = {}         # partita dell'avventura attiva
CATALOGO = {}      # id -> avventura (manifest + mappe + personaggi + mostri + documenti)
CONFIG = {}              # impostazioni modificabili dal browser (dati/config.json)
PASSWORD_GIOCATORI = ""  # derivate da CONFIG con applica_config()
PUBLIC_URL = ""
OSPITI = True
OAUTH = {}               # provider attivi -> {"id":..., "secret":...}
ACCOUNTS = {}            # "discord:1234" -> client_id
STATI_OAUTH = {}         # state -> (provider, scadenza, verifier, redirect_uri)
VERSIONE = ""            # impronta dei file web: se cambia, i browser si ricaricano
SESSIONE = "chiusa"      # chiusa → (admin apre) lobby → (il Master inizia) in_corso. All'avvio è sempre chiusa.
DOC_EXT = (".html", ".htm", ".pdf", ".md", ".txt", ".png", ".jpg", ".jpeg", ".webp", ".svg")

PROVIDER = {
    "discord": {
        "nome": "Discord", "auth": "https://discord.com/oauth2/authorize", "token": "https://discord.com/api/oauth2/token",
        "utente": "https://discord.com/api/users/@me", "scope": "identify",
        "console": "https://discord.com/developers/applications",
    },
    "google": {
        "nome": "Google", "auth": "https://accounts.google.com/o/oauth2/v2/auth", "token": "https://oauth2.googleapis.com/token",
        "utente": "https://openidconnect.googleapis.com/v1/userinfo", "scope": "openid email profile",
        "console": "https://console.cloud.google.com/apis/credentials",
    },
    "github": {
        "nome": "GitHub", "auth": "https://github.com/login/oauth/authorize", "token": "https://github.com/login/oauth/access_token",
        "utente": "https://api.github.com/user", "scope": "read:user",
        "console": "https://github.com/settings/developers",
    },
}
_save_timer = None


# ============================================================================ database (SQLite)
SCHEMA = """
CREATE TABLE IF NOT EXISTS impostazioni (chiave TEXT PRIMARY KEY, valore TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS utenti (id TEXT PRIMARY KEY, nome TEXT, account TEXT, admin INTEGER DEFAULT 0,
                                   master INTEGER DEFAULT 0, visto REAL, dati TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS account (chiave TEXT PRIMARY KEY, utente_id TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS partite (avventura TEXT PRIMARY KEY, stato TEXT NOT NULL, aggiornata REAL);
"""


def apri_db():
    global DB
    os.makedirs(DATI, exist_ok=True)
    DB = sqlite3.connect(DB_FILE, check_same_thread=False, isolation_level=None)
    DB.execute("PRAGMA journal_mode=WAL")
    DB.executescript(SCHEMA)
    migra_json()


def db_get(chiave, default=None):
    with LOCK:
        r = DB.execute("SELECT valore FROM impostazioni WHERE chiave=?", (chiave,)).fetchone()
    return json.loads(r[0]) if r else default


def db_set(chiave, valore):
    with LOCK:
        DB.execute("INSERT INTO impostazioni(chiave, valore) VALUES(?,?) ON CONFLICT(chiave) DO UPDATE SET valore=excluded.valore",
                   (chiave, json.dumps(valore, ensure_ascii=False)))


def db_partita(aid):
    with LOCK:
        r = DB.execute("SELECT stato FROM partite WHERE avventura=?", (aid,)).fetchone()
    return json.loads(r[0]) if r else None


def migra_json():
    """Importa i vecchi file JSON (config.json, tavolo.json, partite/*.json) una sola volta."""
    if db_get("migrato"):
        return
    vecchio_conf = leggi_json(CONFIG_FILE, None)
    if vecchio_conf and not db_get("config"):
        db_set("config", vecchio_conf)
    t = leggi_json(TAVOLO_FILE, None)
    if t:
        db_set("attiva", t.get("attiva"))
        with LOCK:
            for cid, u in t.get("utenti", {}).items():
                DB.execute("INSERT OR REPLACE INTO utenti(id,nome,account,admin,master,visto,dati) VALUES(?,?,?,?,?,?,?)",
                           (cid, u.get("name"), u.get("account"), int(bool(u.get("admin"))), int(bool(u.get("master_ok"))), u.get("seen"), json.dumps(u)))
            for k, v in t.get("account", {}).items():
                DB.execute("INSERT OR REPLACE INTO account VALUES(?,?)", (k, v))
    if os.path.isdir(PARTITE):
        for f in os.listdir(PARTITE):
            if f.endswith(".json"):
                st = leggi_json(os.path.join(PARTITE, f), None)
                if st:
                    with LOCK:
                        DB.execute("INSERT OR REPLACE INTO partite VALUES(?,?,?)", (f[:-5], json.dumps(st), time.time()))
    for f in (CONFIG_FILE, TAVOLO_FILE):
        if os.path.exists(f):
            os.replace(f, f + ".migrato")
    if os.path.isdir(PARTITE):
        os.replace(PARTITE, PARTITE + ".migrate")
    db_set("migrato", True)


def elenco_partite():
    with LOCK:
        righe = DB.execute("SELECT avventura, stato, aggiornata FROM partite ORDER BY aggiornata DESC").fetchall()
    out = []
    for aid, st, agg in righe:
        st = json.loads(st)
        out.append({"id": aid, "titolo": CATALOGO.get(aid, {}).get("titolo", aid + " (avventura rimossa)"), "aggiornata": agg,
                    "pedine": len(st.get("pedine", {})), "tiri": sum(1 for v in st.get("log", []) if v.get("tipo") == "tiro"),
                    "round": st.get("iniziativa", {}).get("round", 1), "in_gioco": aid == ATTIVA})
    return out


def backup_db():
    tmp = DB_FILE + ".backup"
    with LOCK:
        dest = sqlite3.connect(tmp)
        DB.backup(dest)
        dest.close()
    with open(tmp, "rb") as f:
        data = f.read()
    os.remove(tmp)
    return data


# ============================================================================ impostazioni e admin
def hash_password(pw, sale):
    return hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), bytes.fromhex(sale), 200_000).hex()


def imposta_password_admin(pw):
    sale = secrets.token_hex(16)
    CONFIG["admin"]["sale"] = sale
    CONFIG["admin"]["hash"] = hash_password(pw, sale)


def verifica_admin(utente, pw):
    a = CONFIG.get("admin", {})
    if not a.get("hash") or not pw:
        return False
    ok_utente = secrets.compare_digest(str(utente or "").strip().lower(), a.get("utente", "admin").lower())
    return ok_utente and secrets.compare_digest(hash_password(str(pw), a["sale"]), a["hash"])


def carica_config():
    """Legge dati/config.json; al primo avvio lo crea usando le variabili d'ambiente come valori iniziali."""
    global CONFIG
    CONFIG = db_get("config", {})
    nuovo = not CONFIG
    CONFIG.setdefault("nome_tavolo", "Tavolo Virtuale")
    CONFIG.setdefault("public_url", "")
    CONFIG.setdefault("ospiti", True)
    CONFIG.setdefault("password_giocatori", "")
    CONFIG.setdefault("oauth", {})
    for prov in PROVIDER:
        CONFIG["oauth"].setdefault(prov, {"attivo": False, "id": "", "secret": ""})   # si compilano da ⚙️ Impostazioni
    CONFIG.setdefault("admin", {"utente": "admin"})
    pw_iniziale = None
    if not CONFIG["admin"].get("hash"):
        pw_iniziale = os.environ.get("MASTER_PASSWORD") or secrets.token_urlsafe(9)
        imposta_password_admin(pw_iniziale)
    salva_config()
    applica_config()
    return pw_iniziale if (nuovo or pw_iniziale) else None


def salva_config():
    db_set("config", CONFIG)


def applica_config():
    global PASSWORD_GIOCATORI, PUBLIC_URL, OSPITI, OAUTH
    PASSWORD_GIOCATORI = CONFIG.get("password_giocatori", "")
    PUBLIC_URL = CONFIG.get("public_url", "").rstrip("/")
    OAUTH = {p: {"id": c["id"], "secret": c["secret"]} for p, c in CONFIG.get("oauth", {}).items()
             if p in PROVIDER and c.get("attivo") and c.get("id") and c.get("secret")}
    OSPITI = bool(CONFIG.get("ospiti", True)) or not OAUTH   # senza provider gli ospiti sono sempre ammessi


def config_pubblica():
    """Configurazione per la UI admin, senza segreti."""
    return {
        "nome_tavolo": CONFIG.get("nome_tavolo", ""), "public_url": CONFIG.get("public_url", ""),
        "ospiti": CONFIG.get("ospiti", True), "password_giocatori": CONFIG.get("password_giocatori", ""),
        "admin_utente": CONFIG["admin"].get("utente", "admin"),
        "oauth": {p: {"attivo": c.get("attivo", False), "id": c.get("id", ""), "secret_impostato": bool(c.get("secret")),
                      "nome": PROVIDER[p]["nome"], "console": PROVIDER[p]["console"]} for p, c in CONFIG["oauth"].items() if p in PROVIDER},
    }


def calcola_versione():
    h = hashlib.sha256()
    for root, _d, files in os.walk(WEB):
        for f in sorted(files):
            with open(os.path.join(root, f), "rb") as fh:
                h.update(f.encode() + fh.read())
    return h.hexdigest()[:12]


# ============================================================================ immagini
def dimensioni_immagine(path):
    """(larghezza, altezza) per SVG/PNG/JPEG/WEBP leggendo solo l'intestazione."""
    with open(path, "rb") as f:
        head = f.read(4096)
    if path.lower().endswith(".svg"):
        txt = head.decode("utf-8", "ignore")
        tag = re.search(r"<svg[^>]*>", txt, re.S)
        tag = tag.group(0) if tag else txt
        w = re.search(r'\swidth="([\d.]+)', tag)
        h = re.search(r'\sheight="([\d.]+)', tag)
        if w and h:
            return int(float(w.group(1))), int(float(h.group(1)))
        vb = re.search(r'viewBox="[\d.\-]+[ ,]+[\d.\-]+[ ,]+([\d.]+)[ ,]+([\d.]+)"', tag)
        if vb:
            return int(float(vb.group(1))), int(float(vb.group(2)))
        return 1000, 1000
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", head[16:24])
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        chunk = head[12:16]
        if chunk == b"VP8X":
            return 1 + int.from_bytes(head[24:27], "little"), 1 + int.from_bytes(head[27:30], "little")
        if chunk == b"VP8 ":
            w, h = struct.unpack("<HH", head[26:30])
            return w & 0x3FFF, h & 0x3FFF
        if chunk == b"VP8L":
            b = int.from_bytes(head[21:25], "little")
            return (b & 0x3FFF) + 1, ((b >> 14) & 0x3FFF) + 1
    if head[:2] == b"\xff\xd8":
        with open(path, "rb") as f:
            f.read(2)
            while True:
                m = f.read(2)
                if len(m) < 2 or m[0] != 0xFF:
                    break
                if m[1] in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                    f.read(3)
                    h, w = struct.unpack(">HH", f.read(4))
                    return w, h
                seg = struct.unpack(">H", f.read(2))[0]
                f.seek(seg - 2, 1)
    return 1000, 1000


# ============================================================================ catalogo avventure
def leggi_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def carica_avventura(aid):
    base = os.path.join(AVV_DIR, aid)
    man = leggi_json(os.path.join(base, "avventura.json"), None)
    if not isinstance(man, dict):
        return None
    man["id"] = aid
    mappe = []
    cart = os.path.join(base, "mappe")
    if os.path.isdir(cart):
        for nome in sorted(os.listdir(cart)):
            stem, ext = os.path.splitext(nome)
            if ext.lower() not in IMG_EXT:
                continue
            meta = leggi_json(os.path.join(cart, stem + ".json"), {})
            try:
                w, h = dimensioni_immagine(os.path.join(cart, nome))
            except (OSError, struct.error):
                w, h = 1000, 1000
            sc = {
                "id": stem, "titolo": meta.get("titolo") or stem.replace("_", " ").strip().capitalize(),
                "gruppo": meta.get("gruppo", ""), "ordine": meta.get("ordine", 999),
                "file": f"avventure/{aid}/mappe/{nome}", "larghezza": meta.get("larghezza", w), "altezza": meta.get("altezza", h),
            }
            for k in ("griglia", "inizio", "note_master", "descrizione"):
                if meta.get(k) is not None:
                    sc[k] = meta[k]
            if sc.get("griglia") and not sc["griglia"].get("cella"):
                sc.pop("griglia")
            mappe.append(sc)
    mappe.sort(key=lambda s: (s["ordine"], s["id"]))
    documenti = []
    for d in man.get("documenti", []):
        if isinstance(d, dict) and os.path.isfile(os.path.join(base, "documenti", d.get("file", ""))):
            documenti.append({"file": d["file"], "titolo": d.get("titolo", d["file"]), "solo_master": bool(d.get("solo_master"))})
    return {
        "id": aid,
        "titolo": man.get("titolo", aid), "sottotitolo": man.get("sottotitolo", ""), "descrizione": man.get("descrizione", ""),
        "livello": man.get("livello", ""), "giocatori": man.get("giocatori", ""), "durata": man.get("durata", ""),
        "copertina": man.get("copertina", ""),
        "mappe": mappe,
        "personaggi": leggi_json(os.path.join(base, "personaggi.json"), []),
        "mostri": leggi_json(os.path.join(base, "mostri.json"), []),
        "documenti": documenti,
    }


def firma_catalogo():
    firma = []
    if not os.path.isdir(AVV_DIR):
        return ()
    for root, _dirs, files in os.walk(AVV_DIR):
        for f in files:
            try:
                st = os.stat(os.path.join(root, f))
                firma.append((root, f, st.st_mtime_ns, st.st_size))
            except OSError:
                pass
    return tuple(sorted(firma))


def scansiona():
    global CATALOGO
    nuovo = {}
    if os.path.isdir(AVV_DIR):
        for aid in sorted(os.listdir(AVV_DIR)):
            if ID_RE.match(aid) and os.path.isdir(os.path.join(AVV_DIR, aid)):
                a = carica_avventura(aid)
                if a:
                    nuovo[aid] = a
    with LOCK:
        CATALOGO = nuovo


def osservatore():
    """Rileva nuove avventure/mappe copiate sul server e avvisa tutti, senza riavvii."""
    ultima = firma_catalogo()
    while True:
        time.sleep(4)
        f = firma_catalogo()
        if f != ultima:
            ultima = f
            scansiona()
            chiudi = False
            with LOCK:
                if ATTIVA and ATTIVA not in CATALOGO:
                    attiva_avventura(None)
                    chiudi = True
            if chiudi:
                imposta_sessione("chiusa")
            invia({"t": "catalogo"})


def catalogo_breve():
    with LOCK:
        return [{k: a[k] for k in ("id", "titolo", "sottotitolo", "descrizione", "livello", "giocatori", "durata")}
                | {"mappe": len(a["mappe"]), "personaggi": len(a["personaggi"]), "documenti": a["documenti"]} for a in CATALOGO.values()]


def avventura_per(ruolo):
    with LOCK:
        a = CATALOGO.get(ATTIVA)
        if not a:
            return {"id": None, "titolo": "Nessuna avventura", "mappe": [], "personaggi": [], "mostri": [], "documenti": []}
        a = json.loads(json.dumps(a))
    if ruolo != "master":
        a["mostri"] = [m for m in a["mostri"] if m.get("alleato")]
        a["documenti"] = [d for d in a["documenti"] if not d["solo_master"]]
        for s in a["mappe"]:
            s.pop("note_master", None)
    return a


# ============================================================================ partite
def stato_vuoto(aid):
    a = CATALOGO.get(aid) or {"mappe": []}
    return {
        "versione": 2, "avventura": aid,
        "scena": a["mappe"][0]["id"] if a["mappe"] else None,
        "nebbia": {}, "pedine": {}, "log": [],
        "iniziativa": {"ordine": [], "turno": 0, "round": 1},
        "schede": {}, "note_master": "",
    }


def file_partita(aid):
    return os.path.join(PARTITE, f"{aid}.json")


def attiva_avventura(aid):
    """Salva la partita corrente e carica (o crea) quella dell'avventura indicata."""
    global ATTIVA, STATE
    with LOCK:
        if ATTIVA and STATE:
            _salva()
        ATTIVA = aid
        st = db_partita(aid) if aid else None
        if not isinstance(st, dict):
            st = stato_vuoto(aid)
        base = stato_vuoto(aid)
        for k, v in base.items():
            st.setdefault(k, v)
        ids = {s["id"] for s in CATALOGO.get(aid, {}).get("mappe", [])}
        if st.get("scena") not in ids:
            st["scena"] = base["scena"]
        STATE = st
        pg_validi = {p["id"] for p in CATALOGO.get(aid, {}).get("personaggi", [])}
        for u in USERS.values():
            if u.get("char") and u["char"] not in pg_validi:
                u["char"] = None
    salva_presto()


def salva_presto():
    global _save_timer
    with LOCK:
        if _save_timer:
            return
        _save_timer = threading.Timer(1.0, _salva)
        _save_timer.daemon = True
        _save_timer.start()


def _scrivi(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    os.replace(tmp, path)


def _salva():
    global _save_timer
    with LOCK:
        _save_timer = None
        ora = time.time()
        DB.execute("BEGIN")
        try:
            DB.execute("INSERT INTO impostazioni(chiave, valore) VALUES('attiva', ?) ON CONFLICT(chiave) DO UPDATE SET valore=excluded.valore", (json.dumps(ATTIVA),))
            DB.execute("DELETE FROM utenti")
            DB.executemany("INSERT INTO utenti(id,nome,account,admin,master,visto,dati) VALUES(?,?,?,?,?,?,?)",
                           [(cid, u.get("name"), u.get("account"), int(bool(u.get("admin"))), int(bool(u.get("master_ok") or u.get("admin"))),
                             u.get("seen"), json.dumps(u, ensure_ascii=False)) for cid, u in USERS.items()])
            DB.execute("DELETE FROM account")
            DB.executemany("INSERT INTO account VALUES(?,?)", list(ACCOUNTS.items()))
            if ATTIVA:
                DB.execute("INSERT INTO partite VALUES(?,?,?) ON CONFLICT(avventura) DO UPDATE SET stato=excluded.stato, aggiornata=excluded.aggiornata",
                           (ATTIVA, json.dumps(STATE, ensure_ascii=False), ora))
            DB.execute("COMMIT")
        except Exception:
            DB.execute("ROLLBACK")
            raise


def carica_tutto():
    global USERS, ACCOUNTS
    scansiona()
    with LOCK:
        USERS = {r[0]: json.loads(r[1]) for r in DB.execute("SELECT id, dati FROM utenti")}
        ACCOUNTS = dict(DB.execute("SELECT chiave, utente_id FROM account").fetchall())
    aid = db_get("attiva")
    attiva_avventura(aid if aid in CATALOGO else None)   # ricordata, ma il tavolo resta chiuso finché l'admin non lo apre


def imposta_sessione(stato):
    global SESSIONE
    SESSIONE = stato
    invia({"t": "sessione", "sessione": stato, "attiva": ATTIVA})


# ============================================================================ dadi
DICE_RE = re.compile(r"([+-]?)\s*(?:(\d*)d(\d+|%)(?:(kh|kl)(\d+))?|(\d+))", re.I)


def tira(espr):
    """Interpreta e tira un'espressione tipo '2d20kh1+5', '1d8+3+1d6', 'd%'."""
    s = espr.replace(" ", "").lower()
    if not s or len(s) > 120:
        raise ValueError("espressione non valida")
    pos, parti, totale, dadi_tot = 0, [], 0, 0
    nat20 = nat1 = False
    for m in DICE_RE.finditer(s):
        if m.start() != pos:
            raise ValueError("espressione non valida")
        pos = m.end()
        segno = -1 if m.group(1) == "-" else 1
        if m.group(6) is not None:
            v = int(m.group(6))
            parti.append({"tipo": "num", "valore": v * segno})
            totale += v * segno
            continue
        n = int(m.group(2) or 1)
        facce = 100 if m.group(3) == "%" else int(m.group(3))
        if n < 1 or n > 100 or facce < 2 or facce > 1000:
            raise ValueError("troppi dadi")
        dadi_tot += n
        if dadi_tot > 200:
            raise ValueError("troppi dadi")
        valori = [secrets.randbelow(facce) + 1 for _ in range(n)]
        tenuti = list(range(n))
        if m.group(4):
            k = max(1, min(n, int(m.group(5))))
            ordinati = sorted(range(n), key=lambda i: valori[i], reverse=(m.group(4) == "kh"))
            tenuti = sorted(ordinati[:k])
        somma = sum(valori[i] for i in tenuti)
        if facce == 20:
            nat20 = nat20 or any(valori[i] == 20 for i in tenuti)
            nat1 = nat1 or any(valori[i] == 1 for i in tenuti)
        parti.append({"tipo": "dadi", "n": n, "facce": facce, "valori": valori, "tenuti": tenuti, "segno": segno, "somma": somma * segno})
        totale += somma * segno
    if pos != len(s) or not parti:
        raise ValueError("espressione non valida")
    return {"espr": espr.strip(), "parti": parti, "totale": totale, "critico": nat20, "fallimento": nat1}


# ============================================================================ broadcast
def visibile(evento, ruolo, cid):
    t = evento.get("t")
    if ruolo == "master":
        return evento
    if t == "pedina" and evento["pedina"].get("nascosta"):
        return {"t": "pedina_via", "id": evento["pedina"]["id"]}
    if t == "log":
        e = evento["voce"]
        if e.get("segreto") and e.get("da") != cid:
            return None
    return evento


def invia(evento, solo=None):
    with LOCK:
        for cid, c in list(CLIENTS.items()):
            if solo and cid not in solo:
                continue
            ev = visibile(evento, c["role"], cid)
            if ev is not None:
                c["q"].put(ev)


def online():
    with LOCK:
        return [{"id": cid, "name": USERS[cid]["name"], "color": USERS[cid]["color"], "role": USERS[cid]["role"], "char": USERS[cid].get("char"), "avatar": USERS[cid].get("avatar", ""), "admin": bool(USERS[cid].get("admin"))}
                for cid in CLIENTS if cid in USERS]


def stato_per(cid):
    u = USERS.get(cid, {})
    ruolo = u.get("role", "giocatore")
    with LOCK:
        s = json.loads(json.dumps(STATE))
    if ruolo != "master":
        s["pedine"] = {k: v for k, v in s["pedine"].items() if not v.get("nascosta")}
        s["log"] = [e for e in s["log"] if not e.get("segreto") or e.get("da") == cid]
        s["note_master"] = ""
    s["online"] = online()
    s["io"] = {"id": cid, **{k: u.get(k) for k in ("name", "color", "role", "char", "avatar", "provider")}, "admin": bool(u.get("admin"))}
    s["avv"] = avventura_per(ruolo)
    s["sessione"] = SESSIONE
    if ruolo == "master" or u.get("admin"):
        s["catalogo"] = catalogo_breve()
        s["attiva"] = ATTIVA
    return s


def aggiungi_log(voce):
    voce.setdefault("id", uuid.uuid4().hex[:10])
    voce.setdefault("ora", time.time())
    with LOCK:
        STATE["log"].append(voce)
        del STATE["log"][:-MAX_LOG]
    invia({"t": "log", "voce": voce})
    salva_presto()


def sistema(testo):
    aggiungi_log({"tipo": "sistema", "testo": testo})


# ============================================================================ operazioni
def is_master(cid):
    return USERS.get(cid, {}).get("role") == "master"


def puo_muovere(cid, pedina):
    if is_master(cid):
        return True
    return pedina.get("proprietario") == cid or (pedina.get("pg") and pedina.get("pg") == USERS.get(cid, {}).get("char"))


COLORE_RE = re.compile(r"^#[0-9a-fA-F]{3,8}$")
NOMI_RISERVATI = {"admin", "amministratore", "master", "sistema"}


def colore_valido(c, default="#c0392b"):
    c = str(c or "").strip()
    return c if COLORE_RE.match(c) else default


def nome_riservato(nome):
    n = re.sub(r"\s+", " ", str(nome or "")).strip().lower()
    return n in NOMI_RISERVATI or n == CONFIG.get("admin", {}).get("utente", "admin").lower()


LIMITI = {"veloce": (20.0, 30.0), "normale": (5.0, 15.0), "accesso": (2.0, 10.0)}   # richieste al secondo, raffica massima
OP_VELOCI = {"pedina_muovi", "righello"}   # trascinamenti: il client ne manda ~12 al secondo
_SECCHI = {}
_SECCHI_LOCK = threading.Lock()


def troppe_richieste(chi, tipo):
    """Token bucket per giocatore (o IP): True se la richiesta va rifiutata."""
    ritmo, raffica = LIMITI[tipo]
    ora = time.monotonic()
    with _SECCHI_LOCK:
        if len(_SECCHI) > 5000:   # pulizia dei secchi vecchi
            for k in [k for k, (_, t) in _SECCHI.items() if ora - t > 60]:
                del _SECCHI[k]
        gettoni, prima = _SECCHI.get((chi, tipo), (raffica, ora))
        gettoni = min(raffica, gettoni + (ora - prima) * ritmo)
        if gettoni < 1:
            _SECCHI[(chi, tipo)] = (gettoni, ora)
            return True
        _SECCHI[(chi, tipo)] = (gettoni - 1, ora)
        return False


CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https:; "
       "media-src 'self' data: blob:; connect-src 'self'; frame-src 'self'; object-src 'none'; base-uri 'none'; "
       "form-action 'self'; frame-ancestors 'self'")


def pg_occupato(pg, cid):
    """Il personaggio è già in mano a un altro giocatore collegato?"""
    return any(k != cid and k in USERS and USERS[k].get("char") == pg for k in CLIENTS)


def pulisci_pedina(d):
    out = {}
    for k in ("id", "scena", "x", "y", "nome", "colore", "icona", "taglia", "pf", "pfmax", "ca", "nascosta", "condizioni",
              "tipo", "pg", "mostro", "proprietario", "slot"):
        if k in d:
            out[k] = d[k]
    out["taglia"] = max(0.5, min(6, float(out.get("taglia", 1) or 1)))
    out["nome"] = str(out.get("nome", "Pedina"))[:40]
    if "condizioni" in out:
        out["condizioni"] = [str(c)[:20] for c in out["condizioni"]][:12]
    return out


def crea_pedina_pg(cid, pg, colore):
    info = next((p for p in CATALOGO.get(ATTIVA, {}).get("personaggi", []) if p.get("id") == pg), None)
    if not info:
        return
    with LOCK:
        for p in STATE["pedine"].values():
            if p.get("pg") == pg:
                p["proprietario"] = cid
                p["colore"] = colore
                invia({"t": "pedina", "pedina": p})
                return
        sch = STATE["schede"].setdefault(pg, {"pf": info.get("pf", 10)})
        n = sum(1 for p in STATE["pedine"].values() if p.get("pg"))
        pid = uuid.uuid4().hex[:10]
        p = STATE["pedine"][pid] = {
            "id": pid, "scena": STATE["scena"], "x": None, "y": None, "slot": n,
            "nome": info.get("nome", "Eroe"), "colore": colore, "icona": info.get("icona", "🙂"), "taglia": 1,
            "pf": sch.get("pf", info.get("pf", 10)), "pfmax": info.get("pf", 10), "ca": info.get("ca", 10),
            "tipo": "pg", "pg": pg, "proprietario": cid, "condizioni": [],
        }
    invia({"t": "pedina", "pedina": p})
    salva_presto()


def scrivi_meta_mappa(scena_id, aggiorna):
    """Aggiorna il file <mappa>.json accanto all'immagine (formato unificato)."""
    a = CATALOGO.get(ATTIVA)
    sc = next((s for s in (a or {}).get("mappe", []) if s["id"] == scena_id), None)
    if not sc:
        raise ValueError("mappa inesistente")
    path = os.path.join(AVV_DIR, ATTIVA, "mappe", scena_id + ".json")
    meta = leggi_json(path, {})
    meta.update(aggiorna)
    _scrivi(path, meta)


def op(cid, d):
    t = d.get("op")
    u = USERS[cid]
    master = is_master(cid)

    if t == "tira":
        r = tira(str(d.get("espr", "")))
        voce = {"tipo": "tiro", "da": cid, "chi": u["name"], "colore": u["color"], "etichetta": str(d.get("etichetta", ""))[:80],
                "segreto": bool(d.get("segreto")), "modo": d.get("modo", ""), **r}
        if d.get("danni"):
            espr2 = str(d["danni"])
            if r["critico"]:  # colpo critico: si raddoppiano i dadi dei danni
                espr2 = re.sub(r"(\d*)d(\d+)", lambda m: f"{2 * int(m.group(1) or 1)}d{m.group(2)}", espr2)
            voce["danni"] = tira(espr2)
        aggiungi_log(voce)
        return {"ok": True, "tiro": voce}

    if t == "chat":
        testo = str(d.get("testo", "")).strip()[:600]
        if not testo:
            return {"ok": False}
        aggiungi_log({"tipo": "chat", "da": cid, "chi": u["name"], "colore": u["color"], "testo": testo, "segreto": bool(d.get("segreto"))})
        return {"ok": True}

    if t == "ping":
        invia({"t": "ping", "x": float(d["x"]), "y": float(d["y"]), "colore": u["color"], "chi": u["name"], "centra": bool(d.get("centra")) and master})
        return {"ok": True}

    if t == "righello":
        invia({"t": "righello", "da": cid, "colore": u["color"], "punti": d.get("punti")})
        return {"ok": True}

    if t == "scegli_pg":
        pg = d.get("pg") or None
        validi = {p["id"] for p in CATALOGO.get(ATTIVA, {}).get("personaggi", [])}
        if pg and pg not in validi:
            return {"ok": False, "errore": "personaggio inesistente"}
        with LOCK:   # controllo e assegnazione insieme: due giocatori non possono prendere lo stesso PG nello stesso istante
            if pg and not master and pg_occupato(pg, cid):
                return {"ok": False, "errore": "personaggio già scelto da un altro giocatore"}
            u["char"] = pg
            if pg and not master:
                crea_pedina_pg(cid, pg, u["color"])
        invia({"t": "online", "online": online()})
        salva_presto()
        return {"ok": True}

    if t == "pedina_muovi":
        with LOCK:
            p = STATE["pedine"].get(d.get("id"))
            if not p or not puo_muovere(cid, p):
                return {"ok": False, "errore": "non puoi muovere questa pedina"}
            p["x"], p["y"] = float(d["x"]), float(d["y"])
        if d.get("finale"):
            salva_presto()
        invia({"t": "pedina", "pedina": p, "da": cid, "trascina": not d.get("finale")})
        return {"ok": True}

    if t == "pedina_salva":
        nuova = pulisci_pedina(d.get("pedina", {}))
        with LOCK:
            vecchia = STATE["pedine"].get(nuova.get("id"))
            if vecchia:
                if not puo_muovere(cid, vecchia):
                    return {"ok": False, "errore": "non è la tua pedina"}
                if not master:
                    # Il giocatore cambia solo posizione, PF e condizioni della sua pedina: nome, icona, scena… restano del Master.
                    nuova = {k: nuova[k] for k in ("x", "y", "pf", "condizioni") if k in nuova}
                    if "pf" in nuova:
                        pfmax = vecchia.get("pfmax") or 0
                        nuova["pf"] = max(0, min(int(nuova["pf"] or 0), pfmax)) if pfmax else vecchia.get("pf")
                vecchia.update(nuova)
                p = vecchia
            else:
                # Solo il Master crea pedine nuove: quelle dei giocatori nascono da crea_pedina_pg (scegli_pg).
                if not master:
                    return {"ok": False, "errore": "solo il Master può aggiungere pedine"}
                nuova["id"] = uuid.uuid4().hex[:10]
                nuova.setdefault("scena", STATE["scena"])
                STATE["pedine"][nuova["id"]] = nuova
                p = nuova
            if p.get("pg") and "pf" in p:
                STATE["schede"].setdefault(p["pg"], {})["pf"] = p["pf"]
        if p.get("pg"):
            invia({"t": "scheda", "id": p["pg"], "scheda": STATE["schede"][p["pg"]]})
        invia({"t": "pedina", "pedina": p})
        salva_presto()
        return {"ok": True, "id": p["id"]}

    if t == "pedina_elimina":
        with LOCK:
            p = STATE["pedine"].get(d.get("id"))
            if not p or not (master or p.get("proprietario") == cid):
                return {"ok": False}
            del STATE["pedine"][p["id"]]
            STATE["iniziativa"]["ordine"] = [x for x in STATE["iniziativa"]["ordine"] if x.get("pedina") != p["id"]]
        invia({"t": "pedina_via", "id": p["id"]})
        invia({"t": "iniziativa", "iniziativa": STATE["iniziativa"]})
        salva_presto()
        return {"ok": True}

    if t == "scheda":
        pid = str(d.get("id"))
        if not master and u.get("char") != pid:
            return {"ok": False, "errore": "non è la tua scheda"}
        with LOCK:
            sch = STATE["schede"].setdefault(pid, {})
            for k in ("pf", "pft", "slot", "usi", "note", "condizioni"):
                if k in d.get("scheda", {}):
                    sch[k] = d["scheda"][k]
            if isinstance(sch.get("note"), str):
                sch["note"] = sch["note"][:5000]
            cambiate = []
            for p in STATE["pedine"].values():
                if p.get("pg") == pid and "pf" in sch:
                    p["pf"] = sch["pf"]
                    cambiate.append(p)
        for p in cambiate:
            invia({"t": "pedina", "pedina": p})
        invia({"t": "scheda", "id": pid, "scheda": sch})
        salva_presto()
        return {"ok": True}

    if t == "iniziativa":
        azione = d.get("azione")
        with LOCK:
            ini = STATE["iniziativa"]
            if azione == "aggiungi":
                voce = {"id": uuid.uuid4().hex[:8], "nome": str(d.get("nome", "?"))[:40], "valore": int(d.get("valore", 0)),
                        "pedina": d.get("pedina"), "colore": colore_valido(d.get("colore"), u["color"]), "nascosta": bool(d.get("nascosta")) and master}
                if not master:
                    voce["da"] = cid
                    ped = STATE["pedine"].get(voce["pedina"]) if voce["pedina"] else None
                    if voce["pedina"] and not (ped and puo_muovere(cid, ped)):
                        return {"ok": False, "errore": "non è la tua pedina"}
                ini["ordine"] = [x for x in ini["ordine"] if not (voce["pedina"] and x.get("pedina") == voce["pedina"])]
                ini["ordine"].append(voce)
                ini["ordine"].sort(key=lambda x: -x["valore"])
            elif not master:
                return {"ok": False, "errore": "solo il Master gestisce i turni"}
            elif azione == "prossimo" and ini["ordine"]:
                ini["turno"] += 1
                if ini["turno"] >= len(ini["ordine"]):
                    ini["turno"] = 0
                    ini["round"] += 1
            elif azione == "precedente" and ini["ordine"]:
                ini["turno"] -= 1
                if ini["turno"] < 0:
                    ini["turno"] = len(ini["ordine"]) - 1
                    ini["round"] = max(1, ini["round"] - 1)
            elif azione == "rimuovi":
                ini["ordine"] = [x for x in ini["ordine"] if x["id"] != d.get("id")]
                ini["turno"] = min(ini["turno"], max(0, len(ini["ordine"]) - 1))
            elif azione == "valore":
                for x in ini["ordine"]:
                    if x["id"] == d.get("id"):
                        x["valore"] = int(d.get("valore", 0))
                ini["ordine"].sort(key=lambda x: -x["valore"])
            elif azione == "svuota":
                STATE["iniziativa"] = {"ordine": [], "turno": 0, "round": 1}
            ini = STATE["iniziativa"]
        invia({"t": "iniziativa", "iniziativa": ini})
        if azione == "prossimo" and ini["ordine"]:
            cur = ini["ordine"][ini["turno"]]
            if not cur.get("nascosta"):
                sistema(f"🔔 Round {ini['round']}: tocca a {cur['nome']}!")
        salva_presto()
        return {"ok": True}

    # ------------------------------------------------------------ apertura/chiusura del tavolo
    if t == "sessione_apri":
        if not u.get("admin"):
            return {"ok": False, "errore": "solo l'amministratore apre il tavolo"}
        aid = str(d.get("id") or ATTIVA or "")
        if aid not in CATALOGO:
            return {"ok": False, "errore": "scegli un'avventura"}
        if aid != ATTIVA:
            attiva_avventura(aid)
        imposta_sessione("lobby")
        invia({"t": "ricarica"})
        return {"ok": True}
    if t == "nomina_master":
        if not u.get("admin"):
            return {"ok": False, "errore": "solo l'amministratore sceglie il Master"}
        uid = str(d.get("id"))
        if uid not in USERS:
            return {"ok": False, "errore": "utente inesistente"}
        toccati = []
        with LOCK:
            if d.get("master", True):
                for k, v in USERS.items():   # un solo Master per partita
                    if k != uid and v.get("role") == "master":
                        v["role"] = "giocatore"
                        if not v.get("admin"):
                            v["master_ok"] = False
                        toccati.append(k)
                USERS[uid].update({"role": "master", "master_ok": True, "char": None})
            else:
                USERS[uid]["role"] = "giocatore"
                if not USERS[uid].get("admin"):
                    USERS[uid]["master_ok"] = False
            toccati.append(uid)
            for k in toccati:
                if k in CLIENTS:
                    CLIENTS[k]["role"] = USERS[k]["role"]
                    CLIENTS[k]["q"].put({"t": "ruolo", "ruolo": USERS[k]["role"]})
        invia({"t": "online", "online": online()})
        if d.get("master", True):
            sistema(f"👑 {USERS[uid]['name']} sarà il Master.")
        salva_presto()
        return {"ok": True}

    if t == "sessione_inizia":
        if not (master or u.get("admin")):
            return {"ok": False, "errore": "solo il Master fa iniziare la partita"}
        imposta_sessione("in_corso")
        sistema("⚔️ La partita ha inizio!")
        return {"ok": True}
    if t == "sessione_pausa":
        if not master:
            return {"ok": False}
        imposta_sessione("lobby")
        return {"ok": True}
    if t == "sessione_chiudi":
        if not (master or u.get("admin")):
            return {"ok": False, "errore": "solo admin o Master chiudono il tavolo"}
        _salva()
        imposta_sessione("chiusa")
        return {"ok": True}

    # ------------------------------------------------------------ impostazioni (solo admin)
    if t and t.startswith("imp_"):
        if not u.get("admin"):
            return {"ok": False, "errore": "solo l'amministratore può cambiare le impostazioni"}
        return impostazioni(cid, t, d)

    # ------------------------------------------------------------ solo Master
    if not master:
        return {"ok": False, "errore": "solo il Master può farlo"}

    if t == "scena":
        with LOCK:
            STATE["scena"] = str(d.get("id"))
            mossi = []
            if d.get("porta_gruppo", True):
                for p in STATE["pedine"].values():
                    if p.get("pg"):
                        p["scena"], p["x"], p["y"] = STATE["scena"], None, None
                        mossi.append(p)
        invia({"t": "scena", "id": STATE["scena"]})
        for p in mossi:
            invia({"t": "pedina", "pedina": p})
        sistema("🗺️ Il Master ha cambiato mappa.")
        salva_presto()
        return {"ok": True}

    if t == "griglia":
        g = d.get("griglia") or {}
        scrivi_meta_mappa(str(d["id"]), {"griglia": {"cella": float(g.get("cella", 0)), "ox": float(g.get("ox", 0)), "oy": float(g.get("oy", 0)), "mostra": bool(g.get("mostra"))}})
        scansiona()
        invia({"t": "catalogo"})
        return {"ok": True}

    if t == "nebbia":
        sc = str(d.get("scena", STATE["scena"]))
        with LOCK:
            nb = STATE["nebbia"].setdefault(sc, {"attiva": False, "celle": []})
            if "attiva" in d:
                nb["attiva"] = bool(d["attiva"])
            if d.get("azione") == "rivela":
                nb["celle"] = sorted(set(nb["celle"]) | set(d.get("celle", [])))
            elif d.get("azione") == "copri":
                nb["celle"] = sorted(set(nb["celle"]) - set(d.get("celle", [])))
            elif d.get("azione") == "copri_tutto":
                nb["celle"] = []
        invia({"t": "nebbia", "scena": sc, "nebbia": nb})
        salva_presto()
        return {"ok": True}

    if t == "note_master":
        with LOCK:
            STATE["note_master"] = str(d.get("testo", ""))[:20000]
        salva_presto()
        return {"ok": True}

    if t == "svuota_log":
        with LOCK:
            STATE["log"] = []
        invia({"t": "ricarica"})
        salva_presto()
        return {"ok": True}

    if t == "pulisci_scena":
        sc = str(d.get("scena", STATE["scena"]))
        with LOCK:
            via = [k for k, p in STATE["pedine"].items() if p.get("scena") == sc and not p.get("pg")]
            for k in via:
                del STATE["pedine"][k]
        for k in via:
            invia({"t": "pedina_via", "id": k})
        salva_presto()
        return {"ok": True}

    if t == "reset_partita":
        with LOCK:
            STATE.clear()
            STATE.update(stato_vuoto(ATTIVA))
        invia({"t": "ricarica"})
        salva_presto()
        return {"ok": True}

    if t == "avventura_attiva":
        aid = str(d.get("id"))
        if aid not in CATALOGO:
            return {"ok": False, "errore": "avventura inesistente"}
        attiva_avventura(aid)
        invia({"t": "ricarica"})
        sistema(f"📚 Si gioca: {CATALOGO[aid]['titolo']}")
        return {"ok": True}

    if t == "avventura_nuova":
        titolo = str(d.get("titolo", "")).strip()
        if not titolo:
            return {"ok": False, "errore": "serve un titolo"}
        aid = nuova_avventura(titolo)
        invia({"t": "catalogo"})
        return {"ok": True, "id": aid}

    if t == "avventura_info":
        man_p = os.path.join(AVV_DIR, ATTIVA, "avventura.json")
        man = leggi_json(man_p, {})
        for k in ("titolo", "sottotitolo", "descrizione", "livello", "giocatori", "durata"):
            if k in d:
                man[k] = str(d[k])[:2000]
        _scrivi(man_p, man)
        scansiona()
        invia({"t": "catalogo"})
        return {"ok": True}

    if t == "mappa_meta":
        agg = {k: d[k] for k in ("titolo", "ordine", "note_master", "gruppo") if k in d}
        if "ordine" in agg:
            agg["ordine"] = int(agg["ordine"])
        scrivi_meta_mappa(str(d["id"]), agg)
        scansiona()
        invia({"t": "catalogo"})
        return {"ok": True}

    if t == "mappa_elimina":
        mid = str(d.get("id"))
        a = CATALOGO.get(ATTIVA, {})
        sc = next((x for x in a.get("mappe", []) if x["id"] == mid), None)
        if not sc:
            return {"ok": False, "errore": "mappa inesistente"}
        if len(a["mappe"]) <= 1:
            return {"ok": False, "errore": "l'avventura deve avere almeno una mappa"}
        cart = os.path.join(AVV_DIR, ATTIVA, "mappe")
        for f in os.listdir(cart):
            if os.path.splitext(f)[0] == mid:
                os.remove(os.path.join(cart, f))
        scansiona()
        with LOCK:
            if STATE.get("scena") == mid:
                STATE["scena"] = CATALOGO[ATTIVA]["mappe"][0]["id"]
                invia({"t": "scena", "id": STATE["scena"]})
        invia({"t": "catalogo"})
        salva_presto()
        return {"ok": True}

    if t == "documento_elimina":
        nome = os.path.basename(str(d.get("file", "")))
        base = os.path.join(AVV_DIR, ATTIVA)
        man_p = os.path.join(base, "avventura.json")
        man = leggi_json(man_p, {})
        man["documenti"] = [x for x in man.get("documenti", []) if x.get("file") != nome]
        _scrivi(man_p, man)
        try:
            os.remove(os.path.join(base, "documenti", nome))
        except OSError:
            pass
        scansiona()
        invia({"t": "catalogo"})
        return {"ok": True}

    if t == "avventura_elimina":
        aid = str(d.get("id"))
        if aid == ATTIVA:
            return {"ok": False, "errore": "non puoi eliminare l'avventura in corso"}
        if not ID_RE.match(aid) or aid not in CATALOGO:
            return {"ok": False, "errore": "avventura inesistente"}
        shutil.rmtree(os.path.join(AVV_DIR, aid), ignore_errors=True)
        with LOCK:
            DB.execute("DELETE FROM partite WHERE avventura=?", (aid,))
        scansiona()
        invia({"t": "catalogo"})
        return {"ok": True}

    return {"ok": False, "errore": "operazione sconosciuta"}


def impostazioni(cid, t, d):
    if t == "imp_leggi":
        utenti = sorted(({"id": k, "nome": v.get("name"), "account": v.get("account", ""), "provider": v.get("provider", "ospite"),
                          "avatar": v.get("avatar", ""), "master": bool(v.get("master_ok") or v.get("admin")), "admin": bool(v.get("admin")),
                          "online": k in CLIENTS, "visto": v.get("seen", 0), "io": k == cid} for k, v in USERS.items()),
                        key=lambda x: -(x["visto"] or 0))
        return {"ok": True, "config": config_pubblica(), "utenti": utenti}
    if t == "imp_salva":
        c = d.get("config", {})
        nuovo = json.loads(json.dumps(CONFIG))   # si lavora su una copia: se qualcosa non va, CONFIG resta com'era
        for k in ("nome_tavolo", "password_giocatori"):
            if k in c:
                nuovo[k] = str(c[k]).strip()[:200]
        if "public_url" in c:
            url = str(c["public_url"]).strip()
            if url and not re.match(r"^https?://", url, re.I):
                url = "https://" + url                        # «dnd.esempio.it» → «https://dnd.esempio.it»
            url = re.sub(r"^(https?://[^/\s]+).*$", r"\1", url).lower()   # niente percorsi né barra finale
            if url and not re.match(r"^https?://[a-z0-9.\-]+(:\d+)?$", url) or (url and "." not in url and "localhost" not in url):
                return {"ok": False, "errore": "L'indirizzo pubblico deve essere tipo https://dnd.esempio.it"}
            nuovo["public_url"] = url
        if "ospiti" in c:
            nuovo["ospiti"] = bool(c["ospiti"])
        for prov, conf in (c.get("oauth") or {}).items():
            if prov not in PROVIDER:
                continue
            dest = nuovo["oauth"].setdefault(prov, {})
            if "attivo" in conf:
                dest["attivo"] = bool(conf["attivo"])
            if "id" in conf:
                nuovo_id = re.sub(r"\s+", "", str(conf["id"]))[:300]
                formato = {"discord": r"^\d{15,25}$", "google": r"^[\w\-]+\.apps\.googleusercontent\.com$", "github": r"^[A-Za-z0-9._\-]{10,60}$"}[prov]
                attivo = bool(conf.get("attivo", dest.get("attivo")))
                if nuovo_id and not re.match(formato, nuovo_id):
                    if attivo:   # si controllano solo i provider accesi
                        esempi = {"discord": "deve contenere solo numeri, es. 1570503076421439708",
                                  "google": "deve finire con .apps.googleusercontent.com",
                                  "github": "deve essere un codice di lettere e numeri, senza spazi"}
                        return {"ok": False, "errore": f"{PROVIDER[prov]['nome']}: il Client ID non sembra giusto ({esempi[prov]}). Controlla anche che il browser non l'abbia compilato da solo."}
                    nuovo_id = dest.get("id", "")   # provider spento con un valore strano: si lascia quello di prima
                dest["id"] = nuovo_id
            if conf.get("secret"):          # vuoto = lascia quello esistente
                dest["secret"] = str(conf["secret"]).strip()[:300]
            if conf.get("rimuovi_secret"):
                dest["secret"] = ""
        CONFIG.clear()
        CONFIG.update(nuovo)
        salva_config()
        applica_config()
        invia({"t": "info"})
        return {"ok": True, "config": config_pubblica()}
    if t == "imp_admin":
        if not verifica_admin(CONFIG["admin"].get("utente"), d.get("attuale", "")):
            return {"ok": False, "errore": "la password attuale non è corretta"}
        nuovo_utente = str(d.get("utente", "")).strip()[:40]
        if nuovo_utente:
            CONFIG["admin"]["utente"] = nuovo_utente
        if d.get("nuova"):
            if len(d["nuova"]) < 8:
                return {"ok": False, "errore": "la nuova password deve avere almeno 8 caratteri"}
            imposta_password_admin(str(d["nuova"]))
        salva_config()
        return {"ok": True}
    if t == "imp_partite":
        _salva()
        return {"ok": True, "partite": elenco_partite()}
    if t == "imp_partita_azzera":
        aid = str(d.get("id"))
        with LOCK:
            if aid == ATTIVA:
                STATE.clear()
                STATE.update(stato_vuoto(aid))
            DB.execute("DELETE FROM partite WHERE avventura=?", (aid,))
        if aid == ATTIVA:
            invia({"t": "ricarica"})
            salva_presto()
        return {"ok": True}
    if t == "imp_utente":
        uid = str(d.get("id"))
        if uid not in USERS:
            return {"ok": False, "errore": "utente inesistente"}
        if d.get("elimina"):
            if uid == cid:
                return {"ok": False, "errore": "non puoi eliminare te stesso"}
            for k in [k for k, v in ACCOUNTS.items() if v == uid]:
                del ACCOUNTS[k]
            del USERS[uid]
            c = CLIENTS.get(uid)
            if c:
                c["q"].put({"t": "esci"})
        else:
            if "master" in d:
                USERS[uid]["master_ok"] = bool(d["master"])
                if not d["master"] and USERS[uid].get("role") == "master":
                    USERS[uid]["role"] = "giocatore"
                    c = CLIENTS.get(uid)
                    if c:
                        c["q"].put({"t": "ricarica"})
            if "admin" in d and uid != cid:
                USERS[uid]["admin"] = bool(d["admin"])
                if d["admin"]:
                    USERS[uid]["master_ok"] = True
        salva_presto()
        return {"ok": True}
    return {"ok": False, "errore": "impostazione sconosciuta"}


# ============================================================================ caricamenti
def installa_pacchetto(dati_zip):
    """Estrae un pacchetto avventura (.zip) in AVV_DIR/<id>. Ritorna l'id."""
    try:
        z = zipfile.ZipFile(io.BytesIO(dati_zip))
    except zipfile.BadZipFile:
        raise ValueError("il file non è uno zip valido")
    nomi = [n for n in z.namelist() if not n.endswith("/")]
    man = [n for n in nomi if n.split("/")[-1] == "avventura.json"]
    if not man:
        raise ValueError("manca avventura.json nel pacchetto")
    radice = min(man, key=len)[: -len("avventura.json")]
    manifest = json.loads(z.read(radice + "avventura.json"))
    aid = str(manifest.get("id") or radice.strip("/").split("/")[-1] or "avventura").lower()
    aid = re.sub(r"[^a-z0-9_\-]", "-", aid)[:60].strip("-") or "avventura"
    if not ID_RE.match(aid):
        raise ValueError("id dell'avventura non valido")
    totale = sum(z.getinfo(n).file_size for n in nomi)
    if totale > 300 * 1024 * 1024:
        raise ValueError("pacchetto troppo grande una volta estratto")
    tmp = os.path.join(AVV_DIR, f".tmp-{aid}-{uuid.uuid4().hex[:6]}")
    os.makedirs(tmp)
    try:
        for n in nomi:
            if not n.startswith(radice):
                continue
            rel = n[len(radice):]
            dest = os.path.realpath(os.path.join(tmp, rel))
            if not dest.startswith(os.path.realpath(tmp) + os.sep):
                raise ValueError("percorso non valido nel pacchetto")
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with z.open(n) as src, open(dest, "wb") as out:
                shutil.copyfileobj(src, out)
        finale = os.path.join(AVV_DIR, aid)
        vecchio = None
        if os.path.exists(finale):
            vecchio = finale + f".old-{uuid.uuid4().hex[:6]}"
            os.replace(finale, vecchio)
        os.replace(tmp, finale)
        if vecchio:
            shutil.rmtree(vecchio, ignore_errors=True)
    finally:
        if os.path.exists(tmp):
            shutil.rmtree(tmp, ignore_errors=True)
    scansiona()
    return aid


def salva_mappa_caricata(nome_file, dati, titolo, cella):
    if not ATTIVA:
        raise ValueError("nessuna avventura attiva")
    ext = os.path.splitext(nome_file)[1].lower()
    if ext not in IMG_EXT:
        raise ValueError("formato immagine non supportato (svg, png, jpg, webp)")
    stem = re.sub(r"[^a-z0-9_\-]", "_", os.path.splitext(nome_file)[0].lower())[:40] or "mappa"
    cart = os.path.join(AVV_DIR, ATTIVA, "mappe")
    os.makedirs(cart, exist_ok=True)
    if os.path.exists(os.path.join(cart, stem + ext)):
        stem += "_" + uuid.uuid4().hex[:4]
    with open(os.path.join(cart, stem + ext), "wb") as f:
        f.write(dati)
    meta = {"titolo": titolo or stem, "gruppo": "Caricate", "ordine": 500}
    if cella > 0:
        meta["griglia"] = {"cella": cella, "ox": 0, "oy": 0, "mostra": True}
    _scrivi(os.path.join(cart, stem + ".json"), meta)
    scansiona()
    invia({"t": "catalogo"})
    return stem


# ============================================================================ OAuth
def richiesta_json(url, dati=None, token=None):
    h = {"Accept": "application/json", "User-Agent": "TavoloVirtuale/2.0"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    body = None
    if dati is not None:
        body = urlencode(dati).encode()
        h["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=body, headers=h, method="POST" if body else "GET")
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def redirect_uri(prov, base):
    return f"{base.rstrip('/')}/auth/{prov}/callback"


def oauth_inizio(prov, base):
    cfg, conf = PROVIDER[prov], OAUTH[prov]
    state = secrets.token_urlsafe(24)
    verifier = secrets.token_urlsafe(48)
    ru = redirect_uri(prov, base)
    with LOCK:
        ora = time.time()
        for k in [k for k, v in STATI_OAUTH.items() if v[1] < ora]:
            del STATI_OAUTH[k]
        STATI_OAUTH[state] = (prov, ora + 600, verifier, ru)
    q = {"response_type": "code", "client_id": conf["id"], "redirect_uri": ru, "scope": cfg["scope"], "state": state}
    if prov in ("google", "discord"):
        q["code_challenge"] = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        q["code_challenge_method"] = "S256"
    if prov == "google":
        q["prompt"] = "select_account"
    return cfg["auth"] + "?" + urlencode(q, quote_via=quote)


def oauth_fine(prov, code, state):
    """Scambia il codice con il provider e restituisce (client_id, secret, nome)."""
    with LOCK:
        st = STATI_OAUTH.pop(state, None)
    if not st or st[0] != prov or st[1] < time.time():
        raise ValueError("Accesso scaduto o non valido: riprova.")
    cfg, conf = PROVIDER[prov], OAUTH[prov]
    dati = {"grant_type": "authorization_code", "code": code, "redirect_uri": st[3],
            "client_id": conf["id"], "client_secret": conf["secret"]}
    if prov in ("google", "discord"):
        dati["code_verifier"] = st[2]
    try:
        tok = richiesta_json(cfg["token"], dati)
    except urllib.error.HTTPError as e:
        raise ValueError(f"{cfg['nome']} ha rifiutato il codice (HTTP {e.code}): controlla Client ID, Secret e Redirect URI.")
    except OSError as e:
        raise ValueError(f"Impossibile contattare {cfg['nome']}: {e}")
    if "access_token" not in tok:
        raise ValueError("Il provider ha rifiutato l'accesso.")
    u = richiesta_json(cfg["utente"], token=tok["access_token"])
    if prov == "discord":
        uid, nome = u["id"], u.get("global_name") or u.get("username")
        avatar = f"https://cdn.discordapp.com/avatars/{u['id']}/{u['avatar']}.png?size=64" if u.get("avatar") else ""
    elif prov == "google":
        uid, nome, avatar = u.get("email") or u["sub"], u.get("given_name") or u.get("name"), u.get("picture", "")
    else:
        uid, nome, avatar = str(u["id"]), u.get("name") or u.get("login"), u.get("avatar_url", "")
    chiave = f"{prov}:{uid}"
    with LOCK:
        cid = ACCOUNTS.get(chiave)
        if not cid or cid not in USERS:
            cid = uuid.uuid4().hex[:12]
            USERS[cid] = {"secret": secrets.token_urlsafe(18), "name": (nome or "Avventuriero")[:30], "color": "#c0392b",
                          "role": "giocatore", "char": None}
            ACCOUNTS[chiave] = cid
        USERS[cid].update({"account": chiave, "avatar": avatar, "provider": PROVIDER[prov]["nome"], "seen": time.time()})
    salva_presto()
    return cid, USERS[cid]["secret"], USERS[cid]["name"]


# ============================================================================ contenuti dal browser
def slug(t, maxlen=40):
    t = re.sub(r"[^a-z0-9]+", "-", t.lower().translate(str.maketrans("àèéìòùç", "aeeiouc"))).strip("-")
    return t[:maxlen].strip("-") or "avventura"


def nuova_avventura(titolo):
    aid = slug(titolo)
    while os.path.exists(os.path.join(AVV_DIR, aid)):
        aid = f"{slug(titolo, 34)}-{uuid.uuid4().hex[:4]}"
    os.makedirs(os.path.join(AVV_DIR, aid, "mappe"))
    os.makedirs(os.path.join(AVV_DIR, aid, "documenti"))
    _scrivi(os.path.join(AVV_DIR, aid, "avventura.json"), {"id": aid, "titolo": titolo[:80], "formato": 1, "documenti": []})
    for f in ("personaggi.json", "mostri.json"):
        _scrivi(os.path.join(AVV_DIR, aid, f), [])
    scansiona()
    return aid


def salva_documento(nome_file, dati, titolo, solo_master):
    if not ATTIVA:
        raise ValueError("nessuna avventura attiva")
    stem, ext = os.path.splitext(os.path.basename(nome_file))
    if ext.lower() not in DOC_EXT:
        raise ValueError("formato non supportato (html, pdf, md, txt o immagini)")
    nome = re.sub(r"[^\w\-.]", "_", stem)[:60] + ext.lower()
    base = os.path.join(AVV_DIR, ATTIVA)
    os.makedirs(os.path.join(base, "documenti"), exist_ok=True)
    with open(os.path.join(base, "documenti", nome), "wb") as f:
        f.write(dati)
    man_p = os.path.join(base, "avventura.json")
    man = leggi_json(man_p, {})
    docs = [d for d in man.get("documenti", []) if d.get("file") != nome]
    docs.append({"file": nome, "titolo": titolo or stem, "solo_master": bool(solo_master)})
    man["documenti"] = docs
    _scrivi(man_p, man)
    scansiona()
    invia({"t": "catalogo"})


def zip_avventura(aid):
    base = os.path.join(AVV_DIR, aid)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _d, files in os.walk(base):
            for f in files:
                full = os.path.join(root, f)
                z.write(full, os.path.join(aid, os.path.relpath(full, base)))
    return buf.getvalue()


# ============================================================================ HTTP
class Gestore(BaseHTTPRequestHandler):
    server_version = "TavoloVirtuale/2.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    def _json(self, obj, code=200):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _auth(self, qs=None):
        cid = self.headers.get("X-Client") or (qs or {}).get("c", [""])[0]
        sec = self.headers.get("X-Secret") or (qs or {}).get("s", [""])[0]
        u = USERS.get(cid)
        if u and secrets.compare_digest(u.get("secret", ""), sec):
            u["seen"] = time.time()
            return cid
        return None

    def _ip(self):
        # dietro il proxy HTTPS l'IP vero è l'ultimo aggiunto in X-Forwarded-For
        xff = self.headers.get("X-Forwarded-For", "")
        return xff.split(",")[-1].strip() or self.client_address[0]

    def end_headers(self):
        h = getattr(self, "_headers_buffer", [])
        if not any(b.lower().startswith(b"content-security-policy:") for b in h):
            self.send_header("Content-Security-Policy", getattr(self, "_csp", None) or CSP)
        self.send_header("X-Content-Type-Options", "nosniff")
        self._csp = None
        super().end_headers()

    def _file(self, full, attach=None):
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json", "image/svg+xml"):
            ctype += "; charset=utf-8"
        with open(full, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        if attach:
            self.send_header("Content-Disposition", f'attachment; filename="{attach}"')
        if getattr(self, "_sandbox", False):
            self.send_header("Content-Security-Policy", "sandbox allow-popups allow-popups-to-escape-sandbox allow-modals")
            self._sandbox = False
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        url = urlparse(self.path)
        qs = parse_qs(url.query)
        path = unquote(url.path)
        if path == "/api/info":
            with LOCK:
                a = CATALOGO.get(ATTIVA, {}) if SESSIONE != "chiusa" else {}
                presi = [USERS[c].get("char") for c in CLIENTS if c in USERS and USERS[c].get("char")]
            return self._json({
                "avventura": {k: a.get(k, "") for k in ("id", "titolo", "sottotitolo", "descrizione")},
                "personaggi": [{k: p.get(k) for k in ("id", "nome", "icona", "razza", "classe", "colore", "facoltativo")} for p in a.get("personaggi", [])],
                "presi": presi, "password_giocatori": bool(PASSWORD_GIOCATORI),
                "login": [{"id": k, "nome": PROVIDER[k]["nome"]} for k in OAUTH], "ospiti": OSPITI,
                "versione": VERSIONE, "nome_tavolo": CONFIG.get("nome_tavolo", "Tavolo Virtuale"), "sessione": SESSIONE,
            })
        m = re.match(r"^/auth/(\w+)/(start|callback)$", path)
        if m and m.group(1) in OAUTH:
            return self._oauth(m.group(1), m.group(2), qs)
        if path == "/api/scarica_avventura":
            cid = self._auth(qs)
            aid = qs.get("id", [""])[0]
            if not cid or not is_master(cid) or aid not in CATALOGO:
                return self._json({"ok": False}, 403)
            data = zip_avventura(aid)
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", f'attachment; filename="{aid}.zip"')
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if path == "/api/io":
            cid = self._auth(qs)
            if not cid:
                return self._json({"ok": False}, 401)
            u = USERS[cid]
            return self._json({"ok": True, "nome": u.get("name"), "admin": bool(u.get("admin")), "master": bool(u.get("master_ok") or u.get("admin")),
                               "provider": u.get("provider", ""), "avatar": u.get("avatar", ""), "char": u.get("char"),
                               "colore": u.get("color"), "ruolo": u.get("role")})
        if path == "/api/stato":
            cid = self._auth(qs)
            if not cid:
                return self._json({"ok": False, "errore": "non autenticato"}, 401)
            return self._json(stato_per(cid))
        if path == "/api/eventi":
            return self._sse(qs)
        if path == "/api/esporta":
            cid = self._auth(qs)
            if not cid or not is_master(cid):
                return self._json({"ok": False}, 403)
            _salva()
            aid = qs.get("id", [ATTIVA])[0]
            data = json.dumps(db_partita(aid) or {}, ensure_ascii=False, indent=1).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Disposition", f'attachment; filename="partita_{aid}.json"')
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if path == "/api/backup":
            cid = self._auth(qs)
            if not cid or not USERS[cid].get("admin"):
                return self._json({"ok": False}, 403)
            _salva()
            data = backup_db()
            self.send_response(200)
            self.send_header("Content-Type", "application/vnd.sqlite3")
            self.send_header("Content-Disposition", f'attachment; filename="tavolo-{time.strftime("%Y%m%d-%H%M")}.db"')
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if path.startswith("/avventure/"):
            return self._avventura_file(path, qs)
        return self._statico(path)

    def _avventura_file(self, path, qs):
        parti = path.split("/")  # ['', 'avventure', id, 'mappe'|'documenti', file...]
        if len(parti) < 5 or parti[3] not in ("mappe", "documenti", "immagini") or not ID_RE.match(parti[2]):
            return self.send_error(404)
        base = os.path.realpath(os.path.join(AVV_DIR, parti[2]))
        full = os.path.realpath(os.path.join(base, *parti[3:]))
        if not full.startswith(base + os.sep) or not os.path.isfile(full):
            return self.send_error(404)
        if parti[3] == "documenti":
            self._sandbox = not full.lower().endswith(".pdf")
            doc = next((d for d in CATALOGO.get(parti[2], {}).get("documenti", []) if d["file"] == "/".join(parti[4:])), None)
            if doc and doc["solo_master"]:
                cid = self._auth(qs)
                if not cid or not is_master(cid):
                    return self.send_error(403, "Solo per il Master")
        return self._file(full)

    def _base_url(self):
        if PUBLIC_URL:
            return PUBLIC_URL
        proto = self.headers.get("X-Forwarded-Proto", "http").split(",")[0].strip()
        host = self.headers.get("X-Forwarded-Host") or self.headers.get("Host") or "localhost"
        return f"{proto}://{host.split(',')[0].strip()}"

    def _oauth(self, prov, fase, qs):
        if fase == "start":
            self.send_response(302)
            self.send_header("Location", oauth_inizio(prov, self._base_url()))
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        try:
            if "error" in qs:
                raise ValueError("Accesso annullato.")
            cid, sec, nome = oauth_fine(prov, qs.get("code", [""])[0], qs.get("state", [""])[0])
            dati = json.dumps({"id": cid, "secret": sec, "nome": nome, "account": PROVIDER[prov]["nome"]})
            nonce = secrets.token_urlsafe(16)
            self._csp = f"default-src 'none'; script-src 'nonce-{nonce}'; base-uri 'none'; frame-ancestors 'none'"
            corpo = f"""<!doctype html><meta charset="utf-8"><title>Accesso</title><script nonce="{nonce}">
try{{const v=JSON.parse(localStorage.getItem("tv_cred")||"{{}}");localStorage.setItem("tv_cred",JSON.stringify(Object.assign(v,{dati},{{oauth:true}})))}}catch(e){{}}
location.replace("/?accesso=1");</script>"""
        except Exception as e:  # errori di rete o del provider: si mostra un messaggio leggibile
            corpo = f'<!doctype html><meta charset="utf-8"><p style="font:16px sans-serif">⚠️ {str(e)[:200]}</p><p><a href="/">Torna al tavolo</a></p>'
        data = corpo.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _statico(self, path):
        if path in ("", "/", "/admin", "/admin/"):
            path = "/index.html"
        base = os.path.realpath(WEB)
        full = os.path.realpath(os.path.join(base, path.lstrip("/")))
        if not full.startswith(base + os.sep) or not os.path.isfile(full):
            return self.send_error(404, "Non trovato")
        if full.endswith("index.html"):
            data = open(full, encoding="utf-8").read().replace("__VERSIONE__", VERSIONE).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(data)
            return
        return self._file(full)

    def _sse(self, qs):
        cid = self._auth(qs)
        if not cid:
            return self._json({"ok": False}, 401)
        q = queue.Queue()
        with LOCK:
            vecchio = CLIENTS.get(cid)
            CLIENTS[cid] = {"q": q, "role": USERS[cid]["role"]}
        if vecchio:
            vecchio["q"].put(None)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        invia({"t": "online", "online": online()})
        try:
            self.wfile.write(b"retry: 2000\n\n")
            self.wfile.flush()
            while True:
                try:
                    ev = q.get(timeout=15)
                except queue.Empty:
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
                    continue
                if ev is None:
                    break
                self.wfile.write(b"data: " + json.dumps(ev, ensure_ascii=False).encode("utf-8") + b"\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            with LOCK:
                if CLIENTS.get(cid, {}).get("q") is q:
                    del CLIENTS[cid]
            invia({"t": "online", "online": online()})

    def do_POST(self):
        url = urlparse(self.path)
        qs = parse_qs(url.query)
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_BODY:
            return self._json({"ok": False, "errore": "file troppo grande (max 80 MB)"}, 413)
        raw = self.rfile.read(n)

        # caricamenti binari (solo Master)
        if url.path in ("/api/carica_avventura", "/api/carica_mappa", "/api/carica_documento"):
            cid = self._auth(qs)
            if not cid or not is_master(cid):
                return self._json({"ok": False, "errore": "solo il Master può caricare"}, 403)
            try:
                if url.path == "/api/carica_avventura":
                    aid = installa_pacchetto(raw)
                    invia({"t": "catalogo"})
                    if aid == ATTIVA:
                        attiva_avventura(aid)
                        invia({"t": "ricarica"})
                    return self._json({"ok": True, "id": aid, "titolo": CATALOGO.get(aid, {}).get("titolo", aid)})
                if url.path == "/api/carica_documento":
                    salva_documento(qs.get("nome", ["documento.html"])[0], raw, qs.get("titolo", [""])[0], qs.get("solo_master", ["0"])[0] == "1")
                    return self._json({"ok": True})
                nome = qs.get("nome", ["mappa.png"])[0]
                stem = salva_mappa_caricata(nome, raw, qs.get("titolo", [""])[0], float(qs.get("cella", ["0"])[0] or 0))
                return self._json({"ok": True, "id": stem})
            except (ValueError, KeyError, json.JSONDecodeError) as e:
                return self._json({"ok": False, "errore": str(e)}, 400)

        try:
            body = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            return self._json({"ok": False, "errore": "JSON non valido"}, 400)

        if url.path in ("/api/login", "/api/entra"):
            if troppe_richieste(self._ip(), "accesso"):
                return self._json({"ok": False, "errore": "Troppi tentativi: aspetta qualche secondo"}, 429)
            return self._login(body) if url.path == "/api/login" else self._entra(body)

        cid = self._auth()
        if not cid:
            return self._json({"ok": False, "errore": "non autenticato"}, 401)
        if url.path == "/api/op":
            if troppe_richieste(cid, "veloce" if body.get("op") in OP_VELOCI else "normale"):
                return self._json({"ok": False, "errore": "Piano! Troppe azioni in poco tempo"}, 429)
            try:
                return self._json(op(cid, body))
            except (ValueError, KeyError, TypeError) as e:
                return self._json({"ok": False, "errore": str(e) or "dati non validi"}, 400)
        if url.path == "/api/importa" and is_master(cid):
            with LOCK:
                STATE.clear()
                STATE.update(stato_vuoto(ATTIVA))
                STATE.update({k: v for k, v in body.items() if k in STATE})
            invia({"t": "ricarica"})
            salva_presto()
            return self._json({"ok": True})
        return self._json({"ok": False}, 404)

    def _login(self, body):
        """Primo passo: chi sei? (ospite o amministratore; gli account OAuth passano da /auth/...)"""
        tipo = body.get("tipo")
        cid, sec = body.get("id"), body.get("secret")
        conosciuto = cid in USERS and secrets.compare_digest(USERS[cid].get("secret", ""), str(sec or ""))
        if tipo == "admin":
            if not verifica_admin(body.get("utente", ""), body.get("password", "")):
                return self._json({"ok": False, "errore": "Utente o password dell'amministratore sbagliati"}, 403)
            if not conosciuto:
                cid = uuid.uuid4().hex[:12]
                USERS[cid] = {"secret": secrets.token_urlsafe(18), "name": CONFIG["admin"].get("utente", "admin").capitalize(),
                              "color": "#e0b04a", "role": "master", "char": None}
            USERS[cid].update({"admin": True, "master_ok": True, "seen": time.time()})
        elif tipo == "ospite":
            if not OSPITI:
                return self._json({"ok": False, "errore": "Gli ospiti non sono ammessi: accedi con un account"}, 403)
            if PASSWORD_GIOCATORI and not secrets.compare_digest(str(body.get("password", "")), PASSWORD_GIOCATORI):
                return self._json({"ok": False, "errore": "Password del tavolo sbagliata (chiedila al Master)"}, 403)
            nome = str(body.get("nome", "")).strip()[:30]
            if not nome:
                return self._json({"ok": False, "errore": "Scrivi il tuo nome"}, 400)
            if nome_riservato(nome):
                return self._json({"ok": False, "errore": "Questo nome è riservato: scegline un altro"}, 400)
            if not conosciuto:
                cid = uuid.uuid4().hex[:12]
                USERS[cid] = {"secret": secrets.token_urlsafe(18), "color": "#c0392b", "role": "giocatore", "char": None}
            USERS[cid].update({"name": nome, "seen": time.time()})
        else:
            return self._json({"ok": False, "errore": "tipo di accesso non valido"}, 400)
        salva_presto()
        return self._json({"ok": True, "id": cid, "secret": USERS[cid]["secret"], "nome": USERS[cid]["name"]})

    def _entra(self, body):
        """Secondo passo: ci si siede al tavolo con un ruolo (e magari un personaggio)."""
        cid, sec = body.get("id"), body.get("secret")
        if not (cid in USERS and secrets.compare_digest(USERS[cid].get("secret", ""), str(sec or ""))):
            return self._json({"ok": False, "errore": "Devi prima accedere", "login": True}, 401)
        u = USERS[cid]
        # Master: l'admin (se lo chiede) oppure chi è stato nominato Master dall'admin. Tutti gli altri sono giocatori.
        ruolo = "master" if body.get("ruolo") == "master" and (u.get("master_ok") or u.get("admin")) else "giocatore"
        if u.get("role") == "master" and u.get("master_ok") and not u.get("admin"):
            ruolo = "master"
        pg = body.get("personaggio") or None
        if pg and pg not in {p["id"] for p in CATALOGO.get(ATTIVA, {}).get("personaggi", [])}:
            pg = None
        nome = str(body.get("nome") or "").strip()[:30]
        if nome and nome_riservato(nome) and not u.get("admin"):
            return self._json({"ok": False, "errore": "Questo nome è riservato: scegline un altro"}, 400)
        with LOCK:   # controllo del PG e assegnazione in un solo passo (niente doppioni con richieste simultanee)
            if pg and ruolo == "giocatore" and pg_occupato(pg, cid):
                return self._json({"ok": False, "errore": "Personaggio già scelto da un altro giocatore"}, 409)
            if nome:
                u["name"] = nome
            u.update({"color": colore_valido(body.get("colore"), colore_valido(u.get("color"))), "role": ruolo, "char": pg if ruolo == "giocatore" else None, "seen": time.time()})
            if pg and ruolo == "giocatore":
                crea_pedina_pg(cid, pg, u["color"])
        salva_presto()
        if SESSIONE != "chiusa":
            sistema(f"👋 {u['name']} si è seduto al tavolo{' come Master' if ruolo == 'master' else ''}.")
        return self._json({"ok": True, "id": cid, "secret": u["secret"]})

def ip_locali():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return [ip] if not ip.startswith("127.") else []
    except OSError:
        return []


def main():
    global VERSIONE
    ap = argparse.ArgumentParser(description="Tavolo Virtuale per D&D")
    ap.add_argument("--porta", type=int, default=int(os.environ.get("PORT", 8000)))
    ap.add_argument("--host", default=os.environ.get("HOST", "0.0.0.0"))
    a = ap.parse_args()
    VERSIONE = calcola_versione()
    os.makedirs(DATI, exist_ok=True)
    apri_db()
    pw_iniziale = carica_config()
    os.makedirs(AVV_DIR, exist_ok=True)
    carica_tutto()
    threading.Thread(target=osservatore, daemon=True).start()
    srv = ThreadingHTTPServer((a.host, a.porta), Gestore)
    srv.daemon_threads = True
    print("=" * 60)
    print("  🐉  TAVOLO VIRTUALE  ·  pronto!")
    print("=" * 60)
    print(f"  Su questo PC:          http://localhost:{a.porta}")
    for ip in ip_locali():
        print(f"  In rete locale:        http://{ip}:{a.porta}")
    print(f"  Database:              {DB_FILE}")
    print(f"  Account admin:         {CONFIG['admin']['utente']}" + (f"  ·  password iniziale: {pw_iniziale}" if pw_iniziale else "  (password cifrata nel database)"))
    print(f"  Accesso con account:   {', '.join(PROVIDER[p]['nome'] for p in OAUTH) or '(nessuno: si configura in ⚙️ Impostazioni)'}")
    print(f"  Ospiti:                {'ammessi' if OSPITI else 'non ammessi'}{' · password del tavolo attiva' if PASSWORD_GIOCATORI else ''}")
    print(f"  Avventure ({len(CATALOGO)}):        {', '.join(CATALOGO) or 'nessuna: caricane una dal pannello Master'}")
    print(f"  In gioco:              {ATTIVA}")
    print("=" * 60)
    def ferma(*_):
        print("Salvo e chiudo…", flush=True)
        _salva()
        os._exit(0)
    signal.signal(signal.SIGTERM, ferma)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        ferma()


if __name__ == "__main__":
    main()
