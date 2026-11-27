"""Test nel browser (Playwright + Chromium) del client nuovo in Angular (pagina principale; il vecchio è su /vecchio/).

Percorrono a mano, come farebbe una persona, i flussi di tutti i ruoli: account di sistema, amministratore
del tavolo, Master e giocatori, anche su telefono. Servono per decidere se il client vecchio si può togliere.

Requisiti (una volta sola):
    python3 -m venv e2e/.venv && e2e/.venv/bin/pip install playwright && e2e/.venv/bin/playwright install chromium
    (cd ../tavolo-web && npm ci && npx ng build)
Uso:  ./run.sh ../target/release/tavolo test_gui      (solo server Rust: il Python serve solo il client vecchio)
Screenshot dei fallimenti in $GUI_SCREENSHOT (predefinito: cartella temporanea, stampata).
"""
import itertools
import json
import re
import os
import sqlite3
import tempfile
import time
import unittest
from urllib.parse import urljoin

from harness import PW_ADMIN, REPO, Client, Server, rust
from test_dati import zip_di
from test_permessi import PNG

try:
    from playwright.sync_api import expect, sync_playwright
except ImportError:  # pragma: no cover
    sync_playwright = None

DIST = os.environ.get("WEB_BETA_DIR") or os.path.join(REPO, "tavolo-web", "dist", "tavolo-web", "browser")
SHOT = os.environ.get("GUI_SCREENSHOT") or tempfile.mkdtemp(prefix="tavolo-gui-")
MOTIVO = (
    "manca Playwright" if sync_playwright is None
    else "solo server Rust" if not rust()
    else "manca la build del client (npx ng build)" if not os.path.exists(os.path.join(DIST, "index.html"))
    else None
)
T = 8000  # ms: attese nel browser
_ip = itertools.count(1)


@unittest.skipIf(MOTIVO, MOTIVO or "")
class GuiBase(unittest.TestCase):
    """Un server e un Chromium per classe; ogni test apre le sue pagine (contesti separati = browser separati)."""

    @classmethod
    def setUpClass(cls):
        cls.srv = Server({"WEB_BETA_DIR": DIST})
        cls.url = f"http://127.0.0.1:{cls.srv.porta}/"
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch()
        cls.sistema = Client(cls.srv)
        assert cls.sistema.login_admin().json["ok"]

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.srv.chiudi()

    def setUp(self):
        self.pagine = []
        self.errori = []

    def tearDown(self):
        esito = self._outcome.result
        fallito = any(t is self for t, _ in esito.failures + esito.errors) if hasattr(esito, "failures") else False
        for i, p in enumerate(self.pagine):
            if fallito:
                f = os.path.join(SHOT, f"{self.id().split('.')[-1]}_{i}.png")
                try:
                    p.screenshot(path=f, full_page=True)
                    print(f"\n  screenshot: {f}")
                except Exception:  # noqa: BLE001
                    pass
            p.context.close()
        # nessun errore JavaScript durante il test (gli errori di rete attesi, come i 403, non contano)
        self.assertEqual([e for e in self.errori if "Failed to load resource" not in e], [], "errori nella console")

    # ------------------------------------------------------------------ aiuti
    def pagina(self, telefono=False):
        ctx = self.browser.new_context(
            viewport={"width": 390, "height": 844} if telefono else {"width": 1280, "height": 800},
            has_touch=telefono, is_mobile=telefono,
            # ogni browser ha il suo indirizzo, come nella realtà (il limite di accessi è per IP)
            extra_http_headers={"X-Forwarded-For": f"10.99.{next(_ip) // 250}.{next(_ip) % 250}"},
        )
        p = ctx.new_page()
        p.set_default_timeout(T)
        p.on("pageerror", lambda e: self.errori.append(f"pageerror: {e}"))
        p.on("console", lambda m: m.type == "error" and self.errori.append(f"console: {m.text}"))
        self.pagine.append(p)
        return p

    def ospite(self, nome, telefono=False):
        p = self.pagina(telefono)
        p.goto(self.url)
        p.get_by_label("Il tuo nome").fill(nome)
        p.get_by_role("button", name="Entra come ospite").click()
        expect(p.locator("#sala")).to_be_visible()
        return p

    def cred(self, p):
        return json.loads(p.evaluate("localStorage.getItem('tv_cred')"))

    def admin_tavolo(self, nome):
        """Un ospite promosso dall'account di sistema ad amministratore del tavolo."""
        p = self.ospite(nome)
        self.sistema.ok("imp_utente", id=self.cred(p)["id"], admin=True)
        # il server manda «ricarica»: la sala diventa quella dell'amministratore
        expect(p.locator(".sala-passi")).to_be_visible()
        return p

    def entra_sistema(self, telefono=False):
        p = self.pagina(telefono)
        p.goto(self.url)
        p.get_by_text("Amministrazione del sistema").click()
        p.locator("input[autocomplete=current-password]").fill(PW_ADMIN)
        p.get_by_role("button", name="Accedi").click()
        expect(p.locator(".sis-nav")).to_be_visible()
        return p

    def chiudi_tavolo(self):
        """Riporta il server a tavolo chiuso (tra un test e l'altro), come farebbe un amministratore."""
        c = Client(self.srv)
        c.login_ospite(f"Pulizia{time.monotonic_ns() % 100000}")
        self.sistema.ok("imp_utente", id=c.id, admin=True)
        c.entra("master")
        c.op("reset_partita")
        c.op("sessione_chiudi")
        self.sistema.ok("imp_utente", id=c.id, elimina=True)


class TestSistema(GuiBase):
    def test_entra_e_vede_solo_amministrazione(self):
        p = self.entra_sistema()
        expect(p.locator("#sala")).to_have_count(0)            # niente sala d'attesa
        expect(p.locator("#mappa")).to_have_count(0)           # niente mappa
        expect(p.locator(".titolo-scena")).to_contain_text("Amministrazione")
        for nome in ["Generale", "Accesso con account", "Utenti e permessi", "Partite e backup", "Registro", "Account di sistema"]:
            p.locator(".sis-nav button", has_text=nome).click()
            expect(p.locator(".sis-pagina h2")).to_contain_text(nome.split()[0])

    def test_salva_impostazioni(self):
        p = self.entra_sistema()
        p.locator(".sis-nav button", has_text="Generale").click()
        salva = p.locator(".salva-barra button")
        expect(salva).to_be_disabled()
        p.get_by_label("Nome del tavolo").fill("Tavolo dei test")
        expect(salva).to_be_enabled()
        salva.click()
        expect(salva).to_be_disabled()
        self.assertEqual(Client(self.srv).get("/api/info").json["nome_tavolo"], "Tavolo dei test")
        p.reload()                                             # la sezione resta quella scelta
        expect(p.get_by_label("Nome del tavolo")).to_have_value("Tavolo dei test")

    def test_permessi_dalla_lista_utenti(self):
        g = Client(self.srv)
        g.login_ospite("Promosso")
        p = self.entra_sistema()
        p.locator(".sis-nav button", has_text="Utenti").click()
        p.get_by_placeholder("Cerca per nome o account").fill("promo")
        riga = p.locator(".utente", has_text="Promosso")
        expect(p.locator(".utente")).to_have_count(1)
        riga.get_by_label("Admin").check()
        expect(riga.locator(".chip", has_text="admin")).to_be_visible()
        self.assertTrue(next(u for u in self.sistema.ok("imp_leggi")["utenti"] if u["id"] == g.id)["admin"])
        p.locator(".filtri button", has_text="Admin").click()
        expect(p.locator(".utente")).to_have_count(1)          # l'account di sistema non conta come admin del tavolo

    def test_telefono(self):
        p = self.entra_sistema(telefono=True)
        expect(p.get_by_title("Mostra pannello")).to_have_count(0)
        p.locator(".sis-nav button", has_text="Utenti").click()
        expect(p.locator(".sis-pagina h2")).to_contain_text("Utenti")
        larga = p.evaluate("document.documentElement.scrollWidth > innerWidth")
        self.assertFalse(larga, "la pagina scorre di lato sul telefono")
        self.assertLessEqual(p.evaluate("document.querySelector('.sis-pagina').getBoundingClientRect().right"), 390, "contenuto tagliato a destra")


class TestPulizia(GuiBase):
    def test_pulizia_vecchi_utenti(self):
        vecchi = []
        for i in range(3):
            c = Client(self.srv)
            c.login_ospite(f"Vecchio{i}")
            vecchi.append(c.id)
        recente = Client(self.srv)
        recente.login_ospite("Recente")
        # invecchia gli ospiti e aggiunge due copie dell'account di sistema come quelle del server Python
        self.srv.stop()
        db = sqlite3.connect(os.path.join(self.srv.dati, "tavolo.db"))
        for uid in vecchi:
            db.execute("UPDATE utenti SET dati = json_set(dati, '$.seen', 1000) WHERE id = ?", (uid,))
        riga = db.execute("SELECT dati FROM utenti WHERE id = ?", (self.sistema.id,)).fetchone()[0]
        for k in ("copia1", "copia2"):
            d = json.loads(riga)
            d["seen"] = 2000
            db.execute("INSERT INTO utenti (id, dati) VALUES (?, ?)", (k, json.dumps(d)))
        db.commit()
        db.close()
        self.srv.start()
        type(self).url = f"http://127.0.0.1:{self.srv.porta}/"
        type(self).sistema = Client(self.srv)
        assert self.sistema.login_admin().json["ok"]

        p = self.entra_sistema()
        p.locator(".sis-nav button", has_text="Utenti").click()
        expect(p.locator(".sis-nav .bolla")).to_have_text("5")
        expect(p.locator(".pulizia")).to_contain_text("2 vecchie copie")
        expect(p.locator(".pulizia")).to_contain_text("3 ospiti")
        expect(p.locator(".pulizia select")).to_have_value("30")
        p.locator(".pulizia button").click()
        dlg = p.locator(".dialogo")
        expect(dlg).to_contain_text("Eliminare 5 utenti")
        dlg.get_by_role("button", name="Elimina").click()
        expect(p.locator(".pulizia.ok")).to_be_visible()
        nomi = {u["nome"] for u in self.sistema.ok("imp_leggi")["utenti"]}
        self.assertIn("Recente", nomi)
        self.assertFalse(nomi & {"Vecchio0", "Vecchio1", "Vecchio2"})
        self.assertEqual(sum(1 for u in self.sistema.ok("imp_leggi")["utenti"] if u["sistema"]), 1)


class PartitaBase(GuiBase):
    """Ogni test parte da tavolo chiuso e partita azzerata."""

    def tearDown(self):
        super().tearDown()
        self.chiudi_tavolo()

    def avvia(self, nome_admin="Capo", giocatori=("Giulia",), telefono=False):
        """Amministratore apre «prova», ogni giocatore sceglie un personaggio, l'amministratore fa il Master e inizia."""
        a = self.admin_tavolo(nome_admin)
        a.locator(".sala-avv button", has_text="Avventura di prova").click()
        expect(a.locator(".sala-passi")).to_contain_text("i giocatori stanno scegliendo")
        gs = []
        for nome, pg in zip(giocatori, ["Rocco", "Lia", "Bruno"]):
            g = self.ospite(nome, telefono=telefono)
            expect(g.get_by_role("heading", name="Scegli il tuo personaggio")).to_be_visible()
            g.locator(".carta-pg").filter(has=g.locator("b", has_text=re.compile(f"^{pg}$"))).click()
            g.locator("#sala-conferma, #sala-anteprima button.primario").first.click()
            expect(g.get_by_role("heading", name="Sei pronto!")).to_be_visible()
            gs.append(g)
        a.locator(".persona", has_text=nome_admin).get_by_role("button", name="Rendi Master").click()
        a.locator(".dialogo").get_by_role("button", name="Andiamo!").click()   # «Sei il Master!»
        expect(a.locator(".persona", has_text=nome_admin).locator(".chip")).to_have_text("👑 Master")
        a.locator("#sala-inizia").click()
        for p in [a, *gs]:
            expect(p.locator("#sala")).to_have_count(0)
            expect(p.locator("#mappa")).to_be_visible()
        return a, gs


class TestPartita(PartitaBase):
    def test_sala_e_inizio(self):
        a, (g,) = self.avvia()
        expect(g.locator(".pedina.mia")).to_have_count(1)                # il suo personaggio è sulla mappa
        expect(a.locator("#schede-nav button", has_text="Master")).to_be_visible()
        expect(g.locator("#schede-nav button", has_text="Master")).to_have_count(0)

    def test_dadi_e_chat(self):
        a, (g, h) = self.avvia(giocatori=("Giulia", "Marco"))
        g.locator(".dadi-bottoni button", has_text="d6").first.click()
        g.locator(".dadi-bottoni button", has_text="d6").first.click()
        expect(g.locator(".pool-espr")).to_contain_text("2d6")
        g.locator("#pool-tira").click()
        for p in (a, g, h):
            expect(p.locator(".log .voce", has_text="2d6").last).to_be_visible()
        # tiro privato: lo vedono lui e il Master, non l'altro giocatore
        g.locator("#tab-dadi .switch input").check()
        g.locator("#tab-dadi input[name=chat]").fill("/r 1d20+77")
        g.locator("#tab-dadi form.chat button").click()
        expect(a.locator(".log .voce.segreto", has_text="1d20+77")).to_be_visible()
        expect(g.locator(".log .voce.segreto", has_text="1d20+77")).to_be_visible()
        g.locator("#tab-dadi .switch input").uncheck()
        g.locator("#tab-dadi input[name=chat]").fill("ciao a tutti")
        g.locator("#tab-dadi form.chat button").click()
        expect(h.locator(".log .voce", has_text="ciao a tutti")).to_be_visible()
        expect(h.locator(".log", has_text="1d20+77")).to_have_count(0)

    def test_master_cambia_mappa_e_aggiunge_mostro(self):
        a, (g,) = self.avvia()
        a.locator("#schede-nav button", has_text="Master").click()
        a.locator("#m-scene button", has_text="Grotta").click()
        expect(g.locator(".titolo-scena")).to_contain_text("Grotta")
        expect(g.locator(".pedina.mia")).to_have_count(1)                # il gruppo è stato portato
        prima = g.locator(".pedina").count()
        a.locator(".bestiario button", has_text="Coboldo").click()
        expect(g.locator(".pedina")).to_have_count(prima + 1)
        # mostro nascosto: lo vede solo il Master
        a.get_by_label("aggiungi nascosti").check()
        a.locator(".bestiario button", has_text="Cane fedele").click()
        expect(a.locator(".pedina")).to_have_count(prima + 2)
        time.sleep(0.5)
        expect(g.locator(".pedina:not([hidden])")).to_have_count(prima + 1)

    def test_trascina_pedina(self):
        a, (g,) = self.avvia()
        p = g.locator(".pedina.mia")
        box = p.bounding_box()
        x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        g.mouse.move(x, y)
        g.mouse.down()
        for i in range(1, 11):
            g.mouse.move(x + 15 * i, y + 8 * i)
        g.mouse.up()
        pid = p.get_attribute("id")
        prima = a.locator("#" + pid).bounding_box()
        time.sleep(0.6)
        dopo = a.locator("#" + pid).bounding_box()
        self.assertTrue(abs(dopo["x"] - box["x"]) > 50 or abs(prima["x"] - box["x"]) > 50, "il Master non vede lo spostamento")

    def test_pausa_e_ripresa(self):
        a, (g,) = self.avvia()
        a.get_by_title("Torna alla sala d'attesa").click()
        a.locator(".dialogo").get_by_role("button", name="Metti in pausa").click()
        expect(g.locator("#sala")).to_be_visible()
        expect(a.locator("#sala-inizia")).to_be_visible()
        a.locator("#sala-inizia").click()
        expect(g.locator("#sala")).to_have_count(0)

    def test_ricarica_pagina_resta_dentro(self):
        a, (g,) = self.avvia()
        g.reload()
        expect(g.locator("#mappa")).to_be_visible()
        expect(g.locator(".pedina.mia")).to_have_count(1)

    def test_scheda_personaggio(self):
        a, (g,) = self.avvia()
        g.locator("#schede-nav button", has_text="Scheda").click()
        expect(g.locator("#tab-scheda")).to_contain_text("Rocco")
        # una prova dalla scheda finisce nella cronologia del Master
        g.locator("#tab-scheda button", has_text="Iniziativa").click()
        expect(a.locator(".log .voce", has_text="Iniziativa").last).to_be_visible()
        # i punti ferita cambiati dal giocatore si vedono sulla pedina, anche dal Master
        g.locator("#tab-scheda input[type=number]").first.fill("5")
        g.locator("#tab-scheda button", has_text="Danno").click()
        expect(g.locator("#tab-scheda")).to_contain_text("23/28")
        a.locator(".pedina", has_text="Rocco").click()
        expect(a.locator("#pannello-pedina")).to_contain_text("23")

    def test_telefono_giocatore(self):
        a, (g,) = self.avvia(telefono=True)
        larga = g.evaluate("document.documentElement.scrollWidth > innerWidth")
        self.assertFalse(larga, "la pagina scorre di lato sul telefono")
        g.get_by_title("Mostra pannello").click()
        expect(g.locator("#laterale.aperto")).to_be_visible()
        g.locator("#pool-tira").click()
        expect(a.locator(".log .voce", has_text="Giulia").last).to_be_visible()


class TestStrumenti(PartitaBase):
    """Strumenti della mappa, turni, documenti, caricamenti e salvataggi (il resto delle funzioni del client vecchio)."""

    def centro_vuoto(self, p):
        """Un punto della mappa lontano dalle pedine (angolo in alto a sinistra dell'immagine)."""
        b = p.locator("#mappa").bounding_box()
        return b["x"] + 30, b["y"] + 30

    def strumento(self, p, nome):
        p.locator("#barra button", has_text=nome).click()

    def test_righello_e_ping(self):
        a, (g,) = self.avvia()
        self.strumento(g, "Righello")
        x, y = self.centro_vuoto(g)
        g.mouse.move(x, y)
        g.mouse.down()
        for i in range(1, 8):
            g.mouse.move(x + 30 * i, y + 10)
        expect(a.locator("#sovra text", has_text="📏")).to_be_visible()     # il Master vede la misura dal vivo
        g.mouse.up()
        expect(a.locator("#sovra text", has_text="📏")).to_have_count(0)
        self.strumento(g, "Ping")
        g.mouse.click(x + 40, y + 40)
        expect(a.locator("#sovra .ping", has_text="Giulia")).to_be_visible()

    def test_nebbia(self):
        a, (g,) = self.avvia()
        a.locator("#schede-nav button", has_text="Master").click()
        a.locator(".bestiario button", has_text="Coboldo").click()
        coboldo = g.locator(".pedina", has_text="Coboldo")
        expect(coboldo).to_be_visible()
        self.strumento(a, "Nebbia")
        a.locator("#nebbia-strumenti").get_by_label("attiva su questa mappa").check()
        expect(coboldo).to_be_hidden()                                       # tutto coperto: il mostro sparisce
        expect(g.locator(".pedina.mia")).to_be_visible()                     # il proprio personaggio no
        self.assertGreater(g.evaluate("document.getElementById('nebbia-cv').width"), 0)
        # il Master rivela tutta la mappa con un rettangolo
        a.locator("#nebbia-strumenti button", has_text="area").click()
        b = a.locator("#mappa").bounding_box()
        # dall'angolo in basso a sinistra a quello in alto a destra (in alto a sinistra c'è il riquadro della nebbia)
        a.mouse.move(b["x"] + 2, b["y"] + b["height"] - 2)
        a.mouse.down()
        a.mouse.move(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2, steps=5)
        a.mouse.move(b["x"] + b["width"] - 2, b["y"] + 2, steps=5)
        a.mouse.up()
        expect(coboldo).to_be_visible()
        # «Copri tutto» (con conferma) lo nasconde di nuovo
        a.locator("#nebbia-strumenti button", has_text="Copri tutto").click()
        a.locator(".dialogo").get_by_role("button", name="Copri tutto").click()
        expect(coboldo).to_be_hidden()

    def test_turni(self):
        a, (g, h) = self.avvia(giocatori=("Giulia", "Marco"))
        for p in (a, g, h):
            p.locator("#schede-nav button", has_text="Turni").click()
        g.locator("#tab-iniziativa button", has_text="Tira iniziativa").click()
        expect(a.locator(".ini-lista li", has_text="Rocco")).to_be_visible()
        a.locator(".ini-master input[name=nome]").fill("Orco")
        a.locator(".ini-master input[name=val]").fill("99")
        a.locator(".ini-master form button").click()
        expect(h.locator(".ini-lista li").first).to_contain_text("Orco")    # il più alto agisce per primo
        a.locator(".ini-master button", has_text="Prossimo turno").click()
        expect(h.locator(".ini-lista li.corrente")).to_have_count(1)
        prima = h.locator(".ini-lista li.corrente").inner_text()
        a.locator(".ini-master button", has_text="Prossimo turno").click()
        expect(h.locator(".ini-lista li.corrente")).not_to_have_text(prima)
        self.assertEqual(g.locator(".ini-master").count(), 0)               # i giocatori non comandano i turni
        a.locator(".ini-master button", has_text="Fine scontro").click()
        a.locator(".dialogo button.primario").click()                        # conferma
        expect(h.locator(".ini-lista li", has_text="Orco")).to_have_count(0)

    def test_documenti(self):
        a, (g,) = self.avvia()
        for p in (a, g):
            p.locator("#schede-nav button", has_text="Gruppo").click()
        expect(g.locator(".documenti a", has_text="Guida del Giocatore")).to_be_visible()
        expect(g.locator(".documenti a", has_text="Manuale del Master")).to_have_count(0)   # solo per il Master
        manuale = a.locator(".documenti a", has_text="Manuale del Master")
        expect(manuale).to_be_visible()
        guida = urljoin(g.url, g.locator(".documenti a", has_text="Guida del Giocatore").get_attribute("href"))
        self.assertEqual(g.request.get(guida).status, 200)
        url_manuale = urljoin(a.url, manuale.get_attribute("href"))
        self.assertEqual(a.request.get(url_manuale).status, 200)
        self.assertNotEqual(g.request.get(url_manuale.split("?")[0]).status, 200)   # senza credenziali del Master no
        expect(g.locator("#tab-gruppo .party-pg", has_text="Rocco")).to_be_visible()

    def test_carica_mappa_e_avventura(self):
        a, (g,) = self.avvia()
        a.locator("#schede-nav button", has_text="Master").click()
        a.locator("#tab-master summary", has_text="Carica una mappa").click()
        a.locator("#tab-master input[accept^='image/']").set_input_files({"name": "bosco.png", "mimeType": "image/png", "buffer": PNG})
        a.get_by_placeholder("Titolo della mappa").fill("Bosco fitto")
        a.locator("#tab-master details[open] button", has_text="Carica").last.click()
        expect(a.locator("#m-scene button", has_text="Bosco fitto")).to_be_visible()
        a.locator("#m-scene button", has_text="Bosco fitto").click()
        expect(g.locator(".titolo-scena")).to_contain_text("Bosco fitto")
        zip_ = zip_di({"pkg/avventura.json": json.dumps({"id": "caricata", "titolo": "Avventura caricata", "documenti": []}),
                       "pkg/personaggi.json": "[]", "pkg/mappe/a.svg": '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>'})
        a.locator("#tab-master input[accept^='.zip']").set_input_files({"name": "caricata.zip", "mimeType": "application/zip", "buffer": zip_})
        a.locator("#tab-master button", has_text="Carica").first.click()
        expect(a.locator("#tab-master .avv", has_text="Avventura caricata")).to_be_visible()

    def test_salvataggio(self):
        a, (g,) = self.avvia()
        a.locator("#schede-nav button", has_text="Master").click()
        a.locator("#tab-master summary", has_text="Salvataggio").click()
        with a.expect_download() as d:
            a.locator("#tab-master a", has_text="Scarica salvataggio").click()
        file = d.value.path()
        salvato = json.load(open(file))
        self.assertIn("pedine", salvato)
        pedine = g.locator(".pedina").count()
        a.locator(".bestiario button", has_text="Coboldo").click()
        expect(g.locator(".pedina")).to_have_count(pedine + 1)
        a.locator("#tab-master input[accept='application/json']").set_input_files(file)
        a.locator(".dialogo").get_by_role("button", name="Carica").click()
        expect(g.locator(".pedina")).to_have_count(pedine)                  # tornati com'era al salvataggio

class TestSistemaVecchio(GuiBase):
    """L'amministrazione del client vecchio (/vecchio/) ha le stesse sezioni di quella nuova."""

    def entra_sistema_vecchio(self, telefono=False):
        p = self.pagina(telefono)
        p.goto(self.url + "vecchio/admin")
        p.locator("#in-pw").fill(PW_ADMIN)
        p.locator("#in-admin-btn").click()
        expect(p.locator("#sis-nav")).to_be_visible()
        return p

    def test_sezioni_e_niente_sala(self):
        p = self.entra_sistema_vecchio()
        expect(p.locator("#sala")).to_be_hidden()
        expect(p.locator("#nome-scena")).to_contain_text("Amministrazione")
        for nome in ["Generale", "Accesso con account", "Utenti e permessi", "Partite e backup", "Registro", "Account di sistema"]:
            p.locator("#sis-nav button", has_text=nome).click()
            expect(p.locator(".sis-sez:not([hidden]) h2")).to_contain_text(nome.split()[0])
        expect(p.locator("#i-audit .utente").first).to_contain_text("accesso di sistema")

    def test_salva_e_utenti(self):
        g = Client(self.srv)
        g.login_ospite("DaPromuovere")
        p = self.entra_sistema_vecchio()
        p.locator("#sis-nav button", has_text="Generale").click()
        salva = p.locator('.sis-sez[data-sez="generale"] [data-salva]')
        expect(salva).to_be_disabled()
        p.locator("#i-nome").fill("Tavolo vecchio")
        expect(salva).to_be_enabled()
        salva.click()
        expect(salva).to_be_disabled()
        self.assertEqual(Client(self.srv).get("/api/info").json["nome_tavolo"], "Tavolo vecchio")
        p.locator("#sis-nav button", has_text="Utenti").click()
        p.locator("#i-cerca").fill("promuo")
        expect(p.locator("#i-utenti .utente")).to_have_count(1)
        p.locator("#i-utenti .utente", has_text="DaPromuovere").get_by_label("Admin").check()
        expect(p.locator("#i-utenti .utente .chip", has_text="admin")).to_be_visible()
        p.locator("#i-cerca").fill("")
        p.locator("#i-filtri button", has_text="Admin").click()
        expect(p.locator("#i-utenti .utente")).to_have_count(1)
        expect(p.locator("#i-pulizia")).to_have_class(re.compile("ok"))   # niente da pulire

    def test_telefono(self):
        p = self.entra_sistema_vecchio(telefono=True)
        p.locator("#sis-nav button", has_text="Utenti").click()
        expect(p.locator(".sis-sez:not([hidden]) h2")).to_contain_text("Utenti")
        self.assertFalse(p.evaluate("document.documentElement.scrollWidth > innerWidth"), "la pagina scorre di lato")
        self.assertLessEqual(p.evaluate("document.querySelector('.sis-pagina').getBoundingClientRect().right"), 390, "contenuto tagliato a destra")


class TestCompatibilita(GuiBase):
    def test_chi_era_dentro_col_vecchio_client_resta_dentro(self):
        p = self.pagina()
        p.goto(self.url + "vecchio/")
        p.locator("#in-nome").fill("Veterano")
        p.locator("#in-ospite-btn").click()
        expect(p.locator("#sala")).to_be_visible()          # dentro col client vecchio (credenziali salvate)
        p.goto(self.url)
        expect(p.locator("#sala")).to_be_visible()
        expect(p.locator("#sala")).to_contain_text("Veterano")

    def test_indirizzi(self):
        c = Client(self.srv)
        r = c.get("/beta/?accesso=1")                                     # il vecchio indirizzo provvisorio
        self.assertEqual((r.status, r.h("location")), (308, "/?accesso=1"))
        self.assertEqual(c.get("/beta").h("location"), "/")
        vecchio = c.get("/vecchio/")
        self.assertEqual(vecchio.status, 200)
        self.assertIn(b"app.js?v=", vecchio.body)
        self.assertNotIn(b"__VERSIONE__", vecchio.body)
        self.assertEqual(c.get("/vecchio/style.css").status, 200)
        self.assertEqual(c.get("/vecchio").h("location"), "/vecchio/")
        self.assertIn(b"<app-root>", c.get("/").body)
        self.assertEqual(c.get("/admin/?x=1").h("location"), "/admin?x=1")
        self.assertIn(b"<app-root>", c.get("/admin").body)                # percorso dell'app: stessa pagina
        self.assertEqual(c.get("/non-esiste.js").status, 404)
        self.assertNotIn(b"root:", c.get("/../../etc/passwd").body)
        self.assertNotIn(b"root:", c.get("/vecchio/../../../etc/passwd").body)

    def test_ingresso_admin_e_vecchio_client(self):
        p = self.pagina()
        p.goto(self.url + "admin/")                                       # ingresso di riserva dell'amministratore
        expect(p.locator("details.admin-box")).to_have_attribute("open", "")
        v = self.pagina()
        v.goto(self.url + "vecchio/")                                     # il vecchio funziona ancora
        v.locator("#in-nome").fill("Nostalgico")
        v.locator("#in-ospite-btn").click()
        expect(v.locator("#sala")).to_be_visible()


if __name__ == "__main__":
    unittest.main()
