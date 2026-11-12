#!/usr/bin/env python3
"""Compone i documenti del one-shot «La Tana di Vermiglia».

- 1_Manuale_del_Master.html   (da sorgenti/master.html)
- 2_Guida_del_Giocatore.html  (regole della campagna + ambientazione di Pietracalda)
- 3_Schede_dei_Personaggi.html (generate da dati/personaggi.json)
Il pacchetto per il Tavolo Virtuale si crea con tavolo/strumenti/crea_pacchetto.py.
"""
import html
import json
import os
import re
import shutil
import sys

QUI = os.path.dirname(os.path.abspath(__file__))
RADICE = os.path.dirname(QUI)
BRUMARIA = os.path.join(RADICE, "..", "brumaria")
sys.path.insert(0, os.path.join(BRUMARIA, "strumenti"))
from componi import CSS  # noqa: E402

ABILITA = {
    "Acrobazia": "DES", "Addestrare Animali": "SAG", "Arcano": "INT", "Atletica": "FOR", "Furtività": "DES",
    "Indagare": "INT", "Inganno": "CAR", "Intimidire": "CAR", "Intrattenere": "CAR", "Intuizione": "SAG",
    "Medicina": "SAG", "Natura": "INT", "Percezione": "SAG", "Persuasione": "CAR", "Rapidità di Mano": "DES",
    "Religione": "INT", "Storia": "INT", "Sopravvivenza": "SAG",
}
NOMI_CAR = {"FOR": "Forza", "DES": "Destrezza", "COS": "Costituzione", "INT": "Intelligenza", "SAG": "Saggezza", "CAR": "Carisma"}


def mod(v):
    return (v - 10) // 2


def sg(n):
    return f"+{n}" if n >= 0 else f"−{-n}"


def pagina(titolo, descr, corpo):
    return f"""<!doctype html>
<html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{titolo}</title><meta name="description" content="{descr}"><style>{CSS}</style></head>
<body>
{corpo}
</body></html>
"""


def scheda(p, prima):
    e = html.escape
    car = p["car"]
    righe_ts = ", ".join(f"{NOMI_CAR[k]} {sg(mod(v) + (p['comp'] if k in p['ts'] else 0))}" for k, v in car.items())
    tutte = []
    for nome, c in ABILITA.items():
        if nome in p["abilita"]:
            tutte.append(f'<span class="chip"><b>{nome} {sg(p["abilita"][nome])}</b></span>')
        else:
            tutte.append(f'<span class="chip">{nome} {sg(mod(car[c]) + p.get("factotum", 0))}</span>')
    pp = 10 + p["abilita"].get("Percezione", mod(car["SAG"]))
    att = "".join(
        f"<tr><td>{e(a['nome'])}</td><td>{sg(a['bonus']) if a['bonus'] is not None else '—'}</td><td>{e(a['danni'])} {e(a['tipo'])}</td><td>{e(a['note'])}</td></tr>"
        for a in p["attacchi"])
    cap = "".join(f"<li><b>{e(c['nome'])}.</b> {e(c['testo'])}</li>" for c in p["capacita"])
    mag = ""
    if p.get("magia"):
        m = p["magia"]
        slot = " · ".join(f"{k}° livello: " + " ".join(["☐"] * n) for k, n in m["slot"].items())
        inc = "".join(
            f"<li><b>{e(i['nome'])}</b> <small>({'trucchetto' if i['liv'] == 0 else str(i['liv']) + '° liv.'})</small>: {e(i['testo'])}</li>"
            for i in m["incantesimi"])
        mag = f"""<h4>Magia · CD {m['cd']} · attacco con incantesimi {sg(m['att'])}</h4>
<p><b>Slot:</b> {slot} <small>(si recuperano con il riposo lungo)</small>{(' · ' + e(m['nota'])) if m.get('nota') else ''}</p><ul>{inc}</ul>"""
    ca = f"<b>{p['ca']}</b>" + (f"<small>{e(p['ca_note'])}</small>" if p.get("ca_note") else "")
    return f"""<div class="scheda{' prima' if prima else ''}">
<div class="intest"><div><div class="nome">{p['icona']} {e(p['nome'])}</div><div class="cl">{e(p['razza'])} · {e(p['classe'])} · {e(p['background'])}</div></div><div><b>Livello {p['livello']}</b><br><small>{e(p['sottotitolo'])}</small></div></div>
<p><b>Chi sono.</b> {e(p['chi'])}</p>
<p><b>Personalità.</b> {e(p['personalita'])}</p>
<p><b>Perché sono alla locanda.</b> {e(p['perche'])}</p>
<p><b>Legame</b> (presentazioni): <i>«{e(p['legame'])}»</i></p>
<div class="big"><div><small>CA</small>{ca}</div><div><small>Punti Ferita</small><b>{p['pf']}</b></div><div><small>Velocità</small><b>{e(p['vel'])}</b></div><div><small>Iniziativa</small><b>{sg(p['iniz'])}</b></div><div><small>Dadi Vita</small><b>{p['dadivita']}</b></div></div>
<table><tr>{''.join(f'<th>{k}</th>' for k in car)}</tr><tr>{''.join(f'<td>{v} (<b>{sg(mod(v))}</b>)</td>' for v in car.values())}</tr>
<tr><td colspan="6"><b>Tiri salvezza:</b> {righe_ts}</td></tr></table>
<p><b>Abilità</b> (in grassetto quelle in cui sei addestrato): {''.join(tutte)}{(' <span class="chip"><b>' + e(p['extra']) + '</b></span>') if p.get('extra') else ''} · Percezione passiva {pp}.</p>
{('<p><b>Sensi e tratti:</b> ' + e(p['sensi']) + '</p>') if p.get('sensi') else ''}
<table><tr><th>Attacco</th><th>Per colpire</th><th>Danni</th><th>Note</th></tr>{att}</table>
<h4>Cosa so fare</h4><ul>{cap}</ul>
{mag}
<p><b>Equipaggiamento:</b> {e(p['equip'])}</p>
<p><b>Come giocarlo:</b> {e(p['consiglio'])}</p>
<p><b>PF attuali:</b> ______ &nbsp; <b>Note:</b> ____________________________________________</p>
</div>"""


def main():
    # manuale
    with open(os.path.join(QUI, "sorgenti", "master.html"), encoding="utf-8") as f:
        corpo = f.read()
    with open(os.path.join(RADICE, "1_Manuale_del_Master.html"), "w", encoding="utf-8") as f:
        f.write(pagina("La Tana di Vermiglia · Master", "One-shot di draghi per D&D 5e, per principianti.", corpo))

    # guida del giocatore: riusa le regole e sostituisce l'ambientazione
    with open(os.path.join(BRUMARIA, "strumenti", "sorgenti", "giocatore.html"), encoding="utf-8") as f:
        g = f.read()
    g = g.replace("<h1>Le Campane di Brumaria</h1>", "<h1>La Tana di Vermiglia</h1>")
    g = g.replace("Ascoltate bene… quando suonano le campane.", "")
    g = g.replace("<i>Benvenuti a Brumaria. </i>", "<i>Benvenuti a Pietracalda. Occhio al cielo.</i>")
    mondo = """<h2>9. Il mondo: Pietracalda e il Monte Fumo</h2>
<p><b>Pietracalda</b> è un villaggio di pastori e minatori ai piedi del <b>Monte Fumo</b>, un vecchio vulcano che dormiva da cent'anni. Dentro la montagna c'è la <b>Forgia di Durnkar</b>, l'antica officina dei nani, abbandonata quando la lava si risvegliò.</p>
<p>Da tre settimane il Monte Fumo fuma di nuovo. I pastori dicono che le pecore spariscono di notte, che si trovano piccole impronte artigliate nel fango, e che un'<b>ombra alata, rossa come il vino</b>, è stata vista girare attorno alla cima.</p>
<p>Stasera siete tutti alla locanda <b>«Il Boccale Bruciato»</b>, per motivi diversi (li trovate sulla vostra scheda). Il fuoco scoppietta, lo stufato è caldo… e fuori, il cielo sopra la montagna è rosso come una brace.</p>
<h4>Chi conoscete già</h4>
<ul><li><b>Bertoldo</b>: l'oste, grasso e gentile, racconta storie di nani.</li>
<li><b>Nonno Gualtiero</b>: il fabbro del villaggio, burbero e fortissimo.</li>
<li><b>Tilde</b>: sua nipote, dieci anni, trecce rosse, vende castagne e sembra sempre nascondere qualcosa.</li></ul>
<figure class="mappa"><img src="../../asset/mappe/vermiglia/01_piazza_di_pietracalda.svg" alt="Piazza di Pietracalda"><figcaption>La piazza di Pietracalda</figcaption></figure>
"""
    g = re.sub(r"<h2>9\. Il mondo.*?(?=<h2>10\.)", mondo, g, flags=re.S)
    with open(os.path.join(RADICE, "2_Guida_del_Giocatore.html"), "w", encoding="utf-8") as f:
        f.write(pagina("La Tana di Vermiglia · Giocatori", "Regole semplici e ambientazione per chi gioca la prima volta.", g))

    # schede
    with open(os.path.join(QUI, "dati", "personaggi.json"), encoding="utf-8") as f:
        pg = json.load(f)
    corpo = """<div class="copertina"><h1>La Tana di Vermiglia</h1><div class="sotto">Schede dei Personaggi · 3° livello</div>
<div class="info">Cinque eroi pronti da giocare.<br>Cambia pure nome, aspetto e genere del tuo personaggio.</div></div>
<div class="nota"><b>Come leggere la scheda.</b> I numeri con il «+» si aggiungono al d20. <b>CA</b> = quanto è difficile colpirti. <b>PF</b> = Punti Ferita. Tieni il conto di PF e slot a matita!</div>
""" + "\n".join(scheda(p, i == 0) for i, p in enumerate(pg))
    with open(os.path.join(RADICE, "3_Schede_dei_Personaggi.html"), "w", encoding="utf-8") as f:
        f.write(pagina("La Tana di Vermiglia · Schede", "Cinque personaggi di 3° livello pronti da giocare.", corpo))
    print("ok documenti one-shot")

    print("Pacchetto per il tavolo: python3 tavolo/strumenti/crea_pacchetto.py avventure/vermiglia")

if __name__ == "__main__":
    main()
