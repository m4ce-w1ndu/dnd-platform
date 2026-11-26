"""Accesso: login, ingresso al tavolo, sessione, file statici e file delle avventure."""
import time
import unittest

from harness import PW_ADMIN, Base, Client, Server


class TestLogin(Base):
    def test_ospite_e_riuso_credenziali(self):
        c = self.nuovo()
        r = c.login_ospite("Gimli")
        self.assertEqual(r.status, 200)
        self.assertTrue(r.json["ok"])
        self.assertEqual(r.json["nome"], "Gimli")
        primo = c.id
        r = c.login_ospite("Gimli Secondo")        # stesse credenziali: stesso utente, nome nuovo
        self.assertEqual(c.id, primo)
        self.assertEqual(r.json["nome"], "Gimli Secondo")

    def test_nome_vuoto_o_riservato(self):
        for nome in ("", "   "):
            self.assertEqual(self.nuovo().login_ospite(nome).status, 400)
        for nome in ("admin", "Admin", "  ADMIN  ", "Master", "sistema", "Amministratore"):
            r = self.nuovo().login_ospite(nome)
            self.assertEqual(r.status, 400, nome)
            self.assertIn("riservato", r.json["errore"])

    def test_admin_password_sbagliata(self):
        self.assertEqual(self.nuovo().login_admin("sbagliata").status, 403)
        self.assertEqual(self.nuovo().login_admin(PW_ADMIN, utente="altro").status, 403)
        self.assertEqual(self.nuovo().login_admin("").status, 403)

    def test_admin_ok(self):
        c = self.nuovo()
        r = c.login_admin()
        self.assertTrue(r.json["ok"])
        io = c.get("/api/io?" + c.qs()).json
        self.assertTrue(io["admin"])
        self.assertTrue(io["master"])

    def test_tipo_non_valido_e_json_rotto(self):
        c = self.nuovo()
        self.assertEqual(c.post("/api/login", {"tipo": "boh"}).status, 400)
        self.assertEqual(c.req("POST", "/api/login", raw=b"{rotto").status, 400)

    def test_limite_tentativi_per_ip(self):
        c = self.nuovo()
        stati = [c.post("/api/login", {"tipo": "admin", "utente": "admin", "password": "no"}).status for _ in range(16)]
        self.assertIn(429, stati)
        self.assertEqual(stati[0], 403)

    def test_io(self):
        c = self.nuovo()
        self.assertEqual(c.get("/api/io").status, 401)
        self.assertEqual(c.get("/api/io?c=nessuno&s=x").status, 401)
        c.login_ospite("Frodo")
        self.assertEqual(c.get("/api/io?c=" + c.id + "&s=sbagliato", auth=False).status, 401)
        io = c.get("/api/io?" + c.qs()).json
        self.assertEqual(io["nome"], "Frodo")
        self.assertFalse(io["admin"])
        self.assertFalse(io["master"])
        for k in ("provider", "avatar", "char", "colore", "ruolo"):
            self.assertIn(k, io)


class TestEntra(Base):
    def test_senza_credenziali(self):
        c = self.nuovo()
        r = c.post("/api/entra", {"id": "x", "secret": "y"})
        self.assertEqual(r.status, 401)
        self.assertTrue(r.json["login"])

    def test_master_solo_se_abilitato(self):
        c = self.nuovo()
        c.login_ospite("Sam")
        self.assertTrue(c.entra("master").json["ok"])
        self.assertEqual(c.get("/api/io?" + c.qs()).json["ruolo"], "giocatore")

    def test_nome_riservato_in_entra(self):
        c = self.nuovo()
        c.login_ospite("Pipino")
        r = c.entra("giocatore", nome="Admin")
        self.assertEqual(r.status, 400)
        self.assertEqual(c.get("/api/io?" + c.qs()).json["nome"], "Pipino")
        # l'amministratore invece può chiamarsi come vuole
        a = self.nuovo()
        a.login_admin()
        self.assertTrue(a.entra("master", nome="Master").json["ok"])
        self.admin.entra("master")          # si rimette il Master di questa classe

    def test_colore_validato(self):
        c = self.nuovo()
        c.login_ospite("Merry")
        c.entra("giocatore", colore='red;"><script>')
        self.assertEqual(c.get("/api/io?" + c.qs()).json["colore"], "#c0392b")
        c.entra("giocatore", colore="#12ab34")
        self.assertEqual(c.get("/api/io?" + c.qs()).json["colore"], "#12ab34")

    def test_personaggio_inesistente_ignorato(self):
        c = self.nuovo()
        c.login_ospite("Boromir")
        self.assertTrue(c.entra("giocatore", "non-esiste").json["ok"])
        self.assertIsNone(c.get("/api/io?" + c.qs()).json["char"])

    def test_personaggio_gia_preso(self):
        g1 = self.giocatore("lia")
        info = g1.get("/api/info").json
        self.assertIn("lia", info["presi"])
        g2 = self.nuovo()
        g2.login_ospite("Ladro")
        r = g2.entra("giocatore", "lia")
        self.assertEqual(r.status, 409)
        g2.entra("giocatore")
        g2.collega()
        r = g2.op("scegli_pg", pg="lia")
        self.assertFalse(r.json["ok"])
        self.assertIsNone(g2.get("/api/io?" + g2.qs()).json["char"])
        # quando il primo esce dal tavolo il posto si libera (Python se ne accorge al ping successivo, fino a 30 s)
        g1.scollega()
        fine = time.time() + 40
        while "lia" in g2.get("/api/info").json["presi"] and time.time() < fine:
            time.sleep(0.1)
        self.assertTrue(g2.op("scegli_pg", pg="lia").json["ok"])
        self.assertEqual(self.pedina_pg("lia")["proprietario"], g2.id)

    def test_entra_crea_pedina_del_personaggio(self):
        g = self.giocatore("bruno")
        p = self.pedina_pg("bruno")
        self.assertEqual(p["proprietario"], g.id)
        self.assertEqual(p["pfmax"], 14)
        self.assertEqual(p["tipo"], "pg")


class TestSessione(unittest.TestCase):
    def setUp(self):
        self.srv = Server()

    def tearDown(self):
        self.srv.chiudi()

    def test_ciclo_della_serata(self):
        info = Client(self.srv).get("/api/info").json
        self.assertEqual(info["sessione"], "chiusa")
        self.assertEqual(info["avventura"]["id"], "")
        self.assertEqual(info["personaggi"], [])
        for k in ("presi", "password_giocatori", "login", "ospiti", "versione", "nome_tavolo"):
            self.assertIn(k, info)
        self.assertTrue(info["versione"])

        a = Client(self.srv)
        a.login_admin()
        a.entra("master")
        a.collega()
        self.assertFalse(a.op("sessione_apri", id="non-esiste").json["ok"])
        a.ok("sessione_apri", id="prova")
        self.assertTrue(a.aspetta(lambda e: e.get("t") == "sessione" and e["sessione"] == "lobby"))
        info = a.get("/api/info").json
        self.assertEqual(info["sessione"], "lobby")
        self.assertEqual(info["avventura"]["id"], "prova")
        self.assertEqual({p["id"] for p in info["personaggi"]}, {"rocco", "lia", "bruno"})
        self.assertNotIn("pf", info["personaggi"][0])          # solo i campi per la scelta

        g = Client(self.srv)
        g.login_ospite("Aragorn")
        g.entra()
        g.collega()
        self.assertFalse(g.op("sessione_inizia").json["ok"])
        a.ok("sessione_inizia")
        self.assertTrue(g.aspetta(lambda e: e.get("t") == "sessione" and e["sessione"] == "in_corso"))
        self.assertEqual(g.stato()["sessione"], "in_corso")
        self.assertFalse(g.op("sessione_pausa").json["ok"])
        a.ok("sessione_pausa")
        self.assertEqual(g.stato()["sessione"], "lobby")
        self.assertFalse(g.op("sessione_chiudi").json["ok"])
        a.ok("sessione_chiudi")
        self.assertEqual(g.get("/api/info").json["sessione"], "chiusa")
        a.scollega()
        g.scollega()


class TestStatico(Base):
    def test_index_e_intestazioni(self):
        c = self.nuovo()
        for path in ("/", "/admin", "/admin/", "/index.html"):
            r = c.get(path)
            self.assertEqual(r.status, 200, path)
            self.assertIn("text/html", r.h("content-type"))
            self.assertNotIn(b"__VERSIONE__", r.body)
            self.assertIn("default-src 'self'", r.h("content-security-policy"))
            self.assertIn("frame-ancestors", r.h("content-security-policy"))
            self.assertEqual(r.h("x-content-type-options"), "nosniff")
        info = c.get("/api/info")
        self.assertEqual(info.h("x-content-type-options"), "nosniff")
        self.assertEqual(info.h("cache-control"), "no-store")

    def test_file_e_traversal(self):
        c = self.nuovo()
        self.assertIn("javascript", c.get("/app.js").h("content-type"))
        self.assertIn("text/css", c.get("/style.css").h("content-type"))
        for path in ("/non-esiste.js", "/../server.py", "/%2e%2e/server.py", "/..%2fserver.py", "/web/../../server.py"):
            self.assertEqual(c.get(path).status, 404, path)


class TestFileAvventura(Base):
    def test_mappe(self):
        c = self.nuovo()
        r = c.get("/avventure/prova/mappe/01_piazza.svg")
        self.assertEqual(r.status, 200)
        self.assertIn("image/svg+xml", r.h("content-type"))
        self.assertEqual(c.get("/avventure/prova/mappe/03_bosco.png").h("content-type"), "image/png")

    def test_traversal_e_percorsi_strani(self):
        c = self.nuovo()
        for path in ("/avventure/prova/../../dati/tavolo.db", "/avventure/prova/mappe/../../../dati/tavolo.db",
                     "/avventure/prova/%2e%2e/%2e%2e/dati/tavolo.db", "/avventure/prova/altro/x.svg",
                     "/avventure/PROVA!/mappe/01_piazza.svg", "/avventure/prova/mappe/", "/avventure/prova",
                     "/avventure/prova/avventura.json", "/avventure/prova/mappe/nope.svg"):
            self.assertEqual(c.get(path).status, 404, path)

    def test_documenti_solo_master(self):
        g = self.giocatore()
        anonimo = self.nuovo()
        self.assertEqual(anonimo.get("/avventure/prova/documenti/manuale.html").status, 403)
        self.assertEqual(g.get("/avventure/prova/documenti/manuale.html?" + g.qs()).status, 403)
        r = self.admin.get("/avventure/prova/documenti/manuale.html?" + self.admin.qs())
        self.assertEqual(r.status, 200)
        self.assertIn(b"SEGRETO-MANUALE", r.body)
        self.assertTrue(r.h("content-security-policy").startswith("sandbox"))

    def test_documenti_in_sandbox(self):
        c = self.nuovo()
        r = c.get("/avventure/prova/documenti/guida.html")
        self.assertEqual(r.status, 200)
        csp = r.h("content-security-policy")
        self.assertTrue(csp.startswith("sandbox"), csp)
        self.assertNotIn("allow-scripts", csp)
        self.assertNotIn("allow-same-origin", csp)
        pdf = c.get("/avventure/prova/documenti/mappa.pdf")
        self.assertEqual(pdf.status, 200)
        self.assertFalse(pdf.h("content-security-policy").startswith("sandbox"))


class TestOspitiEOAuth(Base):
    def test_password_del_tavolo(self):
        self.admin.ok("imp_salva", config={"password_giocatori": "segreta"})
        try:
            self.assertTrue(self.nuovo().get("/api/info").json["password_giocatori"])
            self.assertEqual(self.nuovo().login_ospite("Tizio").status, 403)
            self.assertEqual(self.nuovo().login_ospite("Tizio", password="no").status, 403)
            self.assertTrue(self.nuovo().login_ospite("Tizio", password="segreta").json["ok"])
        finally:
            self.admin.ok("imp_salva", config={"password_giocatori": ""})

    def test_ospiti_spenti_e_oauth(self):
        c = self.nuovo()
        self.assertEqual(c.get("/auth/discord/start").status, 404)       # provider non configurato
        self.admin.ok("imp_salva", config={"ospiti": False, "oauth": {"discord": {"attivo": True, "id": "157050307642143970", "secret": "s3greto"}}})
        try:
            info = c.get("/api/info").json
            self.assertFalse(info["ospiti"])
            self.assertEqual(info["login"], [{"id": "discord", "nome": "Discord"}])
            self.assertEqual(c.login_ospite("Ospite").status, 403)
            self.assertTrue(self.nuovo().login_admin().json["ok"])       # l'admin entra sempre
            r = c.get("/auth/discord/start", headers={"Host": "tavolo.example.org", "X-Forwarded-Proto": "https"})
            self.assertEqual(r.status, 302)
            loc = r.h("location")
            self.assertTrue(loc.startswith("https://discord.com/oauth2/authorize?"), loc)
            for parte in ("client_id=157050307642143970", "state=", "code_challenge=", "code_challenge_method=S256",
                          "redirect_uri=https%3A%2F%2Ftavolo.example.org%2Fauth%2Fdiscord%2Fcallback"):
                self.assertIn(parte, loc)
            r = c.get("/auth/discord/callback?code=x&state=falso")
            self.assertEqual(r.status, 200)
            self.assertIn("scaduto".encode(), r.body)
            self.assertNotIn(b"tv_cred", r.body)
            r = c.get("/auth/discord/callback?error=access_denied")
            self.assertIn("annullato".encode(), r.body)
            leggi = self.admin.ok("imp_leggi")
            self.assertTrue(leggi["config"]["oauth"]["discord"]["secret_impostato"])
            self.assertNotIn("s3greto", str(leggi))
        finally:
            self.admin.ok("imp_salva", config={"ospiti": True, "oauth": {"discord": {"attivo": False}}})
        self.assertTrue(self.nuovo().login_ospite("Ospite").json["ok"])


if __name__ == "__main__":
    unittest.main()
