"""Gioco: dadi, chat, pedine, schede, iniziativa, nebbia, mappe e visibilità per ruolo."""
import re
import unittest

from harness import Base, rust, solo_rust


class TestDadi(Base):
    def test_espressioni(self):
        g = self.giocatore()
        for espr, lo, hi in (("1d20", 1, 20), ("2d6+3", 5, 15), ("d%", 1, 100), ("2d20kh1+5", 6, 25), ("2d20kl1", 1, 20),
                             ("1d8 + 3 + 1d6", 5, 17), ("10", 10, 10), ("-1d4", -4, -1), ("3d6-2", 1, 16)):
            t = g.ok("tira", espr=espr)["tiro"]
            self.assertTrue(lo <= t["totale"] <= hi, (espr, t))
            self.assertEqual(t["espr"], espr.strip())
            for k in ("parti", "critico", "fallimento", "id", "ora", "da", "chi", "colore", "tipo"):
                self.assertIn(k, t)
        t = g.ok("tira", espr="2d20kh1")["tiro"]
        dadi = t["parti"][0]
        self.assertEqual(len(dadi["valori"]), 2)
        self.assertEqual(len(dadi["tenuti"]), 1)
        self.assertEqual(t["totale"], max(dadi["valori"]))

    def test_espressioni_non_valide(self):
        g = self.giocatore()
        for espr in ("", "ciao", "1d1", "101d6", "1d1001", "1d20+", "d", "2d6 3d6x", "x" * 121, "50d6+50d6+50d6+51d6"):
            r = g.op("tira", espr=espr)
            self.assertEqual(r.status, 400, espr)
            self.assertFalse(r.json["ok"])

    def test_danni_raddoppiati_sul_critico(self):
        g = self.giocatore()
        for _ in range(200):
            t = g.ok("tira", espr="4d20kh1", danni="1d6+2")["tiro"]
            if t["critico"]:
                self.assertEqual(t["danni"]["parti"][0]["n"], 2)
                break
            self.assertEqual(t["danni"]["parti"][0]["n"], 1)
        else:
            self.fail("nessun 20 naturale in 200 tiri")

    def test_tiro_segreto(self):
        g, altro = self.giocatore(), self.giocatore()
        self.admin.collega()
        try:
            t = g.ok("tira", espr="1d20", segreto=True, etichetta="Furtività")["tiro"]
            self.assertTrue(self.admin.aspetta(lambda e: e.get("t") == "log" and e["voce"]["id"] == t["id"]))
            self.assertTrue(g.aspetta(lambda e: e.get("t") == "log" and e["voce"]["id"] == t["id"]))
            self.assertIsNone(altro.aspetta(lambda e: e.get("t") == "log" and e["voce"]["id"] == t["id"], 1))
            self.assertNotIn(t["id"], [v["id"] for v in altro.stato()["log"]])
            self.assertIn(t["id"], [v["id"] for v in g.stato()["log"]])
            self.assertIn(t["id"], [v["id"] for v in self.admin.stato()["log"]])
        finally:
            self.admin.scollega()


class TestChat(Base):
    def test_chat(self):
        g = self.giocatore()
        self.assertFalse(g.op("chat", testo="   ").json["ok"])
        g.ok("chat", testo="x" * 1000)
        voce = g.stato()["log"][-1]
        self.assertEqual(voce["tipo"], "chat")
        self.assertEqual(len(voce["testo"]), 600)

    def test_log_limitato(self):
        i = 0
        while i < 410:                    # tanti giocatori, ognuno sotto il proprio limite di frequenza
            g = self.giocatore(collega=False)
            for _ in range(14):
                if i < 410:
                    g.ok("chat", testo=f"m{i}")
                    i += 1
        log = self.admin.stato()["log"]
        self.assertLessEqual(len(log), 400)
        self.assertEqual(log[-1]["testo"], "m409")


class TestPedine(Base):
    def test_master_crea_giocatore_no(self):
        g = self.giocatore()
        r = g.op("pedina_salva", pedina={"nome": "<img src=x onerror=alert(1)>", "x": 1, "y": 1})
        self.assertFalse(r.json["ok"])
        self.assertNotIn("<img", str(self.admin.stato()["pedine"]))
        pid = self.admin.ok("pedina_salva", pedina={"nome": "Goblin" * 20, "x": 10, "y": 20, "taglia": 99, "condizioni": ["x" * 50] * 30, "nascosta": False})["id"]
        p = self.admin.stato()["pedine"][pid]
        self.assertEqual(len(p["nome"]), 40)
        self.assertEqual(p["taglia"], 6)
        self.assertEqual(len(p["condizioni"]), 12)
        self.assertEqual(len(p["condizioni"][0]), 20)
        self.assertEqual(p["scena"], self.admin.stato()["scena"])

    def test_muovere(self):
        g, altro = self.giocatore("rocco"), self.giocatore()
        p = self.pedina_pg("rocco")
        g.ok("pedina_muovi", id=p["id"], x=100, y=200, finale=True)
        p = self.pedina_pg("rocco")
        self.assertEqual((p["x"], p["y"]), (100, 200))
        self.assertFalse(altro.op("pedina_muovi", id=p["id"], x=1, y=1).json["ok"])
        self.assertFalse(altro.op("pedina_muovi", id="non-esiste", x=1, y=1).json["ok"])
        self.assertEqual(g.op("pedina_muovi", id=p["id"], x="abc", y=1).status, 400)
        self.admin.ok("pedina_muovi", id=p["id"], x=5, y=6)
        self.assertEqual(self.pedina_pg("rocco")["x"], 5)

    def test_giocatore_modifica_solo_posizione_pf_condizioni(self):
        g = self.giocatore("lia")
        p = self.pedina_pg("lia")
        g.ok("pedina_salva", pedina={**p, "nome": "Hackerata", "icona": "💀", "pf": 999, "pfmax": 999, "condizioni": ["Prono"], "x": 7, "nascosta": True})
        q = self.pedina_pg("lia")
        self.assertEqual(q["nome"], p["nome"])
        self.assertEqual(q["icona"], p["icona"])
        self.assertEqual(q["pfmax"], 22)
        self.assertEqual(q["pf"], 22)            # limitati ai PF massimi
        self.assertEqual(q["condizioni"], ["Prono"])
        self.assertEqual(q["x"], 7)
        self.assertFalse(q.get("nascosta"))
        g.ok("pedina_salva", pedina={"id": p["id"], "pf": -5})
        self.assertEqual(self.pedina_pg("lia")["pf"], 0)
        self.assertEqual(self.admin.stato()["schede"]["lia"]["pf"], 0)   # la scheda segue la pedina

    def test_eliminare(self):
        g = self.giocatore("bruno")
        mostro = self.admin.ok("pedina_salva", pedina={"nome": "Orco", "x": 1, "y": 1})["id"]
        self.admin.ok("iniziativa", azione="aggiungi", nome="Orco", valore=12, pedina=mostro)
        self.assertFalse(g.op("pedina_elimina", id=mostro).json["ok"])
        self.admin.ok("pedina_elimina", id=mostro)
        st = self.admin.stato()
        self.assertNotIn(mostro, st["pedine"])
        self.assertNotIn(mostro, [x.get("pedina") for x in st["iniziativa"]["ordine"]])
        mia = self.pedina_pg("bruno")["id"]
        g.ok("pedina_elimina", id=mia)                # la propria sì
        self.assertNotIn(mia, self.admin.stato()["pedine"])

    def test_pedina_nascosta(self):
        g = self.giocatore()
        pid = self.admin.ok("pedina_salva", pedina={"nome": "Assassino", "x": 1, "y": 1, "nascosta": True})["id"]
        self.assertNotIn(pid, g.stato()["pedine"])
        self.assertIn(pid, self.admin.stato()["pedine"])
        self.admin.ok("pedina_muovi", id=pid, x=3, y=3)
        ev = g.aspetta(lambda e: e.get("id") == pid or e.get("pedina", {}).get("id") == pid)
        self.assertEqual(ev, {"t": "pedina_via", "id": pid})
        g.svuota()
        p = self.admin.stato()["pedine"][pid]
        self.admin.ok("pedina_salva", pedina={**p, "nascosta": False})
        ev = g.aspetta(lambda e: e.get("t") == "pedina" and e["pedina"]["id"] == pid)
        self.assertEqual(ev["pedina"]["nome"], "Assassino")


class TestSchede(Base):
    def test_scheda(self):
        g, altro = self.giocatore("rocco"), self.giocatore()
        g.ok("scheda", id="rocco", scheda={"pf": 20, "note": "n" * 6000, "usi": {"a": 1}, "ignoto": 1})
        sch = self.admin.stato()["schede"]["rocco"]
        self.assertEqual(sch["pf"], 20)
        self.assertEqual(len(sch["note"]), 5000)
        self.assertNotIn("ignoto", sch)
        self.assertEqual(self.pedina_pg("rocco")["pf"], 20)
        self.assertFalse(altro.op("scheda", id="rocco", scheda={"pf": 1}).json["ok"])
        self.admin.ok("scheda", id="rocco", scheda={"pf": 3})
        self.assertEqual(self.pedina_pg("rocco")["pf"], 3)


class TestIniziativa(Base):
    def test_giocatore(self):
        g, altro = self.giocatore("lia"), self.giocatore()
        mia = self.pedina_pg("lia")["id"]
        g.ok("iniziativa", azione="aggiungi", nome="Lia", valore=15, pedina=mia, nascosta=True, colore="url(javascript:x)")
        voce = next(x for x in self.admin.stato()["iniziativa"]["ordine"] if x.get("pedina") == mia)
        self.assertFalse(voce["nascosta"])
        self.assertTrue(re.match(r"^#[0-9a-fA-F]{3,8}$", voce["colore"]))
        self.assertEqual(voce["da"], g.id)
        r = altro.op("iniziativa", azione="aggiungi", nome="Furbo", valore=30, pedina=mia)
        self.assertFalse(r.json["ok"])
        altro.ok("iniziativa", azione="aggiungi", nome="Io", valore=3)
        g.ok("iniziativa", azione="aggiungi", nome="Lia", valore=18, pedina=mia)   # rimpiazza la propria voce
        ordine = self.admin.stato()["iniziativa"]["ordine"]
        self.assertEqual(sum(1 for x in ordine if x.get("pedina") == mia), 1)
        for azione in ("prossimo", "precedente", "rimuovi", "valore", "svuota"):
            self.assertFalse(g.op("iniziativa", azione=azione, id=ordine[0]["id"], valore=1).json["ok"], azione)

    def test_master(self):
        self.admin.ok("iniziativa", azione="svuota")
        for nome, v in (("A", 10), ("B", 20), ("C", 15)):
            self.admin.ok("iniziativa", azione="aggiungi", nome=nome, valore=v)
        ini = self.admin.stato()["iniziativa"]
        self.assertEqual([x["nome"] for x in ini["ordine"]], ["B", "C", "A"])
        self.admin.collega()
        try:
            for _ in range(3):
                self.admin.ok("iniziativa", azione="prossimo")
            ini = self.admin.stato()["iniziativa"]
            self.assertEqual((ini["turno"], ini["round"]), (0, 2))
            self.assertTrue(self.admin.aspetta(lambda e: e.get("t") == "log" and "Round 2" in e["voce"].get("testo", "")))
        finally:
            self.admin.scollega()
        self.admin.ok("iniziativa", azione="precedente")
        ini = self.admin.stato()["iniziativa"]
        self.assertEqual((ini["turno"], ini["round"]), (2, 1))
        a = next(x for x in ini["ordine"] if x["nome"] == "A")
        self.admin.ok("iniziativa", azione="valore", id=a["id"], valore=99)
        self.assertEqual(self.admin.stato()["iniziativa"]["ordine"][0]["nome"], "A")
        self.admin.ok("iniziativa", azione="rimuovi", id=a["id"])
        self.assertEqual(len(self.admin.stato()["iniziativa"]["ordine"]), 2)
        self.admin.ok("iniziativa", azione="svuota")
        self.assertEqual(self.admin.stato()["iniziativa"], {"ordine": [], "turno": 0, "round": 1})


class TestMappaENebbia(Base):
    def test_nebbia(self):
        g = self.giocatore()
        sc = self.admin.stato()["scena"]
        self.admin.ok("nebbia", attiva=True)
        self.admin.ok("nebbia", azione="rivela", celle=["1,1", "2,2", "3,3"])
        self.admin.ok("nebbia", azione="copri", celle=["2,2"])
        nb = g.stato()["nebbia"][sc]
        self.assertEqual(nb, {"attiva": True, "celle": ["1,1", "3,3"]})
        self.assertFalse(g.op("nebbia", azione="rivela", celle=["9,9"]).json["ok"])
        self.admin.ok("nebbia", azione="copri_tutto")
        self.assertEqual(self.admin.stato()["nebbia"][sc]["celle"], [])

    def test_scena_porta_il_gruppo(self):
        g = self.giocatore("rocco")
        mostro = self.admin.ok("pedina_salva", pedina={"nome": "Lupo", "x": 1, "y": 1, "scena": "01_piazza"})["id"]
        self.admin.ok("scena", id="02_grotta", porta_gruppo=True)
        st = g.stato()
        self.assertEqual(st["scena"], "02_grotta")
        p = self.pedina_pg("rocco")
        self.assertEqual((p["scena"], p["x"], p["y"]), ("02_grotta", None, None))
        self.assertEqual(st["pedine"][mostro]["scena"], "01_piazza")
        self.assertFalse(g.op("scena", id="01_piazza").json["ok"])
        self.admin.ok("pulisci_scena", scena="01_piazza")
        self.assertNotIn(mostro, self.admin.stato()["pedine"])
        self.assertIn(p["id"], self.admin.stato()["pedine"])
        self.admin.ok("scena", id="01_piazza", porta_gruppo=False)

    def test_griglia_e_meta_mappa(self):
        self.admin.ok("griglia", id="02_grotta", griglia={"cella": 40, "ox": 2, "oy": 3, "mostra": True})
        self.admin.ok("mappa_meta", id="02_grotta", titolo="Grotta buia", ordine=7, note_master="trappola")
        m = next(s for s in self.admin.stato()["avv"]["mappe"] if s["id"] == "02_grotta")
        self.assertEqual(m["griglia"], {"cella": 40.0, "ox": 2.0, "oy": 3.0, "mostra": True})
        self.assertEqual((m["titolo"], m["ordine"], m["note_master"]), ("Grotta buia", 7, "trappola"))
        self.assertFalse(self.admin.op("mappa_meta", id="non-esiste", titolo="x").json.get("ok"))

    def test_note_master_e_log(self):
        g = self.giocatore()
        self.admin.ok("note_master", testo="Il drago è il sindaco")
        self.assertEqual(self.admin.stato()["note_master"], "Il drago è il sindaco")
        self.assertEqual(g.stato()["note_master"], "")
        g.ok("chat", testo="ciao")
        self.admin.ok("svuota_log")
        self.assertEqual(self.admin.stato()["log"], [])


class TestVisibilita(Base):
    def test_stato_per_ruolo(self):
        g = self.giocatore()
        sg, sm = g.stato(), self.admin.stato()
        for k in ("versione", "avventura", "scena", "nebbia", "pedine", "log", "iniziativa", "schede", "note_master",
                  "online", "io", "avv", "sessione"):
            self.assertIn(k, sg)
        self.assertNotIn("catalogo", sg)
        self.assertIn("catalogo", sm)
        self.assertEqual(sm["attiva"], "prova")
        self.assertEqual([m["id"] for m in sg["avv"]["mostri"]], ["cane"])
        self.assertEqual(len(sm["avv"]["mostri"]), 2)
        self.assertEqual([d["file"] for d in sg["avv"]["documenti"]], ["guida.html", "mappa.pdf"])
        self.assertNotIn("SEGRETO-MAPPA", str(sg))
        self.assertIn("SEGRETO-MAPPA", str(sm))
        self.assertEqual(sg["io"]["id"], g.id)
        self.assertEqual(sg["io"]["role"], "giocatore")
        self.assertFalse(sg["io"]["admin"])
        self.assertEqual([m["id"] for m in sm["avv"]["mappe"]], ["01_piazza", "02_grotta", "03_bosco"])
        bosco = sm["avv"]["mappe"][2]
        self.assertEqual((bosco["larghezza"], bosco["altezza"]), (300, 200))
        self.assertEqual(sm["avv"]["mappe"][1]["larghezza"], 800)
        self.assertEqual(sm["avv"]["mappe"][0]["file"], "avventure/prova/mappe/01_piazza.svg")

    def test_online_e_doppia_connessione(self):
        g = self.giocatore(nome="Unico")
        self.assertIn(g.id, [o["id"] for o in g.stato()["online"]])
        secondo = type(g)(self.srv)
        secondo.id, secondo.secret, secondo.ip = g.id, g.secret, g.ip
        secondo.collega()
        g.svuota()
        secondo.ok("chat", testo="ancora qui")
        self.assertTrue(secondo.aspetta(lambda e: e.get("t") == "log"))
        if rust():
            # due schede dello stesso utente restano collegate insieme (niente scollegamenti a ripetizione)
            self.assertTrue(g.aspetta(lambda e: e.get("t") == "log", 3))
        else:
            self.assertIsNone(g.aspetta(lambda e: e.get("t") == "log", 1))   # Python: la vecchia scheda resta muta
        secondo.scollega()

    def test_eventi_senza_credenziali(self):
        c = self.nuovo()
        self.assertEqual(c.get("/api/eventi").status, 401)
        self.assertEqual(c.get("/api/stato").status, 401)
        self.assertEqual(c.post("/api/op", {"op": "chat", "testo": "x"}).status, 401)


class TestLimiti(Base):
    def test_troppe_azioni(self):
        g = self.giocatore()
        stati = [g.op("chat", riprova=False, testo="spam").status for _ in range(30)]
        self.assertIn(429, stati)
        self.assertEqual(stati[0], 200)
        trascina = self.giocatore("rocco")
        pid = self.pedina_pg("rocco")["id"]
        stati = [trascina.op("pedina_muovi", riprova=False, id=pid, x=i, y=i).status for i in range(25)]
        self.assertNotIn(429, stati)                      # i trascinamenti hanno un limite più largo

    def test_operazione_sconosciuta(self):
        g = self.giocatore()
        for corpo in ({"op": "boh"}, {}, {"op": None}):
            r = g.post("/api/op", corpo)
            self.assertIn(r.status, (200, 400))
            self.assertFalse(r.json["ok"])
        self.assertFalse(self.admin.op("boh").json["ok"])
        self.assertEqual(g.req("POST", "/api/op", raw=b"[1,2").status, 400)
        self.assertEqual(g.post("/api/nonesiste", {}).status, 404)

    @solo_rust
    def test_corpi_strani(self):
        """Il server Python qui chiude la connessione senza rispondere (eccezione non gestita)."""
        g = self.giocatore()
        for raw in (b'{"op": 5}', b"[1]", b'"ciao"', b'{"op": "chat", "testo": {"a": 1}}', b'{"op": "pedina_muovi", "id": [1]}'):
            r = g.req("POST", "/api/op", raw=raw)
            self.assertIn(r.status, (200, 400), raw)
            self.assertFalse(r.json["ok"], raw)


if __name__ == "__main__":
    unittest.main()
