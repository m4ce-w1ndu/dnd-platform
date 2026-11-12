#!/usr/bin/env python3
"""Mappe originali per «Pericolo a Pinebrook» (l'avventura ufficiale non ha mappe di gioco).

Riusa il motore di disegno della campagna. Scrive in asset/mappe/pinebrook/ le immagini SVG (+ PNG) e i .json
del formato unificato del Tavolo Virtuale (titolo, griglia, punto di partenza, note del Master).
"""
import json
import math
import os
import random
import sys

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(QUI, "..", "..", "brumaria", "strumenti"))
from genera_mappe import Map, C, INK, FLOOR, WOOD, FONT, smooth_path, blob_pts  # noqa: E402

OUT = os.path.join(QUI, "..", "..", "..", "asset", "mappe", "pinebrook")
# mappe sostituite da quelle di Calos Pro Maps: restano disponibili come alternativa
ALTERNATIVE = {"02_ingresso_della_caverna", "03_i_tunnel_della_tana", "04_la_caverna_delle_uova"}
ICE = "#cfe8f3"
ICE_D = "#7fb6d2"
SNOW = "#eef3f6"
ROCCIA = "#8f979c"
G = {"cella": C, "ox": 40, "oy": 92}


def ghiaccioli(m, x, y, w, h, seed, n=12):
    rnd = random.Random(seed)
    for _ in range(n):
        px, py = (x + rnd.random() * w) * C, (y + rnd.random() * h) * C
        s = rnd.uniform(5, 10)
        a = rnd.uniform(0, 6.28)
        pts = [(px + s * math.cos(a), py + s * math.sin(a)), (px + s * 0.35 * math.cos(a + 2.2), py + s * 0.35 * math.sin(a + 2.2)),
               (px + s * 0.35 * math.cos(a - 2.2), py + s * 0.35 * math.sin(a - 2.2))]
        m.post.append('<polygon points="' + " ".join(f"{a_:.1f},{b_:.1f}" for a_, b_ in pts) + f'" fill="#e9f6fc" stroke="{ICE_D}" stroke-width="1.2"/>')


def impronta(m, x, y, ang):
    X, Y = x * C, y * C
    m.post.append(f'<g transform="translate({X:.0f},{Y:.0f}) rotate({ang})" opacity=".85"><ellipse rx="7" ry="11" fill="#dff1fa" stroke="{ICE_D}" stroke-width="1.2"/>'
                  + "".join(f'<circle cx="{dx}" cy="-14" r="2.6" fill="#dff1fa" stroke="{ICE_D}"/>' for dx in (-6, -2, 2, 6)) + "</g>")


def mappa_sentiero():
    m = Map("01_sentiero_nel_bosco", 30, 20, "Il sentiero nel bosco", "Inizio e Incontro 1 · un drago non così temibile", outdoor=True, base="#b7c48c")
    rnd = random.Random(1)
    for i in range(16):
        m.terr_blob(rnd.uniform(0, 30), rnd.uniform(0, 20), rnd.uniform(1.5, 3), rnd.uniform(1, 2), 10 + i, "#a7b67d", 0.3)
    sent = [(-1, 17.5), (4, 16), (9, 13.5), (13, 11.5), (17, 10.5), (21, 8), (25, 5), (31, 2)]
    m.terr(f'<path d="{smooth_path([(x*C, y*C) for x, y in sent], closed=False)}" stroke="#c9b48a" stroke-width="{2.4*C}" fill="none" stroke-linecap="round"/>')
    m.terr(f'<path d="{smooth_path([(x*C, y*C) for x, y in sent], closed=False)}" stroke="#d8c7a0" stroke-width="{1.6*C}" fill="none" stroke-linecap="round"/>')
    # sottobosco spinoso
    m.terr_blob(14.5, 7.4, 3.2, 1.8, 3, "#6d7f45", 0.25, INK, 1.5)
    for i in range(26):
        x, y = 14.5 + rnd.uniform(-2.8, 2.8), 7.4 + rnd.uniform(-1.5, 1.5)
        m.post.append(f'<path d="M{x*C:.0f},{y*C:.0f} l4,-6 l4,6 M{x*C+2:.0f},{y*C-2:.0f} l-5,-2" stroke="#3d4a22" stroke-width="1.3" fill="none"/>')
    # gusci d'uovo argentati
    for (x, y) in [(15.6, 9.0), (16.1, 9.3), (15.2, 9.4)]:
        m.post.append(f'<path d="M{x*C:.0f},{y*C:.0f} l6,-4 l5,4 l-4,3 z" fill="#d9dee3" stroke="#7d8790" stroke-width="1"/>')
    # impronte di troll del ghiaccio
    for k, (x, y) in enumerate([(5.0, 11.8), (6.2, 10.6), (7.6, 9.8), (8.8, 8.6), (10.2, 7.9)]):
        impronta(m, x, y, 50 + k * 4)
    # alberi
    occ = [(x, y) for x, y in sent]
    alberi = []
    for i in range(260):
        x, y = rnd.uniform(0, 30), rnd.uniform(0, 20)
        if min(math.hypot(x - a, y - b) for a, b in occ) < 2.0:
            continue
        if math.hypot(x - 14.5, y - 7.4) < 3.4:
            continue
        if any(math.hypot(x - a, y - b) < 1.4 for a, b in alberi):
            continue
        alberi.append((x, y))
    for i, (x, y) in enumerate(sorted(alberi, key=lambda p: p[1])):
        m.tree(x, y, rnd.uniform(0.6, 1.0), 100 + i, dead=(i % 13 == 0))
    m.text(27.5, 1.3, "verso la montagna ↗", 12)
    m.text(2.2, 19.4, "da Pinebrook", 11)
    m.label("B1", 3.2, 14.6); m.label("B2", 14.5, 5.0); m.label("B3", 7.2, 12.4)
    return m, {"titolo": "Il sentiero nel bosco", "ordine": 1, "griglia": G, "inizio": [1, 16],
               "note_master": "B1: partenza con la Capitana Kole. B2: il cucciolo esce dal sottobosco spinoso (Percezione CD 10 per sentirlo). B3: impronte di troll del ghiaccio coperte di brina."}


def mappa_ingresso():
    m = Map("02_ingresso_della_caverna", 30, 22, "L'ingresso della caverna", "Incontro 2 · ghiaccioli viventi", outdoor=True, base=SNOW)
    rnd = random.Random(2)
    # fianco della montagna
    m.terr(f'<path d="{smooth_path([(-1*C,-1*C),(31*C,-1*C),(31*C,9*C),(24*C,10.5*C),(19*C,11.5*C),(15*C,12.2*C),(10*C,11.4*C),(5*C,10.2*C),(-1*C,9.5*C)])}" fill="{ROCCIA}" stroke="{INK}" stroke-width="3"/>')
    for i in range(40):
        x, y = rnd.uniform(0, 30), rnd.uniform(0, 9)
        m.terr(f'<path d="M{x*C:.0f},{y*C:.0f} l{rnd.uniform(10,22):.0f},{rnd.uniform(-6,6):.0f}" stroke="#6f777c" stroke-width="2"/>')
    for i in range(14):
        m.terr_blob(rnd.uniform(0, 30), rnd.uniform(12, 22), rnd.uniform(1, 2.5), rnd.uniform(0.6, 1.4), 30 + i, "#ffffff", 0.3)
    # caverna
    m.cave(15, 5.2, 5.2, 3.6, 21)
    m.rect(12.5, 7.5, 5, 4.6)
    m.rect(14, 0, 2, 3)
    m.deco_blob(15, 10.6, 2.6, 1.2, 22, ICE, ICE_D, 0.3)
    ghiaccioli(m, 11.5, 10.2, 7, 4, 5, 26)
    ghiaccioli(m, 12.5, 7.6, 5, 3, 6, 10)
    m.chest(13.6, 6.2)
    m.post.append(f'<text x="{17.8*C}" y="{3.6*C}" font-family={FONT!r} font-size="20" fill="#ffffff" opacity=".8">⛏ ✋ ⚒</text>')
    m.text(17.8, 3.0, "disegni a gesso", 10)
    m.text(15, 0.6, "tunnel", 10)
    for i in range(12):
        x, y = rnd.uniform(2, 28), rnd.uniform(13, 21)
        m.rock(x, y, rnd.uniform(0.3, 0.6), 50 + i)
    for i, (x, y) in enumerate([(3, 15), (26, 14), (5, 20), (24, 19.5), (28, 21)]):
        m.tree(x, y, 0.9, 80 + i)
    m.label("C1", 15, 13.6); m.label("C2", 13.6, 7.2); m.label("C3", 17.6, 4.6)
    m.text(15, 21.5, "dal bosco", 11)
    return m, {"titolo": "L'ingresso della caverna", "ordine": 2, "griglia": G, "inizio": [13, 19],
               "note_master": "C1: 5 ghiaccioli viventi tra i frammenti di ghiaccio (CA 10, PF 7, artigli +2, 1d6). C2: zaino logoro (carne essiccata, 5 torce, acciarino, 12 mo). C3: disegni a gesso dei troll; il tunnel sale verso la tana."}


def mappa_tunnel():
    m = Map("03_i_tunnel_della_tana", 40, 26, "I tunnel della tana", "Incontro 3 · parete ghiacciata, specchio di ghiaccio, scivoli")
    # ingresso e parete ghiacciata
    m.rect(2, 22, 3, 4)
    m.rect(1, 13, 8, 9)
    m.deco_poly([(1, 13), (9, 13), (9, 15.2), (1, 15.2)], ICE, ICE_D, 2, smooth=False)
    for k in range(9):
        m.floordeco.append(f'<line x1="{(1.3+k*0.9)*C:.0f}" y1="{13*C+4}" x2="{(1.6+k*0.9)*C:.0f}" y2="{15.1*C:.0f}" stroke="{ICE_D}" stroke-width="1.5"/>')
    m.text(5, 14.4, "parete ghiacciata · 15 m", 11)
    m.post.append(f'<path d="M{6.2*C},{15.2*C} C{6.6*C},{14*C} {5.8*C},{13.2*C} {6.2*C},{12*C}" stroke="{WOOD}" stroke-width="3" fill="none" stroke-dasharray="6 3"/>')
    # galleria in salita e specchio
    m.rect(4, 8, 2, 5)
    m.rect(4, 7, 16, 2.4)
    m.stairs(6.4, 7.1, 3.0, 2.2, "e")
    m.post.append(f'<rect x="{13.4*C}" y="{7*C}" width="{0.45*C}" height="{2.4*C}" fill="#e6f6ff" stroke="{ICE_D}" stroke-width="2.5"/>')
    m.post.append(f'<rect x="{13.2*C}" y="{6.9*C}" width="{0.85*C}" height="{2.6*C}" fill="none" stroke="#b9c7ff" stroke-width="2" stroke-dasharray="3 3"/>')
    m.text(13.6, 6.5, "specchio di ghiaccio", 11)
    # grande caverna con la scarpata e gli scivoli
    m.cave(28.5, 12.5, 9.6, 10.2, 31, jit=0.08)
    m.rect(19.5, 7, 2.4, 2.4)
    m.deco_poly([(20.5, 4.5), (27, 3.2), (31, 4.2), (30, 7.6), (24, 8.6), (20.5, 8.4)], "#e3eef4", ICE_D, 2)
    m.post.append(f'<path d="{smooth_path([(20.8*C,8.6*C),(24*C,9.1*C),(30.3*C,7.9*C),(32*C,5*C)], closed=False)}" stroke="{INK}" stroke-width="4" fill="none" stroke-dasharray="10 4"/>')
    m.text(26, 4.6, "scarpata che crolla", 11)
    scivoli = [
        [(22, 8.8), (21.5, 12), (24, 15), (23, 18), (26, 21)],
        [(25, 9.0), (27.5, 12), (25, 14.5), (27.5, 17.5), (30, 21)],
        [(28.5, 8.6), (27, 11), (30.5, 13.5), (29, 16), (32.5, 18.5)],
        [(31, 7.4), (33.5, 10.5), (31.5, 13), (34.5, 16), (34, 19.5)],
        [(24.3, 15.4), (28, 15.2), (31.2, 13.6)],
        [(25.5, 12.3), (29.8, 11.5)],
    ]
    for k, sc in enumerate(scivoli):
        d = smooth_path([(x * C, y * C) for x, y in sc], closed=False)
        m.post.append(f'<path d="{d}" stroke="{INK}" stroke-width="{0.95*C:.0f}" fill="none" stroke-linecap="round"/>')
        m.post.append(f'<path d="{d}" stroke="{ICE}" stroke-width="{0.75*C:.0f}" fill="none" stroke-linecap="round"/>')
        m.post.append(f'<path d="{d}" stroke="#ffffff" stroke-width="2" fill="none" stroke-dasharray="6 8" opacity=".9"/>')
    for (x, y) in [(23, 18), (34, 19.5)]:
        m.post.append(f'<rect x="{(x-0.6)*C}" y="{(y-0.2)*C}" width="{1.2*C}" height="{0.5*C}" fill="#e6f6ff" stroke="{ICE_D}" stroke-width="2.5"/>')
    ghiaccioli(m, 26.6, 16.5, 2.0, 1.6, 9, 9)
    ghiaccioli(m, 32.5, 9.8, 2.0, 1.6, 10, 9)
    m.deco_blob(29.5, 21.0, 5.0, 1.6, 33, "#e3eef4", ICE_D, 0.2)
    m.rect(34.2, 18.5, 5.8, 2)
    m.text(38.7, 18.2, "verso le uova →", 10)
    m.label("T1", 5, 18.6); m.label("T2", 13.6, 10.2); m.label("T3", 25.5, 6.2); m.label("T4", 29.5, 22.6)
    return m, {"titolo": "I tunnel della tana", "ordine": 3, "griglia": G, "inizio": [3, 24],
               "note_master": "T1: scalare la parete (Atletica o Acrobazia CD 10, fallimento 1d6; il kit di Noorah dà vantaggio; con la corda gli altri salgono senza tiro). T2: specchio di Bahamut, risposta «orn darastrix» = cura completa + vantaggio al primo tiro della prova seguente; rompere lo specchio = 1d6 e niente cura. T3: la scarpata crolla, scegliere lo scivolo (Indagare o Percezione CD 10; altrimenti Acrobazia/Atletica CD 15 o 1d6). T4: fondo della caverna."}


def mappa_uova():
    m = Map("04_la_caverna_delle_uova", 30, 24, "La caverna delle uova", "Incontro 4 · uova di drago e argento volante")
    m.cave(15.5, 12, 13.2, 10.4, 41, jit=0.1)
    m.rect(0, 10.5, 3, 2.4)
    rnd = random.Random(4)
    for i in range(7):
        m.deco_blob(rnd.uniform(5, 26), rnd.uniform(4, 20), rnd.uniform(1, 2.2), rnd.uniform(0.6, 1.3), 50 + i, ICE, ICE_D, 0.25, opacity=0.9)
    for i in range(26):
        x, y = rnd.uniform(4, 27), rnd.uniform(3, 21)
        if math.hypot(x - 16, y - 12.5) < 4.2 or (x < 6 and 10 < y < 14):
            continue
        r = rnd.uniform(0.25, 0.5)
        m.post.append(f'<circle cx="{x*C:.0f}" cy="{y*C:.0f}" r="{r*C:.1f}" fill="#b8c8d2" stroke="{INK}" stroke-width="1.5"/><circle cx="{x*C-2:.0f}" cy="{y*C-2:.0f}" r="{r*C*0.4:.1f}" fill="#ffffff" opacity=".8"/>')
    # nido
    m.post.append(f'<ellipse cx="{16*C}" cy="{12.5*C}" rx="{3.4*C}" ry="{2.6*C}" fill="#f6fbfd" stroke="{ICE_D}" stroke-width="2.5"/>')
    for (x, y) in [(14.6, 11.6), (17.4, 11.6), (14.6, 13.5), (17.4, 13.5)]:
        m.post.append(f'<circle cx="{x*C}" cy="{y*C}" r="{0.75*C}" fill="#ffffff" stroke="#a9c7d8" stroke-width="2"/>')
    for (x, y) in [(14.6, 11.6), (17.4, 11.6)]:
        m.post.append(f'<ellipse cx="{x*C}" cy="{y*C}" rx="{0.42*C}" ry="{0.55*C}" fill="#c9d1d8" stroke="#5f6b74" stroke-width="2"/><ellipse cx="{x*C-4}" cy="{y*C-5}" rx="3" ry="5" fill="#ffffff" opacity=".8"/>')
    for (dx, dy) in [(-6, 4), (5, 2), (0, -6), (-2, 7)]:
        m.post.append(f'<path d="M{14.6*C+dx},{13.5*C+dy} l6,-4 l5,4 l-4,3z" fill="#d9dee3" stroke="#7d8790"/>')
    m.post.append(f'<text x="{17.4*C}" y="{13.5*C+5}" font-family={FONT!r} font-size="14" text-anchor="middle" fill="#7d8790">?</text>')
    # buco nel soffitto
    m.post.append(f'<circle cx="{20.5*C}" cy="{7.5*C}" r="{2.6*C}" fill="none" stroke="#5f8fa8" stroke-width="2.5" stroke-dasharray="8 5"/>')
    m.text(20.5, 4.6, "buco nel soffitto (ghiaccio)", 11)
    m.post.append(f'<rect x="{23.5*C}" y="{15.2*C}" width="{1.4*C}" height="{0.9*C}" rx="4" fill="#d98c7a" stroke="{INK}" stroke-width="1.5"/>')
    m.text(24.2, 16.9, "carne congelata", 10)
    m.label("U1", 2.5, 9.6); m.label("U2", 16, 16.2); m.label("U3", 20.5, 9.0)
    return m, {"titolo": "La caverna delle uova", "ordine": 4, "griglia": G, "inizio": [1, 11],
               "note_master": "U2: due uova intatte, un guscio rotto (il cucciolo) e un posto vuoto (uovo rubato dai troll). 3 ladri di uova (CA 12, PF 18, morso +4, 1d6+2). U3: alla fine Rorn sfonda il ghiaccio del soffitto e atterra davanti al gruppo."}


def main():
    import shutil
    import subprocess
    os.makedirs(os.path.join(OUT, "alternative"), exist_ok=True)
    meta_tutte = {}
    for fn in (mappa_sentiero, mappa_ingresso, mappa_tunnel, mappa_uova):
        m, meta = fn()
        cartella = os.path.join(OUT, "alternative") if m.name in ALTERNATIVE else OUT
        svg = os.path.join(cartella, m.name + ".svg")
        with open(svg, "w", encoding="utf-8") as f:
            f.write(m.render(meta["titolo"]))
        if shutil.which("rsvg-convert"):
            os.makedirs(os.path.join(cartella, "png"), exist_ok=True)
            subprocess.run(["rsvg-convert", "--zoom", "2", "-o", os.path.join(cartella, "png", m.name + ".png"), svg], check=True)
        meta_tutte[m.name] = meta
        print("ok", m.name)
    with open(os.path.join(QUI, "dati", "mappe.json"), "w", encoding="utf-8") as f:
        json.dump(meta_tutte, f, ensure_ascii=False, indent=1)

if __name__ == "__main__":
    main()
