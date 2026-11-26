"""Matrice dei permessi: ogni comando provato con ogni ruolo.

Ruoli:
    G  giocatore seduto con il personaggio «rocco» (proprietario della sua pedina)
    P  altro giocatore senza personaggio (non proprietario di nulla)
    A  amministratore seduto come giocatore (non è il Master di questa partita)
    M  Master nominato dall'amministratore (non è admin)
Un comando permesso risponde ok:true; uno vietato risponde ok:false e NON cambia lo stato della partita.
"""
import unittest

from harness import PW_ADMIN, Base

TUTTI = "GPAM"
PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x10\x00\x00\x00\x10\x08\x02\x00\x00\x00\x90\x91h6"
       b"\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82")


class TestMatricePermessi(Base):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.M = cls.nuovo()
        cls.M.login_ospite("Gandalf")
        cls.M.entra()
        cls.M.collega()
        cls.admin.ok("nomina_master", id=cls.M.id)            # l'admin smette di essere Master
        cls.G = cls.giocatore("rocco", nome="Proprietario")
        cls.P = cls.giocatore(nome="Estraneo")
        cls.A = cls.admin
        cls.ruoli = {"G": cls.G, "P": cls.P, "A": cls.A, "M": cls.M}

    def fotografia(self):
        st = self.M.stato()
        return {k: st[k] for k in ("pedine", "iniziativa", "nebbia", "schede", "scena", "note_master", "sessione", "avv", "catalogo")}

    def prova(self, nome, payload, permessi, prima=None):
        for ruolo in "GPAM":            # il Master per ultimo: le operazioni distruttive avvengono dopo i rifiuti
            c = self.ruoli[ruolo]
            dati = payload(ruolo) if callable(payload) else payload
            if prima:
                dati = {**dati, **prima(ruolo)}
            foto = self.fotografia() if ruolo not in permessi else None
            r = c.op(nome, **dati)
            with self.subTest(op=nome, ruolo=ruolo, dati=dati):
                if ruolo in permessi:
                    self.assertEqual(r.status, 200, r)
                    self.assertTrue(r.json.get("ok"), r)
                else:
                    self.assertFalse(r.json.get("ok"), r)
                    self.assertEqual(self.fotografia(), foto, "un comando rifiutato ha cambiato lo stato")

    def test_matrice(self):
        rocco = self.pedina_pg("rocco")["id"]
        mostro = lambda _r: {"id": self.M.ok("pedina_salva", pedina={"nome": "Bersaglio", "x": 1, "y": 1})["id"]}
        voce = lambda _r: {"id": self.M.ok("iniziativa", azione="aggiungi", nome="Z", valore=1) and self.M.stato()["iniziativa"]["ordine"][0]["id"]}

        def mappa_nuova(_r):
            r = self.M.req("POST", "/api/carica_mappa?nome=tmp.png&" + self.M.qs(), raw=PNG)
            return {"id": r.json["id"]}

        casi = [
            ("tira", {"espr": "1d20"}, TUTTI),
            ("chat", {"testo": "ciao"}, TUTTI),
            ("ping", {"x": 1, "y": 2}, TUTTI),
            ("righello", {"punti": [{"x": 0, "y": 0}, {"x": 10, "y": 10}]}, TUTTI),
            ("righello", {"punti": None}, TUTTI),
            ("scegli_pg", lambda r: {"pg": "rocco" if r == "G" else None}, TUTTI),
            ("pedina_muovi", {"id": rocco, "x": 50, "y": 60, "finale": True}, "GM"),
            ("pedina_salva", {"pedina": {"id": rocco, "x": 70, "y": 80}}, "GM"),
            ("pedina_salva", {"pedina": {"nome": "Nuova", "x": 1, "y": 1}}, "M"),
            ("pedina_elimina", {}, "M", mostro),
            ("scheda", {"id": "rocco", "scheda": {"pf": 11}}, "GM"),
            ("scheda", {"id": "lia", "scheda": {"pf": 11}}, "M"),
            ("iniziativa", {"azione": "aggiungi", "nome": "Io", "valore": 5}, TUTTI),
            ("iniziativa", {"azione": "aggiungi", "nome": "Rocco", "valore": 5, "pedina": rocco}, "GM"),
            ("iniziativa", {"azione": "prossimo"}, "M"),
            ("iniziativa", {"azione": "precedente"}, "M"),
            ("iniziativa", {"azione": "valore", "valore": 3}, "M", voce),
            ("iniziativa", {"azione": "rimuovi"}, "M", voce),
            ("iniziativa", {"azione": "svuota"}, "M"),
            ("sessione_apri", {"id": "prova"}, "A"),
            ("nomina_master", lambda _r: {"id": self.M.id}, "A"),
            ("sessione_inizia", {}, "AM"),
            ("sessione_pausa", {}, "M"),
            ("sessione_chiudi", {}, "AM"),
            ("sessione_apri", {"id": "prova"}, "A"),
            ("imp_leggi", {}, "A"),
            ("imp_partite", {}, "A"),
            ("imp_salva", {"config": {"nome_tavolo": "Tavolo di prova"}}, "A"),
            ("imp_admin", {"attuale": PW_ADMIN}, "A"),
            ("imp_utente", lambda _r: {"id": self.P.id, "master": False}, "A"),
            ("imp_partita_azzera", {"id": "seconda"}, "A"),
            ("scena", {"id": "02_grotta", "porta_gruppo": False}, "M"),
            ("griglia", {"id": "02_grotta", "griglia": {"cella": 30, "ox": 0, "oy": 0, "mostra": True}}, "M"),
            ("nebbia", {"azione": "rivela", "celle": ["1,1"]}, "M"),
            ("nebbia", {"attiva": True}, "M"),
            ("note_master", {"testo": "segreto"}, "M"),
            ("pulisci_scena", {}, "M"),
            ("svuota_log", {}, "M"),
            ("avventura_attiva", {"id": "prova"}, "M"),
            ("avventura_nuova", {"titolo": "Creata nei test"}, "M"),
            ("avventura_info", {"descrizione": "nuova descrizione"}, "M"),
            ("mappa_meta", {"id": "02_grotta", "ordine": 2}, "M"),
            ("mappa_elimina", {}, "M", mappa_nuova),
            ("documento_elimina", {"file": "non-esiste.html"}, "M"),
            ("avventura_elimina", {}, "M", lambda _r: {"id": self.M.ok("avventura_nuova", titolo="Da eliminare")["id"]}),
            ("operazione_inventata", {}, ""),
            ("reset_partita", {}, "M"),
        ]
        for caso in casi:
            nome, payload, permessi = caso[:3]
            self.prova(nome, payload, permessi, caso[3] if len(caso) > 3 else None)

    def test_caricamenti_solo_master(self):
        for path in ("/api/carica_mappa?nome=x.png", "/api/carica_documento?nome=x.html", "/api/carica_avventura"):
            for ruolo in "GPA":
                c = self.ruoli[ruolo]
                r = c.req("POST", path + "&" + c.qs() if "?" in path else path + "?" + c.qs(), raw=PNG)
                self.assertEqual(r.status, 403, (path, ruolo))

    def test_scaricamenti(self):
        for path, chi in (("/api/scarica_avventura?id=prova", "M"), ("/api/esporta", "M"), ("/api/backup", "A")):
            for ruolo in "GPAM":
                c = self.ruoli[ruolo]
                r = c.get(path + ("&" if "?" in path else "?") + c.qs())
                self.assertEqual(r.status, 200 if ruolo in chi else 403, (path, ruolo))

    def test_importa_solo_master(self):
        for ruolo in "GPA":
            c = self.ruoli[ruolo]
            r = c.post("/api/importa", {"pedine": {}})
            self.assertNotEqual(r.status, 200)
            self.assertFalse(r.json["ok"])


if __name__ == "__main__":
    unittest.main()
