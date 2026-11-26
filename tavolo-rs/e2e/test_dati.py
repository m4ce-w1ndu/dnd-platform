"""Dati: caricamenti, pacchetti avventura, esporta/importa/backup, impostazioni, persistenza."""
import io
import json
import os
import time
import unittest
import zipfile

from harness import PW_ADMIN, Base, Client, Server
from test_permessi import PNG


def zip_di(files, comprimi=zipfile.ZIP_DEFLATED):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", comprimi) as z:
        for nome, dati in files.items():
            z.writestr(nome, dati)
    return buf.getvalue()


MANIFEST = json.dumps({"id": "caricata", "titolo": "Avventura caricata", "documenti": []})


class TestCaricamenti(Base):
    def carica(self, path, raw, c=None):
        c = c or self.admin
        return c.req("POST", path + ("&" if "?" in path else "?") + c.qs(), raw=raw)

    def test_mappa(self):
        r = self.carica("/api/carica_mappa?nome=Il%20Bosco.png&titolo=Bosco%20fitto&cella=50", PNG)
        self.assertTrue(r.json["ok"], r)
        mid = r.json["id"]
        self.assertEqual(mid, "il_bosco")
        m = next(s for s in self.admin.stato()["avv"]["mappe"] if s["id"] == mid)
        self.assertEqual((m["titolo"], m["gruppo"], m["griglia"]["cella"]), ("Bosco fitto", "Caricate", 50.0))
        self.assertEqual((m["larghezza"], m["altezza"]), (16, 16))
        r2 = self.carica("/api/carica_mappa?nome=Il%20Bosco.png", PNG)
        self.assertNotEqual(r2.json["id"], mid)                 # nessuna sovrascrittura
        self.assertEqual(self.carica("/api/carica_mappa?nome=virus.exe", b"MZ").status, 400)
        strano = self.carica("/api/carica_mappa?nome=..%2F..%2Fx.png", PNG).json["id"]
        self.assertNotIn("/", strano)
        self.assertNotIn(".", strano)
        self.assertEqual(self.admin.get("/" + m["file"]).status, 200)
        self.assertFalse(os.path.exists(os.path.join(self.srv.tmp, "x.png")))

    def test_documento(self):
        g = self.giocatore()
        r = self.carica("/api/carica_documento?nome=Segreti%20del%20DM.html&titolo=Segreti&solo_master=1", b"<p>shh</p>")
        self.assertTrue(r.json["ok"], r)
        docs = {d["file"]: d for d in self.admin.stato()["avv"]["documenti"]}
        self.assertTrue(docs["Segreti_del_DM.html"]["solo_master"])
        self.assertNotIn("Segreti_del_DM.html", [d["file"] for d in g.stato()["avv"]["documenti"]])
        self.assertEqual(g.get("/avventure/prova/documenti/Segreti_del_DM.html?" + g.qs()).status, 403)
        self.assertEqual(self.carica("/api/carica_documento?nome=x.exe", b"MZ").status, 400)
        self.carica("/api/carica_documento?nome=pubblico.md&titolo=Pubblico", b"# ciao")
        self.assertIn("pubblico.md", [d["file"] for d in g.stato()["avv"]["documenti"]])
        self.admin.ok("documento_elimina", file="../../pubblico.md")
        self.assertNotIn("pubblico.md", [d["file"] for d in g.stato()["avv"]["documenti"]])
        self.admin.ok("documento_elimina", file="../avventura.json")
        self.assertIn("prova", [a["id"] for a in self.admin.stato()["catalogo"]])

    def test_pacchetto_avventura(self):
        g = self.giocatore()
        self.assertEqual(self.carica("/api/carica_avventura", b"non sono uno zip").status, 400)
        self.assertEqual(self.carica("/api/carica_avventura", zip_di({"x/readme.txt": "ciao"})).status, 400)
        cattivo = zip_di({"pkg/avventura.json": MANIFEST, "pkg/../../evil.txt": "pwn", "pkg/mappe/a.svg": "<svg/>"})
        self.assertEqual(self.carica("/api/carica_avventura", cattivo).status, 400)
        for root, _d, files in os.walk(self.srv.tmp):
            self.assertNotIn("evil.txt", files)
        r = self.carica("/api/carica_avventura", zip_di({"pkg/avventura.json": MANIFEST, "pkg/personaggi.json": "[]",
                                                         "pkg/mappe/a.svg": '<svg width="10" height="10"/>'}))
        self.assertTrue(r.json["ok"], r)
        self.assertEqual((r.json["id"], r.json["titolo"]), ("caricata", "Avventura caricata"))
        self.assertIn("caricata", [a["id"] for a in self.admin.stato()["catalogo"]])
        strano = zip_di({"a/avventura.json": json.dumps({"id": "../../Strano ID!", "titolo": "S"})})
        r = self.carica("/api/carica_avventura", strano)
        self.assertTrue(r.json["ok"], r)
        self.assertTrue(os.path.isdir(os.path.join(self.srv.avv, r.json["id"])))
        self.assertEqual(self.carica("/api/carica_avventura", zip_di({"p/avventura.json": MANIFEST}), c=g).status, 403)

    def test_zip_bomb(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("b/avventura.json", MANIFEST.replace("caricata", "bomba"))
            with z.open("b/mappe/zeri.svg", "w", force_zip64=True) as f:
                blocco = b"\0" * (1 << 20)
                for _ in range(310):
                    f.write(blocco)
        self.assertLess(len(buf.getvalue()), 2_000_000)
        r = self.carica("/api/carica_avventura", buf.getvalue())
        self.assertEqual(r.status, 400)
        self.assertFalse(os.path.exists(os.path.join(self.srv.avv, "bomba")))

    def test_scarica_avventura(self):
        r = self.admin.get("/api/scarica_avventura?id=prova&" + self.admin.qs())
        self.assertEqual(r.status, 200)
        self.assertEqual(r.h("content-type"), "application/zip")
        nomi = zipfile.ZipFile(io.BytesIO(r.body)).namelist()
        self.assertIn("prova/avventura.json", nomi)
        self.assertIn("prova/mappe/01_piazza.svg", nomi)
        self.assertEqual(self.admin.get("/api/scarica_avventura?id=..%2Fdati&" + self.admin.qs()).status, 403)


class TestAvventure(Base):
    def test_nuova_info_elimina(self):
        aid = self.admin.ok("avventura_nuova", titolo="Àrè Città!")["id"]
        self.assertEqual(aid, "are-citta")
        aid2 = self.admin.ok("avventura_nuova", titolo="Àrè Città!")["id"]
        self.assertNotEqual(aid, aid2)
        self.assertFalse(self.admin.op("avventura_nuova", titolo="  ").json["ok"])
        self.admin.ok("avventura_info", titolo="Prova rinominata", livello="5")
        cat = {a["id"]: a for a in self.admin.stato()["catalogo"]}
        self.assertEqual((cat["prova"]["titolo"], cat["prova"]["livello"]), ("Prova rinominata", "5"))
        self.assertFalse(self.admin.op("avventura_elimina", id="prova").json["ok"])       # quella in corso no
        self.assertFalse(self.admin.op("avventura_elimina", id="../dati").json["ok"])
        self.assertFalse(self.admin.op("avventura_elimina", id="non-esiste").json["ok"])
        self.admin.ok("avventura_elimina", id=aid)
        self.assertNotIn(aid, [a["id"] for a in self.admin.stato()["catalogo"]])
        self.assertFalse(os.path.exists(os.path.join(self.srv.avv, aid)))
        self.assertTrue(os.path.isdir(self.srv.dati))

    def test_cambio_avventura_e_mappe(self):
        g = self.giocatore("rocco")
        self.admin.ok("chat", testo="in prova")
        self.admin.ok("avventura_attiva", id="seconda")
        st = self.admin.stato()
        self.assertEqual((st["avventura"], st["scena"], st["avv"]["id"]), ("seconda", "unica", "seconda"))
        self.assertIsNone(g.get("/api/io?" + g.qs()).json["char"])          # rocco non esiste in «seconda»
        self.assertFalse(self.admin.op("mappa_elimina", id="unica").json["ok"])   # almeno una mappa
        self.assertFalse(self.admin.op("avventura_attiva", id="non-esiste").json["ok"])
        self.admin.ok("avventura_attiva", id="prova")
        st = self.admin.stato()
        self.assertIn("in prova", [v.get("testo") for v in st["log"]])        # la partita di prova era salvata
        self.admin.ok("scena", id="02_grotta", porta_gruppo=False)
        self.admin.ok("mappa_elimina", id="02_grotta")
        st = self.admin.stato()
        self.assertEqual(st["scena"], "01_piazza")
        self.assertNotIn("02_grotta", [m["id"] for m in st["avv"]["mappe"]])
        self.assertFalse(self.admin.op("mappa_elimina", id="non-esiste").json["ok"])

    def test_osservatore(self):
        self.admin.collega()
        try:
            dest = os.path.join(self.srv.avv, "copiata")
            os.makedirs(os.path.join(dest, "mappe"))
            with open(os.path.join(dest, "avventura.json"), "w") as f:
                json.dump({"titolo": "Copiata a mano"}, f)
            self.assertTrue(self.admin.aspetta(lambda e: e.get("t") == "catalogo", 12))
            self.assertIn("copiata", [a["id"] for a in self.admin.stato()["catalogo"]])
        finally:
            self.admin.scollega()


class TestEsportaImporta(Base):
    def test_giro_completo(self):
        pid = self.admin.ok("pedina_salva", pedina={"nome": "Statua", "x": 4, "y": 4})["id"]
        self.admin.ok("note_master", testo="note da esportare")
        r = self.admin.get("/api/esporta?" + self.admin.qs())
        self.assertEqual(r.status, 200)
        self.assertIn("attachment", r.h("content-disposition"))
        salvata = r.json
        self.assertIn(pid, salvata["pedine"])
        self.assertEqual(salvata["note_master"], "note da esportare")
        self.assertEqual(self.admin.get("/api/esporta?id=seconda&" + self.admin.qs()).json, {})
        self.admin.ok("reset_partita")
        self.assertEqual(self.admin.stato()["pedine"], {})
        r = self.admin.post("/api/importa", {**salvata, "estraneo": "x"})
        self.assertTrue(r.json["ok"])
        st = self.admin.stato()
        self.assertIn(pid, st["pedine"])
        self.assertNotIn("estraneo", st)
        self.assertEqual(st["note_master"], "note da esportare")

    def test_backup(self):
        r = self.admin.get("/api/backup?" + self.admin.qs())
        self.assertEqual(r.status, 200)
        self.assertTrue(r.body.startswith(b"SQLite format 3\x00"))
        self.assertIn(".db", r.h("content-disposition"))


class TestImpostazioni(Base):
    def test_leggi_senza_segreti(self):
        g = self.giocatore()
        r = self.admin.ok("imp_leggi")
        self.assertNotIn(g.secret, json.dumps(r))
        self.assertNotIn("hash", json.dumps(r["config"]))
        utente = next(u for u in r["utenti"] if u["id"] == g.id)
        self.assertTrue(utente["online"])
        for k in ("nome", "account", "provider", "avatar", "master", "admin", "visto", "io"):
            self.assertIn(k, utente)
        self.assertEqual(r["config"]["admin_utente"], "admin")
        self.assertEqual(set(r["config"]["oauth"]), {"discord", "google", "github"})

    def test_salva_validazione(self):
        r = self.admin.ok("imp_salva", config={"public_url": "Dnd.Esempio.it/percorso/", "nome_tavolo": "  Il Tavolo  "})
        self.assertEqual(r["config"]["public_url"], "https://dnd.esempio.it")
        self.assertEqual(r["config"]["nome_tavolo"], "Il Tavolo")
        self.assertEqual(self.nuovo().get("/api/info").json["nome_tavolo"], "Il Tavolo")
        self.assertFalse(self.admin.op("imp_salva", config={"public_url": "https://senza punto"}).json["ok"])
        self.assertFalse(self.admin.op("imp_salva", config={"public_url": "javascript:alert(1)"}).json["ok"])
        r = self.admin.op("imp_salva", config={"oauth": {"discord": {"attivo": True, "id": "non-numerico", "secret": "s"}}})
        self.assertFalse(r.json["ok"])
        self.assertIn("Discord", r.json["errore"])
        r = self.admin.ok("imp_salva", config={"oauth": {"google": {"attivo": False, "id": "strano"}}})
        self.assertEqual(r["config"]["oauth"]["google"]["id"], "")          # spento con valore strano: invariato
        self.admin.ok("imp_salva", config={"public_url": ""})

    def test_password_admin(self):
        self.assertFalse(self.admin.op("imp_admin", attuale="sbagliata", nuova="nuovapassword").json["ok"])
        self.assertFalse(self.admin.op("imp_admin", attuale=PW_ADMIN, nuova="corta").json["ok"])
        self.admin.ok("imp_admin", attuale=PW_ADMIN, nuova="nuovapassword", utente="capo")
        self.assertEqual(self.nuovo().login_admin(PW_ADMIN).status, 403)
        self.assertEqual(self.nuovo().login_admin("nuovapassword").status, 403)        # utente cambiato
        self.assertTrue(self.nuovo().login_admin("nuovapassword", utente="Capo").json["ok"])
        self.assertEqual(self.nuovo().login_ospite("capo").status, 400)                # nome riservato
        self.admin.ok("imp_admin", attuale="nuovapassword", nuova=PW_ADMIN, utente="admin")
        self.assertTrue(self.nuovo().login_admin().json["ok"])

    def test_utenti(self):
        g, h = self.giocatore(), self.giocatore()
        self.assertFalse(self.admin.op("imp_utente", id="non-esiste").json["ok"])
        self.assertFalse(self.admin.op("imp_utente", id=self.admin.id, elimina=True).json["ok"])
        self.admin.ok("imp_utente", id=self.admin.id, admin=False)                      # ignorato: niente auto-retrocessione
        self.assertTrue(self.admin.get("/api/io?" + self.admin.qs()).json["admin"])
        self.admin.ok("imp_utente", id=g.id, master=True)
        g.entra("master")
        self.assertEqual(g.get("/api/io?" + g.qs()).json["ruolo"], "master")
        self.admin.ok("imp_utente", id=g.id, master=False)
        self.assertTrue(g.aspetta(lambda e: e.get("t") == "ricarica"))
        self.assertEqual(g.get("/api/io?" + g.qs()).json["ruolo"], "giocatore")
        self.admin.ok("imp_utente", id=g.id, admin=True)
        self.assertTrue(g.op("imp_leggi").json["ok"])
        self.admin.ok("imp_utente", id=g.id, admin=False)
        self.assertFalse(g.op("imp_leggi").json["ok"])
        self.admin.ok("imp_utente", id=h.id, elimina=True)
        self.assertTrue(h.aspetta(lambda e: e.get("t") == "esci"))
        self.assertEqual(h.get("/api/io?" + h.qs()).status, 401)

    def test_nomina_master(self):
        g, h = self.giocatore(), self.giocatore()
        try:
            self.admin.ok("nomina_master", id=g.id)
            self.assertTrue(g.aspetta(lambda e: e.get("t") == "ruolo" and e["ruolo"] == "master"))
            self.admin.ok("nomina_master", id=h.id)
            self.assertTrue(g.aspetta(lambda e: e.get("t") == "ruolo" and e["ruolo"] == "giocatore"))
            self.assertEqual(g.get("/api/io?" + g.qs()).json["ruolo"], "giocatore")
            self.assertFalse(g.get("/api/io?" + g.qs()).json["master"])
            self.assertEqual(self.admin.get("/api/io?" + self.admin.qs()).json["ruolo"], "giocatore")
            self.admin.ok("nomina_master", id=h.id, master=False)
            self.assertEqual(h.get("/api/io?" + h.qs()).json["ruolo"], "giocatore")
            self.assertFalse(self.admin.op("nomina_master", id="non-esiste").json["ok"])
        finally:
            self.admin.entra("master")

    def test_partite(self):
        self.admin.ok("chat", testo="salvami")
        r = self.admin.ok("imp_partite")
        p = next(x for x in r["partite"] if x["id"] == "prova")
        self.assertTrue(p["in_gioco"])
        for k in ("titolo", "aggiornata", "pedine", "tiri", "round"):
            self.assertIn(k, p)
        self.admin.ok("imp_partita_azzera", id="prova")
        self.assertEqual(self.admin.stato()["log"], [])


class TestPersistenza(unittest.TestCase):
    def test_riavvio(self):
        srv = Server()
        try:
            a = Client(srv)
            a.login_admin()
            a.entra("master")
            a.ok("sessione_apri", id="prova")
            a.ok("sessione_inizia")
            g = Client(srv)
            g.login_ospite("Legolas")
            g.entra("giocatore", "lia", colore="#00ff00")
            pid = a.ok("pedina_salva", pedina={"nome": "Tesoro", "x": 9, "y": 9})["id"]
            g.ok("chat", testo="prima del riavvio")
            a.ok("nebbia", azione="rivela", celle=["5,5"])
            srv.restart()
            info = g.get("/api/info").json
            self.assertEqual(info["sessione"], "chiusa")                       # al riavvio il tavolo è chiuso
            io_ = g.get("/api/io?" + g.qs())
            self.assertEqual(io_.status, 200)                                    # le credenziali restano valide
            self.assertEqual(io_.json["colore"], "#00ff00")
            self.assertEqual(a.get("/api/io?" + a.qs()).status, 200)
            a.ok("sessione_apri")                                                # riapre l'avventura ricordata
            st = a.stato()
            self.assertEqual(st["avventura"], "prova")
            self.assertIn(pid, st["pedine"])
            self.assertIn("prima del riavvio", [v.get("testo") for v in st["log"]])
            self.assertIn("5,5", st["nebbia"]["01_piazza"]["celle"])
            self.assertTrue(any(p.get("pg") == "lia" for p in st["pedine"].values()))
        finally:
            srv.chiudi()


if __name__ == "__main__":
    unittest.main()
