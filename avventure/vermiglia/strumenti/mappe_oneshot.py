#!/usr/bin/env python3
"""Mappe del one-shot «La Tana di Vermiglia».

Riusa il motore di disegno della campagna (genera_mappe.py) e scrive in asset/mappe/vermiglia/.
Uso:  python3 mappe_oneshot.py
"""
import math
import os
import random
import shutil
import subprocess
import sys

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(QUI, "..", "..", "brumaria", "strumenti"))
import genera_mappe as g  # noqa: E402
from genera_mappe import Map, C, INK, FLOOR, WATER, WATER_D, GRASS, WOOD, FONT, smooth_path, blob_pts  # noqa: E402

OUT = os.path.join(QUI, "..", "..", "..", "asset", "mappe", "vermiglia")
LAVA = "#e5602a"
LAVA_L = "#ffb347"
ROCK = "#b8ab92"


def lava(m, pts, layer="floordeco", smooth=True):
    P = [(x * C, y * C) for x, y in pts]
    d = smooth_path(P) if smooth else "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in P) + "Z"
    getattr(m, layer).append(f'<path d="{d}" fill="{LAVA}" stroke="#7a2a10" stroke-width="3"/>')
    getattr(m, layer).append(f'<path d="{d}" fill="none" stroke="{LAVA_L}" stroke-width="2" stroke-dasharray="6 10" opacity=".9"/>')


def coins(m, x, y, w, h, seed, n=40):
    rnd = random.Random(seed)
    for _ in range(n):
        px, py = (x + rnd.random() * w) * C, (y + rnd.random() * h) * C
        m.post.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="{rnd.uniform(2.5,4.5):.1f}" fill="#e2b93b" stroke="#7a5a10" stroke-width=".8"/>')


# ---------------------------------------------------------------------------
def mappa_piazza():
    m = Map("01_piazza_di_pietracalda", 30, 22, "La Piazza di Pietracalda", "Scena 1 · l'assalto dei coboldi", outdoor=True, base="#cfc89c")
    rnd = random.Random(3)
    # piazza lastricata
    m.terr(f'<rect x="{6*C}" y="{5*C}" width="{18*C}" height="{12*C}" rx="18" fill="#d9d0b5" stroke="#9c8f6c" stroke-width="2"/>')
    for i in range(140):
        x, y = rnd.uniform(6.3, 23.7), rnd.uniform(5.3, 16.7)
        m.terr(f'<rect x="{x*C:.0f}" y="{y*C:.0f}" width="{rnd.uniform(8,14):.0f}" height="{rnd.uniform(6,10):.0f}" fill="none" stroke="#b5a984" stroke-width=".8"/>')
    # torrente a est
    m.terr(f'<path d="{smooth_path([(27.2*C,-1*C),(29.6*C,-1*C),(30.6*C,6*C),(29.8*C,12*C),(30.6*C,23*C),(27.6*C,23*C),(27.2*C,14*C),(26.6*C,7*C)])}" fill="{WATER}" stroke="{WATER_D}" stroke-width="2"/>')
    m.planks(25.6, 10.6, 30.4, 10.6, 1.6, "terrain")
    # strade
    for d in [f"M{15*C},{17*C} L{15*C},{22.5*C}", f"M{6*C},{11*C} L{-1*C},{11*C}"]:
        m.terr(f'<path d="{d}" stroke="#c9b98c" stroke-width="{2.4*C}" fill="none"/>')
    # locanda
    m.rect(1, 1, 8, 6)
    m.door(5, 7, "h")
    m.box(1.4, 1.4, 4, 0.7, "#9b6a3a")
    for (x, y) in [(2.4, 3.6), (5, 3.6), (7.4, 4.6), (2.6, 5.6)]:
        m.table(x - 0.5, y - 0.4, 1.0, 0.8)
    m.fire(7.8, 1.8, 0.35)
    m.barrel(6.2, 1.6); m.barrel(6.9, 1.6, 0.25)
    # granaio
    m.rect(21, 1, 7, 6)
    m.door(24.5, 7, "h")
    for (x, y) in [(22, 2), (23, 2), (22, 3), (26.8, 2), (26.8, 3), (26.8, 5.6)]:
        m.crate(x + 0.4, y + 0.4, 0.7)
    m.post.append(f'<ellipse cx="{24*C}" cy="{4*C}" rx="{1.4*C}" ry="{0.9*C}" fill="#e3c76a" stroke="{INK}" stroke-width="1.5"/>')
    # casa di Tilde
    m.rect(1, 14, 6, 6)
    m.door(7, 17, "v")
    m.bed(1.4, 14.4, 0.9, 1.6); m.bed(2.6, 14.4, 0.9, 1.6); m.table(3.6, 17.2, 1.4, 1)
    m.fire(1.8, 19.2, 0.3)
    m.post.append(f'<rect x="{5.4*C}" y="{14.4*C}" width="{1.2*C}" height="{1.2*C}" fill="none" stroke="{INK}" stroke-dasharray="3 3"/>')
    # fucina
    m.rect(21, 15, 6, 5)
    m.door(21, 17.5, "v")
    m.fire(25.6, 16.2, 0.5)
    m.box(23.2, 17.2, 1.2, 0.6, "#5a5a5a")
    m.barrel(25.8, 19.2)
    # piazza: pozzo, bancarelle, carri
    m.well(15, 11, 0.8)
    for (x, y) in [(9, 7), (19.5, 7), (9, 14.6), (19.5, 14.6)]:
        m.box(x, y, 2, 1, "#e0cfa0")
        m.post.append(f'<path d="M{x*C},{y*C} l{C},{-0.3*C} l{C},{0.3*C}" fill="none" stroke="#a8553a" stroke-width="3"/>')
    m.box(11.6, 9.0, 1.0, 2.0, "#9b6a3a"); m.box(17.4, 12.0, 1.0, 2.0, "#9b6a3a")
    m.crate(13, 15.6); m.crate(13.7, 15.8, 0.5); m.barrel(16.8, 6.2)
    # grata del canale
    m.post.append(f'<rect x="{26.2*C}" y="{12.6*C}" width="{1.2*C}" height="{1.2*C}" fill="#3a3a3a" stroke="{INK}" stroke-width="2"/>')
    for k in range(1, 4):
        m.post.append(f'<line x1="{(26.2+0.3*k)*C}" y1="{12.6*C}" x2="{(26.2+0.3*k)*C}" y2="{13.8*C}" stroke="#999" stroke-width="2"/>')
    # alberi, fieni, staccionate
    for i, (x, y, r) in enumerate([(11, 1.6, 1.1), (16, 2, 0.9), (2, 10, 1.0), (10, 19.5, 1.2), (19, 20.5, 1.0), (24.4, 12.4, 0.8), (3.8, 11.8, 0.7)]):
        m.tree(x, y, r, 40 + i)
    m.post.append(f'<path d="M{10*C},{21.4*C} H{20*C} M{17*C},{0.5*C} H{20.5*C}" stroke="{WOOD}" stroke-width="3" stroke-dasharray="10 4"/>')
    for (x, y) in [(13, 20.2), (14.2, 20.6)]:
        m.post.append(f'<circle cx="{x*C}" cy="{y*C}" r="{0.55*C}" fill="#e3c76a" stroke="{INK}" stroke-width="1.5"/>')
    m.label("P1", 5, 5.6); m.label("P2", 15, 12.6); m.label("P3", 24.5, 5.8)
    m.label("P4", 4, 19.2); m.label("P5", 24, 19.2); m.label("P6", 26.8, 14.6)
    m.text(28.6, 3, "torrente", 11, rot=80)
    return m


def mappa_passo():
    m = Map("02_passo_del_vento", 32, 22, "Il Passo del Vento", "Scena 2 · la salita al Monte Fumo", outdoor=True, base=ROCK)
    rnd = random.Random(8)
    for i in range(18):
        g_ = rnd.uniform(0, 32), rnd.uniform(0, 22)
        m.terr_blob(g_[0], g_[1], rnd.uniform(1, 3), rnd.uniform(0.8, 2), 200 + i, "#a99d84", 0.3)
    # baratro
    ch = [(14.2, -1), (17.6, -1), (18.4, 4), (17.4, 9), (18.6, 14), (18.0, 23), (14.4, 23), (15.2, 15), (13.8, 9), (15.0, 4)]
    m.terr(f'<path d="{smooth_path([(x*C, y*C) for x, y in ch])}" fill="#1e1814" stroke="{INK}" stroke-width="5"/>')
    # sentiero
    path_w = [(1, 22.5), (3, 18), (7.5, 16.5), (9, 13), (12.6, 10.2)]
    path_e = [(19.4, 10.2), (22, 8.5), (24, 6.6), (27, 5), (31.5, 1.5)]
    for pth in (path_w, path_e):
        m.terr(f'<path d="{smooth_path([(x*C, y*C) for x, y in pth], closed=False)}" stroke="#d6c9a8" stroke-width="{2.2*C}" fill="none" stroke-linecap="round"/>')
    # ponte di corde
    m.rope_bridge(12.4, 10.2, 19.6, 10.2)
    # sporgenza
    m.terr_blob(6.5, 5, 4.2, 2.6, 21, "#c8bc9f", 0.12, INK, 3)
    m.terr(f'<path d="M{3*C},{7*C} Q{6.5*C},{8.6*C} {10*C},{6.8*C}" stroke="{INK}" stroke-width="4" fill="none"/>')
    for (x, y) in [(5, 4.6), (6.2, 4.0), (7.6, 4.4), (6.8, 5.6)]:
        m.rock(x, y, 0.55, int(x * 7 + y))
    m.post.append(f'<path d="M{7*C},{7.4*C} L{8.4*C},{12.4*C}" stroke="#7a2e1c" stroke-width="3" stroke-dasharray="6 5" marker-end="url(#arrow)"/>')
    # torre in rovina
    m.rect(24, 1, 5, 5)
    m.door(26.5, 6, "h", "arch")
    m.rubble(24.4, 1.4, 2.0, 1.8, 31, 14)
    m.stairs(27.2, 1.3, 1.4, 2.4, "n")
    m.box(25.3, 4.2, 1.2, 0.7, "#9b6a3a")
    # grotta di Mek
    m.terr_blob(22.5, 16, 2.6, 1.9, 41, "#3d342c", 0.18, INK, 3)
    m.terr(f'<path d="{smooth_path([(20.4*C,10.6*C),(21*C,13*C),(22*C,14.6*C)], closed=False)}" stroke="#cdbf9e" stroke-width="{0.9*C}" fill="none" stroke-dasharray="4 6"/>')
    m.post.append(f'<circle cx="{22.8*C}" cy="{16.2*C}" r="6" fill="#e8892f"/>')
    # rocce, alberi morti
    for i, (x, y, r) in enumerate([(2, 2, .7), (11, 3, .8), (11, 17, .6), (4, 13, .7), (21, 20, .8), (28, 12, .9), (30, 18, .7), (25, 10.5, .6), (9.5, 20, .7)]):
        m.rock(x, y, r * 0.8, 500 + i)
    for i, (x, y) in enumerate([(1.5, 9), (12, 20), (29, 9), (26, 19.5)]):
        m.tree(x, y, 0.8, 600 + i, dead=True)
    m.rubble(8.6, 11.6, 2.6, 1.2, 77, 8)
    m.label("Q1", 4.6, 19.2); m.label("Q2", 6.5, 2.0); m.label("Q3", 16, 8.8)
    m.label("Q4", 26.5, 7.4); m.label("Q5", 22.5, 18.6); m.label("Q6", 30, 3.4)
    m.text(2.4, 21.6, "dal villaggio", 11)
    m.text(29.4, 0.9, "alla Forgia", 11)
    return m


def mappa_forgia():
    m = Map("03_forgia_di_durnkar", 44, 30, "La Forgia di Durnkar", "Scene 3-4 · la tana di Vermiglia")
    # esterno
    m.poly([(0, 29.2), (4, 28.6), (9, 28.8), (13, 30), (0, 30)])
    # L1 portale
    m.rect(2, 22, 8, 6)
    m.rect(5, 28, 2, 1.2)
    m.door(6, 28, "h", "locked")
    m.statue(3.2, 23.2); m.statue(8.8, 23.2)
    for (x, y) in [(3, 26), (9, 26)]:
        m.pillar(x, y, 0.35, True)
    m.post.append(f'<text x="{6*C}" y="{25.6*C}" font-family={FONT!r} font-size="20" text-anchor="middle" fill="#7a5a10">ᚦ ᚢ ᚱ</text>')
    # corridoio verso nord
    m.rect(5, 17, 2, 5)
    m.door(6, 22, "h", "sealed")
    # L2 sala delle trappole
    m.rect(3, 13, 18, 4)
    for (x, y) in [(8, 14), (11, 15), (14, 14), (17, 15)]:
        m.post.append(f'<rect x="{x*C+4}" y="{y*C+4}" width="{C-8}" height="{C-8}" fill="none" stroke="#7a2e1c" stroke-width="2" stroke-dasharray="3 2"/>')
    for x in (7, 10, 13, 16, 19):
        m.post.append(f'<rect x="{x*C}" y="{13*C-3}" width="10" height="6" fill="{INK}"/>')
    m.box(19.6, 15.8, 0.8, 0.8, "#8a6a45")
    # L4 dispensa
    m.rect(10, 6, 7, 5)
    m.rect(13, 11, 1, 2)
    m.door(13.5, 12, "h")
    m.barrel(10.6, 6.6); m.barrel(11.4, 6.6); m.crate(16.2, 6.8); m.crate(16.2, 7.7, 0.5); m.table(12.5, 8, 2, 1)
    m.rubble(14.6, 9.4, 2, 1.3, 12, 6)
    # L5 prigione
    m.rect(2, 5, 6, 6)
    m.rect(8, 8, 2, 1)
    m.door(9, 8.5, "v", "locked")
    m.cage(3.2, 6.3, 1.4); m.cage(3.2, 9.4, 1.4); m.cage(6.6, 6.3, 1.2)
    m.post.append(f'<circle cx="{3.2*C}" cy="{9.4*C}" r="6" fill="#d9a066" stroke="{INK}"/>')
    m.statue(6.8, 9.6, 0.42)
    # L3 tana dei coboldi
    m.cave(27.5, 14.5, 5.2, 4.2, 51)
    m.rect(21, 14, 3, 2)
    m.door(21, 15, "v")
    for (x, y) in [(25, 12), (29.5, 12.4), (24.6, 16.6), (30.6, 17)]:
        m.tent(x, y, 1.0)
    m.fire(27.5, 14.8, 0.45)
    m.post.append(f'<rect x="{26.6*C}" y="{11.0*C}" width="{1.8*C}" height="{0.9*C}" fill="#b23a2a" stroke="{INK}" stroke-width="1.5"/>')
    m.text(27.5, 10.7, "altare del drago", 10)
    # galleria verso L6
    m.rect(27, 6, 2, 5)
    # L6 ponte di lava
    m.cave(29.5, 3.6, 6.4, 2.8, 61)
    lava(m, [(28.0, 0.6), (31.0, 0.6), (31.6, 3), (31.2, 7.2), (28.2, 7.2), (27.6, 3)])
    m.planks(27.0, 3.8, 32.4, 3.8, 1.0)
    m.box(25.4, 2.4, 0.6, 0.9, "#666")
    m.text(25.7, 2.1, "leva", 10)
    # passaggio verso L7
    m.rect(34, 2.5, 3, 2)
    m.rect(35, 4.5, 2, 3.5)
    # L7 sala della grande forgia
    m.rect(34, 8, 9, 19)
    m.door(36, 8, "h", "arch")
    lava(m, [(34.1, 8.1), (42.9, 8.1), (42.9, 10.2), (38.5, 11.0), (34.1, 10.2)], smooth=False)
    lava(m, [(41.5, 10.4), (42.9, 10.2), (42.9, 26.9), (41.7, 26.9), (41.3, 18)], smooth=False)
    for (x, y) in [(35.5, 13), (35.5, 18), (35.5, 23), (39.8, 13), (39.8, 18), (39.8, 23)]:
        m.pillar(x, y, 0.4, True)
    m.box(37.2, 17.2, 1.8, 1.0, "#4f4f4f", 2)
    m.post.append(f'<ellipse cx="{38.1*C}" cy="{17.0*C}" rx="9" ry="12" fill="#f2cf4a" stroke="#7a5a10" stroke-width="2"/>')
    m.post.append(f'<rect x="{35*C}" y="{11.4*C}" width="{3*C}" height="{1.0*C}" fill="#3b3b3b" stroke="{INK}" stroke-width="2"/>')
    m.text(36.5, 11.2, "il grande mantice", 10)
    coins(m, 36.6, 22.6, 3.8, 3.2, 7, 70)
    m.chest(38, 24.4); m.chest(36.8, 25.6)
    m.post.append(f'<path d="M{36*C},{8.4*C} L{34*C},{6*C}" stroke="none"/>')
    # cunicolo segreto di Mek (L3 -> L7)
    m.rect(32.4, 15.5, 1.6, 1)
    m.door(34, 16, "v", "secret")
    m.label("L1", 6, 27.2); m.label("L2", 12, 16.2); m.label("L3", 27.5, 18.2)
    m.label("L4", 13.5, 9.8); m.label("L5", 5, 10.4); m.label("L6", 33.2, 1.2)
    m.label("L7", 38.5, 20.6)
    m.text(23, 13.6, "trappole a pressione", 10)
    m.text(38.5, 9.6, "colata di lava", 11)
    return m


LEGENDE = {
    "01_piazza_di_pietracalda": "P6: grata del canale di scolo, da cui arrivano i coboldi",
    "02_passo_del_vento": "La gola è profonda 30 m · Il ponte regge 3 persone alla volta",
    "03_forgia_di_durnkar": "Lava: 3d6 danni da fuoco a chi ci entra · S: passaggio segreto di Mek",
}


def scene_meta(name, title, w, h, grid=True, cols=0, rows=0):
    d = {"id": name, "titolo": title, "file": name + ".svg", "larghezza": w, "altezza": h}
    if grid:
        d["griglia"] = {"cella": C, "ox": 40, "oy": 92, "colonne": cols, "righe": rows}
    return d


def main():
    os.makedirs(OUT, exist_ok=True)
    have_rsvg = shutil.which("rsvg-convert")
    for fn in (mappa_piazza, mappa_passo, mappa_forgia):
        m = fn()
        svg = m.render(LEGENDE[m.name])
        p = os.path.join(OUT, m.name + ".svg")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(svg)
        if have_rsvg:
            png = os.path.join(OUT, "png", m.name + ".png")
            os.makedirs(os.path.dirname(png), exist_ok=True)
            subprocess.run(["rsvg-convert", "--zoom", "2", "-o", png, p], check=True)
        print("ok", m.name)


if __name__ == "__main__":
    main()
