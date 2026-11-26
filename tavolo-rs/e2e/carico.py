"""Prova di carico: tanti giocatori collegati che trascinano, tirano e scrivono insieme.

    python3 carico.py                         # server Python
    python3 carico.py ../target/release/tavolo   # server Rust
    python3 carico.py <server> --giocatori 60 --secondi 30

Ogni giocatore ha lo stream SSE aperto e manda ~10 «righello» al secondo (come quando si trascina,
e ogni righello arriva a TUTTI) più chat, dadi e ping. Si misurano i tempi di risposta, gli errori,
gli eventi ricevuti e la memoria del server.
"""
import argparse
import http.client
import json
import os
import random
import statistics
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import Client, Server  # noqa: E402


def rss_mb(pid):
    try:
        with open(f"/proc/{pid}/status") as f:
            for r in f:
                if r.startswith("VmRSS:"):
                    return int(r.split()[1]) / 1024
    except OSError:
        pass
    return 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("server", nargs="?", default="python")
    ap.add_argument("--giocatori", type=int, default=40)
    ap.add_argument("--secondi", type=float, default=30)
    a = ap.parse_args()
    os.environ["TAVOLO_SERVER"] = a.server if a.server == "python" else os.path.realpath(a.server)
    srv = Server()
    master = Client(srv)
    master.login_admin()
    master.entra("master")
    master.ok("sessione_apri", id="prova")
    master.ok("sessione_inizia")
    master.collega()
    giocatori = []
    for i in range(a.giocatori):
        g = Client(srv)
        assert g.login_ospite(f"Carico{i}").json["ok"]
        g.entra("giocatore", ["rocco", "lia", "bruno"][i] if i < 3 else None)
        g.collega()
        giocatori.append(g)
    print(f"{a.giocatori} giocatori collegati a {os.environ['TAVOLO_SERVER']}; carico per {a.secondi:.0f} s…", flush=True)

    tempi, errori, stati = [], [], {}
    lock = threading.Lock()
    fine = time.time() + a.secondi
    picco_rss = [rss_mb(srv.proc.pid)]

    def gioca(g):
        conn = http.client.HTTPConnection("127.0.0.1", srv.porta, timeout=10)
        h = {"Content-Type": "application/json", "X-Client": g.id, "X-Secret": g.secret, "X-Forwarded-For": g.ip}
        n = 0
        while time.time() < fine:
            n += 1
            if n % 25 == 0:
                corpo = {"op": "tira", "espr": "1d20+5"}
            elif n % 40 == 0:
                corpo = {"op": "chat", "testo": f"ciao {n}"}
            elif n % 50 == 0:
                corpo = {"op": "ping", "x": random.random() * 600, "y": random.random() * 400}
            else:
                corpo = {"op": "righello", "punti": [{"x": 10, "y": 10}, {"x": random.random() * 600, "y": random.random() * 400}]}
            t0 = time.perf_counter()
            try:
                conn.request("POST", "/api/op", body=json.dumps(corpo), headers=h)
                r = conn.getresponse()
                r.read()
                dt = time.perf_counter() - t0
                with lock:
                    tempi.append(dt)
                    stati[r.status] = stati.get(r.status, 0) + 1
            except Exception as e:  # noqa: BLE001
                with lock:
                    errori.append(repr(e))
                conn.close()
                conn = http.client.HTTPConnection("127.0.0.1", srv.porta, timeout=10)
            time.sleep(max(0.0, 0.1 - (time.perf_counter() - t0)))     # ~10 al secondo

    def osserva():
        while time.time() < fine:
            picco_rss.append(rss_mb(srv.proc.pid))
            time.sleep(0.5)

    th = [threading.Thread(target=gioca, args=(g,)) for g in giocatori] + [threading.Thread(target=osserva)]
    for t in th:
        t.start()
    for t in th:
        t.join()
    time.sleep(1)
    eventi = [len(g.eventi) for g in giocatori]
    tempi.sort()
    q = lambda p: tempi[min(len(tempi) - 1, int(len(tempi) * p))] * 1000 if tempi else float("nan")  # noqa: E731
    print(json.dumps({
        "server": "python" if a.server == "python" else "rust",
        "giocatori": a.giocatori,
        "richieste": len(tempi),
        "richieste_al_secondo": round(len(tempi) / a.secondi),
        "codici": stati,
        "errori_di_rete": len(errori),
        "latenza_ms": {"p50": round(q(0.5), 2), "p95": round(q(0.95), 2), "p99": round(q(0.99), 2), "max": round(q(1.0), 2)},
        "eventi_ricevuti_per_giocatore": {"min": min(eventi), "media": round(statistics.mean(eventi))},
        "memoria_server_mb": {"picco": round(max(picco_rss), 1)},
    }, indent=1))
    for g in giocatori + [master]:
        g.scollega()
    srv.chiudi()
    if errori:
        print("primi errori:", errori[:3])


if __name__ == "__main__":
    main()
