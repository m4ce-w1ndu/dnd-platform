"""Harness dei test end-to-end del Tavolo Virtuale.

Avvia il server sotto test (Python o Rust) con dati e avventure in una cartella temporanea,
e offre un piccolo client HTTP + SSE che parla come il browser (tavolo/web/app.js).

Server sotto test, scelto con la variabile TAVOLO_SERVER:
    TAVOLO_SERVER=python                    → python3 tavolo/server.py  (predefinito)
    TAVOLO_SERVER=/percorso/al/binario      → il server Rust (stesse opzioni --porta/--host)
"""
import http.client
import itertools
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from urllib.parse import urlencode

QUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(QUI, "..", ".."))
FIXTURE = os.path.join(QUI, "fixture", "avventure")
PW_ADMIN = "password-admin-di-prova"
_ip = itertools.count(1)


def porta_libera():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def solo_rust(f):
    """Test di robustezza che il server Python non supera (bug noti, corretti nella riscrittura)."""
    return unittest.skipIf(os.environ.get("TAVOLO_SERVER", "python") == "python", "bug noto del server Python")(f)


class Server:
    """Un server avviato in una cartella temporanea; restart() mantiene i dati."""

    def __init__(self, env=None):
        self.tmp = tempfile.mkdtemp(prefix="tavolo-e2e-")
        self.dati = os.path.join(self.tmp, "dati")
        self.avv = os.path.join(self.tmp, "avventure")
        shutil.copytree(FIXTURE, self.avv)
        os.makedirs(self.dati)
        self.extra_env = env or {}
        self.proc = None
        self.log = open(os.path.join(self.tmp, "server.log"), "ab")
        self.start()

    @property
    def tipo(self):
        return os.environ.get("TAVOLO_SERVER", "python")

    def start(self):
        self.porta = porta_libera()
        env = dict(os.environ, DATI_DIR=self.dati, AVVENTURE_DIR=self.avv, MASTER_PASSWORD=PW_ADMIN,
                   WEB_DIR=os.path.join(REPO, "tavolo", "web"), RUST_LOG=os.environ.get("RUST_LOG", "warn"))
        env.update(self.extra_env)
        if self.tipo == "python":
            cmd = [sys.executable, os.path.join(REPO, "tavolo", "server.py")]
        else:
            cmd = [self.tipo]
        cmd += ["--porta", str(self.porta), "--host", "127.0.0.1"]
        self.proc = subprocess.Popen(cmd, env=env, stdout=self.log, stderr=self.log, cwd=self.tmp)
        fine = time.time() + 20
        while time.time() < fine:
            try:
                c = http.client.HTTPConnection("127.0.0.1", self.porta, timeout=2)
                c.request("GET", "/api/info")
                if c.getresponse().status == 200:
                    return
            except OSError:
                pass
            if self.proc.poll() is not None:
                raise RuntimeError("il server non è partito, vedi " + self.log.name)
            time.sleep(0.1)
        raise RuntimeError("il server non risponde")

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()          # SIGTERM: il server deve salvare prima di uscire
            try:
                self.proc.wait(10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None

    def restart(self):
        self.stop()
        self.start()

    def chiudi(self):
        self.stop()
        self.log.close()
        shutil.rmtree(self.tmp, ignore_errors=True)


class Risposta:
    def __init__(self, status, headers, body):
        self.status, self.headers, self.body = status, headers, body

    @property
    def json(self):
        return json.loads(self.body or b"null")

    def h(self, nome):
        return self.headers.get(nome.lower(), "")

    def __repr__(self):
        return f"<{self.status} {self.body[:200]!r}>"


class Client:
    """Un browser: ha un IP (via X-Forwarded-For), delle credenziali e, se serve, uno stream SSE."""

    def __init__(self, srv):
        self.srv = srv
        self.ip = f"10.{next(_ip) // 250 % 250}.{next(_ip) % 250}.{next(_ip) % 250}"
        self.id = self.secret = None
        self.eventi = []
        self._sse = None
        self._cv = threading.Condition()

    # ---------------------------------------------------------------- HTTP
    def req(self, metodo, path, body=None, raw=None, auth=True, headers=None):
        h = {"X-Forwarded-For": self.ip}
        if auth and self.id:
            h.update({"X-Client": self.id, "X-Secret": self.secret})
        if body is not None:
            raw = json.dumps(body).encode()
            h["Content-Type"] = "application/json"
        h.update(headers or {})
        c = http.client.HTTPConnection("127.0.0.1", self.srv.porta, timeout=20)
        c.request(metodo, path, body=raw, headers=h)
        r = c.getresponse()
        out = Risposta(r.status, {k.lower(): v for k, v in r.getheaders()}, r.read())
        c.close()
        return out

    def get(self, path, **kw):
        return self.req("GET", path, **kw)

    def post(self, path, body=None, **kw):
        return self.req("POST", path, body=body, **kw)

    def qs(self):
        return urlencode({"c": self.id, "s": self.secret})

    # ---------------------------------------------------------------- accesso
    def login_ospite(self, nome, **extra):
        r = self.post("/api/login", {"tipo": "ospite", "nome": nome, "id": self.id, "secret": self.secret, **extra})
        if r.status == 200 and r.json.get("ok"):
            self.id, self.secret = r.json["id"], r.json["secret"]
        return r

    def login_admin(self, password=PW_ADMIN, utente="admin"):
        r = self.post("/api/login", {"tipo": "admin", "utente": utente, "password": password, "id": self.id, "secret": self.secret})
        if r.status == 200 and r.json.get("ok"):
            self.id, self.secret = r.json["id"], r.json["secret"]
        return r

    def entra(self, ruolo="giocatore", personaggio=None, **extra):
        return self.post("/api/entra", {"id": self.id, "secret": self.secret, "ruolo": ruolo, "personaggio": personaggio, **extra})

    def op(self, _op, riprova=True, **dati):
        """POST /api/op; ritenta se il limite di frequenza risponde 429 (non è quello che si sta provando)."""
        for _ in range(60):
            r = self.post("/api/op", {"op": _op, **dati})
            if r.status != 429 or not riprova:
                return r
            time.sleep(0.25)
        return r

    def ok(self, _op, **dati):
        r = self.op(_op, **dati)
        assert r.status == 200 and r.json.get("ok"), f"{_op} {dati} → {r}"
        return r.json

    def stato(self):
        r = self.get("/api/stato?" + self.qs())
        assert r.status == 200, r
        return r.json

    # ---------------------------------------------------------------- SSE
    def collega(self):
        """Apre /api/eventi e raccoglie gli eventi in self.eventi (come EventSource)."""
        c = http.client.HTTPConnection("127.0.0.1", self.srv.porta, timeout=60)
        c.request("GET", "/api/eventi?" + self.qs(), headers={"X-Forwarded-For": self.ip})
        sock = c.sock
        r = c.getresponse()
        if r.status != 200:
            raise AssertionError(f"SSE {r.status}")
        self._sse = (sock, r)
        pronto = threading.Event()

        def leggi():
            try:
                while True:
                    riga = r.fp.readline()
                    if not riga:
                        break
                    if riga.startswith(b"retry:"):
                        pronto.set()
                    if riga.startswith(b"data: "):
                        with self._cv:
                            self.eventi.append(json.loads(riga[6:]))
                            self._cv.notify_all()
            except (OSError, ValueError):
                pass
            finally:
                pronto.set()
                with self._cv:
                    self.eventi.append({"t": "__chiuso__"})
                    self._cv.notify_all()

        threading.Thread(target=leggi, daemon=True).start()
        pronto.wait(5)
        return self

    def scollega(self):
        if self._sse:
            try:
                self._sse[0].shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self._sse[0].close()
            self._sse = None

    def aspetta(self, pred, timeout=5.0):
        """Primo evento (già arrivato o in arrivo) che soddisfa pred; None allo scadere."""
        fine = time.time() + timeout
        with self._cv:
            i = 0
            while True:
                while i < len(self.eventi):
                    if pred(self.eventi[i]):
                        return self.eventi[i]
                    i += 1
                resta = fine - time.time()
                if resta <= 0:
                    return None
                self._cv.wait(resta)

    def svuota(self):
        with self._cv:
            self.eventi.clear()


class Base(unittest.TestCase):
    """Un server per classe di test; self.admin è l'admin seduto come Master con «prova» aperta."""
    env = None

    @classmethod
    def setUpClass(cls):
        cls.srv = Server(cls.env)
        cls.clienti = []
        cls.admin = cls.nuovo()
        assert cls.admin.login_admin().json["ok"]
        assert cls.admin.entra("master").json["ok"]
        cls.admin.ok("sessione_apri", id="prova")

    @classmethod
    def tearDownClass(cls):
        for c in cls.clienti:
            c.scollega()
        cls.srv.chiudi()

    @classmethod
    def nuovo(cls):
        c = Client(cls.srv)
        cls.clienti.append(c)
        return c

    _n = itertools.count(1)

    @classmethod
    def giocatore(cls, pg=None, nome=None, collega=True):
        """Un ospite seduto come giocatore (con il personaggio pg), già collegato allo stream."""
        c = cls.nuovo()
        r = c.login_ospite(nome or f"Giocatore{next(cls._n)}")
        assert r.json.get("ok"), r
        r = c.entra("giocatore", pg)
        assert r.json.get("ok"), r
        if collega:
            c.collega()
        return c

    def pedina_pg(self, pg):
        return next(p for p in self.admin.stato()["pedine"].values() if p.get("pg") == pg)
