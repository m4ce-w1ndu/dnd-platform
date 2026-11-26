"""Migrazione: un database scritto dal server Python viene aperto dal server Rust senza perdite.

Si esegue solo con il server Rust (TAVOLO_SERVER=<binario>): prima gira il server Python sui dati,
poi il binario Rust (`verifica-db` e poi il server vero) sulla stessa cartella.
"""
import os
import subprocess
import unittest

from harness import PW_ADMIN, Client, Server, solo_rust


class TestMigrazione(unittest.TestCase):
    @solo_rust
    def test_dal_python_al_rust(self):
        rust = os.environ["TAVOLO_SERVER"]
        os.environ["TAVOLO_SERVER"] = "python"
        srv = Server()
        try:
            a = Client(srv)
            a.login_admin()
            a.entra("master")
            a.ok("sessione_apri", id="prova")
            g = Client(srv)
            g.login_ospite("Legolas")
            g.entra("giocatore", "lia", colore="#00ff00")
            pid = a.ok("pedina_salva", pedina={"nome": "Tesoro", "x": 9.5, "y": 9, "pf": 7, "pfmax": 7, "ca": "15 (scudo)"})["id"]
            g.ok("tira", espr="2d20kh1+3", segreto=True)
            g.ok("scheda", id="lia", scheda={"pf": 20, "note": "àèìòù 🐉", "usi": {"Seconda Ventata": [True, False]}})
            a.ok("nebbia", azione="rivela", celle=["1,1", "2,3"])
            a.ok("iniziativa", azione="aggiungi", nome="Goblin", valore=14)
            a.ok("imp_salva", config={"nome_tavolo": "Tavolo di casa", "password_giocatori": ""})
            capo = Client(srv)                                # un giocatore a cui l'admin dà i permessi di admin
            capo.login_ospite("Gestore")
            a.ok("imp_utente", id=capo.id, admin=True)
            srv.stop()                                  # SIGTERM: il Python salva

            r = subprocess.run([rust, "verifica-db", os.path.join(srv.dati, "tavolo.db")], capture_output=True, text=True, timeout=60)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("nessuna perdita", r.stdout)

            os.environ["TAVOLO_SERVER"] = rust
            srv.start()                                  # stessa cartella dati, ora col server Rust
            self.assertEqual(g.get("/api/io?" + g.qs()).json["colore"], "#00ff00")   # credenziali di prima valide
            self.assertEqual(g.get("/api/info").json["nome_tavolo"], "Tavolo di casa")
            a2 = Client(srv)
            self.assertTrue(a2.login_admin(PW_ADMIN).json["ok"])            # password PBKDF2 del Python → Argon2
            self.assertEqual(Client(srv).login_admin("sbagliata").status, 403)
            # il vecchio utente «Admin» del Python ora è l'account di sistema: configura ma non apre il tavolo
            io_a = a.get("/api/io?" + a.qs()).json
            self.assertTrue(io_a["sistema"])
            self.assertFalse(a.op("sessione_apri").json["ok"])
            self.assertEqual(a2.id, a.id)                    # e il nuovo accesso con password è lo stesso utente
            capo.entra("master")
            capo.ok("sessione_apri")
            st = capo.stato()
            self.assertEqual(st["pedine"][pid]["ca"], "15 (scudo)")
            self.assertEqual(st["pedine"][pid]["x"], 9.5)
            self.assertEqual(st["schede"]["lia"]["note"], "àèìòù 🐉")
            self.assertEqual(st["schede"]["lia"]["usi"], {"Seconda Ventata": [True, False]})
            self.assertEqual(st["nebbia"]["01_piazza"]["celle"], ["1,1", "2,3"])
            self.assertEqual(st["iniziativa"]["ordine"][0]["nome"], "Goblin")
            self.assertTrue(any(v.get("segreto") for v in st["log"]))
            srv.stop()

            # ritorno al Python (piano B): deve ripartire e accettare la stessa password admin
            os.environ["TAVOLO_SERVER"] = "python"
            srv.start()
            self.assertTrue(Client(srv).login_admin(PW_ADMIN).json["ok"])
            self.assertEqual(g.get("/api/io?" + g.qs()).status, 200)
            capo.ok("sessione_apri")
            self.assertIn(pid, capo.stato()["pedine"])
        finally:
            os.environ["TAVOLO_SERVER"] = rust
            srv.chiudi()


if __name__ == "__main__":
    unittest.main()
