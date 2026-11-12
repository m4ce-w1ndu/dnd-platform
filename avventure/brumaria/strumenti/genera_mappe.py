#!/usr/bin/env python3
"""Genera tutte le mappe di «Le Campane di Brumaria» in SVG (e PNG se c'è rsvg-convert).

Uso:  python3 genera_mappe.py            -> scrive in ../mappe/
Le mappe sono deterministiche (seed fissi): rigenerandole si ottiene lo stesso risultato.
"""
import math
import os
import random
import shutil
import subprocess

C = 32  # pixel per quadretto (1 quadretto = 1,5 m)
INK = "#2a2018"
PAPER = "#efe3c4"
FLOOR = "#fbf6e8"
GRIDC = "#7d6d50"
WATER = "#a3c3c0"
WATER_D = "#6f9b9c"
SWAMP = "#a7b28a"
GRASS = "#c9cf9a"
MUD = "#cdbb8d"
WOOD = "#8f6236"
ROOF = "#a8553a"
FONT = "'Noto Serif','DejaVu Serif',Georgia,serif"

# le mappe generate sono asset del repository: asset/mappe/brumaria/ (SVG) e …/png/ (PNG per i VTT)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "asset", "mappe", "brumaria")


def fm(v):
    return f"{v:.1f}"


def esc(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def smooth_path(pts, closed=True):
    """Catmull-Rom -> curve di Bézier (pts in pixel)."""
    n = len(pts)
    d = f"M{fm(pts[0][0])},{fm(pts[0][1])}"
    for i in range(n if closed else n - 1):
        p0 = pts[(i - 1) % n] if (closed or i > 0) else pts[0]
        p1 = pts[i]
        p2 = pts[(i + 1) % n]
        p3 = pts[(i + 2) % n] if (closed or i + 2 < n) else pts[-1]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d += f" C{fm(c1[0])},{fm(c1[1])} {fm(c2[0])},{fm(c2[1])} {fm(p2[0])},{fm(p2[1])}"
    return d + ("Z" if closed else "")


def blob_pts(cx, cy, rx, ry, seed, n=30, jit=0.12):
    rnd = random.Random(seed)
    ph = [rnd.uniform(0, 6.28) for _ in range(3)]
    amp = [rnd.uniform(0.3, 1) for _ in range(3)]
    tot = sum(amp)
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        nz = sum(amp[k] * math.sin((k + 2) * a + ph[k]) for k in range(3)) / tot
        r = 1 + jit * nz + rnd.uniform(-jit / 4, jit / 4)
        pts.append((cx + rx * r * math.cos(a), cy + ry * r * math.sin(a)))
    return pts


def in_ellipse(x, y, cx, cy, rx, ry, k=1.0):
    return ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= k


# ---------------------------------------------------------------------------
#  Mappa tattica a quadretti
# ---------------------------------------------------------------------------
class Map:
    def __init__(self, name, cols, rows, title, subtitle, outdoor=False, base=None):
        self.name, self.cols, self.rows = name, cols, rows
        self.title, self.subtitle = title, subtitle
        self.outdoor = outdoor
        self.base = base
        self.terrain, self.floors, self.floordeco, self.post, self.labels = [], [], [], [], []

    # --- forme del pavimento (unite: i muri si fondono) ---
    def rect(self, x, y, w, h):
        self.floors.append(f'<rect x="{fm(x*C)}" y="{fm(y*C)}" width="{fm(w*C)}" height="{fm(h*C)}"/>')

    def circle(self, cx, cy, r):
        self.floors.append(f'<circle cx="{fm(cx*C)}" cy="{fm(cy*C)}" r="{fm(r*C)}"/>')

    def poly(self, pts):
        p = " ".join(f"{fm(x*C)},{fm(y*C)}" for x, y in pts)
        self.floors.append(f'<polygon points="{p}"/>')

    def cave(self, cx, cy, rx, ry, seed, jit=0.13):
        self.floors.append(f'<path d="{smooth_path(blob_pts(cx*C, cy*C, rx*C, ry*C, seed, jit=jit))}"/>')

    def gap(self, x, y, orient, kind="door"):
        """Apertura di 1 quadretto in un muro spesso, con porta al centro."""
        self.rect(x, y, 1, 1)
        if orient == "v":   # attraversa un muro verticale
            self.door(x + 0.5, y + 0.5, "v", kind)
        else:
            self.door(x + 0.5, y + 0.5, "h", kind)

    # --- terreno (sotto ai pavimenti) ---
    def terr(self, svg):
        self.terrain.append(svg)

    def terr_blob(self, cx, cy, rx, ry, seed, fill, jit=0.15, stroke=None, sw=2):
        st = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
        self.terrain.append(f'<path d="{smooth_path(blob_pts(cx*C, cy*C, rx*C, ry*C, seed, jit=jit))}" fill="{fill}"{st}/>')

    # --- elementi ---
    def door(self, x, y, o, kind="door"):
        w, h = (0.8, 0.32) if o == "h" else (0.32, 0.8)
        X, Y = (x - w / 2) * C, (y - h / 2) * C
        if kind == "secret":
            self.post.append(f'<text x="{fm(x*C)}" y="{fm(y*C+6)}" font-family={FONT!r} font-size="17" font-weight="bold" text-anchor="middle" fill="{INK}" stroke="{FLOOR}" stroke-width="4" paint-order="stroke">S</text>')
            return
        if kind == "arch":
            self.post.append(f'<rect x="{fm(X)}" y="{fm(Y)}" width="{fm(w*C)}" height="{fm(h*C)}" fill="{FLOOR}"/>')
            return
        fill = FLOOR if kind != "sealed" else "#c9b48a"
        self.post.append(f'<rect x="{fm(X)}" y="{fm(Y)}" width="{fm(w*C)}" height="{fm(h*C)}" fill="{fill}" stroke="{INK}" stroke-width="2"/>')
        if kind == "locked":
            self.post.append(f'<circle cx="{fm(x*C)}" cy="{fm(y*C)}" r="3" fill="{INK}"/>')
        if kind == "sealed":
            self.post.append(f'<path d="M{fm(X)},{fm(Y)} L{fm(X+w*C)},{fm(Y+h*C)} M{fm(X+w*C)},{fm(Y)} L{fm(X)},{fm(Y+h*C)}" stroke="{INK}" stroke-width="1.5"/>')
        if kind == "bars":
            self.post.append(f'<line x1="{fm(X)}" y1="{fm(Y)}" x2="{fm(X+w*C)}" y2="{fm(Y+h*C)}" stroke="{INK}" stroke-width="3" stroke-dasharray="3 3"/>')

    def arch_open(self, x1, y1, x2, y2):
        self.post.append(f'<line x1="{fm(x1*C)}" y1="{fm(y1*C)}" x2="{fm(x2*C)}" y2="{fm(y2*C)}" stroke="{PAPER}" stroke-width="11"/>'
                         f'<line x1="{fm(x1*C)}" y1="{fm(y1*C)}" x2="{fm(x2*C)}" y2="{fm(y2*C)}" stroke="{INK}" stroke-width="2" stroke-dasharray="5 4"/>')

    def pillar(self, x, y, r=0.28, square=False):
        if square:
            self.post.append(f'<rect x="{fm((x-r)*C)}" y="{fm((y-r)*C)}" width="{fm(2*r*C)}" height="{fm(2*r*C)}" fill="{INK}"/>')
        else:
            self.post.append(f'<circle cx="{fm(x*C)}" cy="{fm(y*C)}" r="{fm(r*C)}" fill="{INK}"/>')

    def stairs(self, x, y, w, h, d="n"):
        g = [f'<rect x="{fm(x*C)}" y="{fm(y*C)}" width="{fm(w*C)}" height="{fm(h*C)}" fill="{FLOOR}" stroke="{INK}" stroke-width="1.5"/>']
        if d in "ns":
            n = int(h * 4)
            for i in range(1, n):
                yy = (y + h * i / n) * C
                g.append(f'<line x1="{fm(x*C)}" y1="{fm(yy)}" x2="{fm((x+w)*C)}" y2="{fm(yy)}" stroke="{INK}" stroke-width="1.2"/>')
            ay, by = ((y + h) * C - 6, y * C + 8) if d == "n" else (y * C + 6, (y + h) * C - 8)
            cx = (x + w / 2) * C
            g.append(f'<path d="M{fm(cx)},{fm(ay)} L{fm(cx)},{fm(by)}" stroke="{INK}" stroke-width="2" marker-end="url(#arrow)"/>')
        else:
            n = int(w * 4)
            for i in range(1, n):
                xx = (x + w * i / n) * C
                g.append(f'<line x1="{fm(xx)}" y1="{fm(y*C)}" x2="{fm(xx)}" y2="{fm((y+h)*C)}" stroke="{INK}" stroke-width="1.2"/>')
            ax, bx = ((x + w) * C - 6, x * C + 8) if d == "w" else (x * C + 6, (x + w) * C - 8)
            cy = (y + h / 2) * C
            g.append(f'<path d="M{fm(ax)},{fm(cy)} L{fm(bx)},{fm(cy)}" stroke="{INK}" stroke-width="2" marker-end="url(#arrow)"/>')
        self.post.append("".join(g))

    def spiral(self, cx, cy, r=0.9):
        X, Y, R = cx * C, cy * C, r * C
        g = [f'<circle cx="{fm(X)}" cy="{fm(Y)}" r="{fm(R)}" fill="{FLOOR}" stroke="{INK}" stroke-width="2"/>']
        for i in range(10):
            a = 2 * math.pi * i / 10
            g.append(f'<line x1="{fm(X+4*math.cos(a))}" y1="{fm(Y+4*math.sin(a))}" x2="{fm(X+R*math.cos(a))}" y2="{fm(Y+R*math.sin(a))}" stroke="{INK}" stroke-width="1.2"/>')
        g.append(f'<circle cx="{fm(X)}" cy="{fm(Y)}" r="4" fill="{INK}"/>')
        self.post.append("".join(g))

    def ladder(self, x, y, w=0.7, h=1.2):
        X, Y = x * C, y * C
        g = [f'<rect x="{fm(X)}" y="{fm(Y)}" width="{fm(w*C)}" height="{fm(h*C)}" fill="none" stroke="{INK}" stroke-width="2" stroke-dasharray="4 2"/>',
             f'<line x1="{fm(X+5)}" y1="{fm(Y)}" x2="{fm(X+5)}" y2="{fm(Y+h*C)}" stroke="{WOOD}" stroke-width="2.5"/>',
             f'<line x1="{fm(X+w*C-5)}" y1="{fm(Y)}" x2="{fm(X+w*C-5)}" y2="{fm(Y+h*C)}" stroke="{WOOD}" stroke-width="2.5"/>']
        for i in range(1, 5):
            yy = Y + h * C * i / 5
            g.append(f'<line x1="{fm(X+5)}" y1="{fm(yy)}" x2="{fm(X+w*C-5)}" y2="{fm(yy)}" stroke="{WOOD}" stroke-width="2"/>')
        self.post.append("".join(g))

    def box(self, x, y, w, h, fill="#d8c39a", sw=1.5, rx=0):
        self.post.append(f'<rect x="{fm(x*C)}" y="{fm(y*C)}" width="{fm(w*C)}" height="{fm(h*C)}" rx="{rx}" fill="{fill}" stroke="{INK}" stroke-width="{sw}"/>')

    def table(self, x, y, w, h):
        self.box(x, y, w, h, "#c8a774")

    def bed(self, x, y, w=0.8, h=1.6):
        self.box(x, y, w, h, "#e8dcc0")
        self.box(x + 0.1, y + 0.08, w - 0.2, 0.35, "#ffffff", 1)

    def chest(self, x, y):
        self.box(x - 0.35, y - 0.22, 0.7, 0.44, "#b9874d")
        self.post.append(f'<line x1="{fm((x-0.35)*C)}" y1="{fm(y*C)}" x2="{fm((x+0.35)*C)}" y2="{fm(y*C)}" stroke="{INK}" stroke-width="1"/>')

    def barrel(self, x, y, r=0.3):
        self.post.append(f'<circle cx="{fm(x*C)}" cy="{fm(y*C)}" r="{fm(r*C)}" fill="#b98a55" stroke="{INK}" stroke-width="1.5"/><circle cx="{fm(x*C)}" cy="{fm(y*C)}" r="{fm(r*C*0.55)}" fill="none" stroke="{INK}" stroke-width="0.8"/>')

    def crate(self, x, y, s=0.6):
        X, Y, S = (x - s / 2) * C, (y - s / 2) * C, s * C
        self.post.append(f'<rect x="{fm(X)}" y="{fm(Y)}" width="{fm(S)}" height="{fm(S)}" fill="#c99b62" stroke="{INK}" stroke-width="1.5"/><path d="M{fm(X)},{fm(Y)} L{fm(X+S)},{fm(Y+S)} M{fm(X+S)},{fm(Y)} L{fm(X)},{fm(Y+S)}" stroke="{INK}" stroke-width="1"/>')

    def altar(self, x, y, w, h):
        self.box(x, y, w, h, "#d9d2c0", 2)
        self.post.append(f'<path d="M{fm((x+w/2)*C)},{fm((y+0.12)*C)} v{fm((h-0.24)*C)} M{fm((x+w/2-0.2)*C)},{fm((y+h/2-0.05)*C)} h{fm(0.4*C)}" stroke="{INK}" stroke-width="1.5"/>')

    def statue(self, x, y, r=0.38):
        X, Y, R = x * C, y * C, r * C
        pts = []
        for i in range(10):
            a = -math.pi / 2 + i * math.pi / 5
            rr = R if i % 2 == 0 else R * 0.45
            pts.append(f"{fm(X+rr*math.cos(a))},{fm(Y+rr*math.sin(a))}")
        self.post.append(f'<circle cx="{fm(X)}" cy="{fm(Y)}" r="{fm(R+3)}" fill="#ddd6c6" stroke="{INK}" stroke-width="1.5"/><polygon points="{" ".join(pts)}" fill="{INK}"/>')

    def sarcophagus(self, x, y, w=0.9, h=1.9):
        self.box(x, y, w, h, "#d6cdb8", 2, rx=4)
        self.box(x + 0.15, y + 0.15, w - 0.3, h - 0.3, "none", 1, rx=3)

    def bell(self, x, y, r=0.7, label=None):
        X, Y, R = x * C, y * C, r * C
        self.post.append(f'<circle cx="{fm(X)}" cy="{fm(Y)}" r="{fm(R)}" fill="#c9a24a" stroke="{INK}" stroke-width="2.5"/><circle cx="{fm(X)}" cy="{fm(Y)}" r="{fm(R*0.62)}" fill="none" stroke="{INK}" stroke-width="1.2"/><circle cx="{fm(X)}" cy="{fm(Y)}" r="{fm(R*0.22)}" fill="{INK}"/>')

    def well(self, x, y, r=0.6, dark="#3b4a4c"):
        self.post.append(f'<circle cx="{fm(x*C)}" cy="{fm(y*C)}" r="{fm(r*C)}" fill="#cfc6b2" stroke="{INK}" stroke-width="2"/><circle cx="{fm(x*C)}" cy="{fm(y*C)}" r="{fm(r*C*0.65)}" fill="{dark}"/>')

    def fire(self, x, y, r=0.35):
        X, Y, R = x * C, y * C, r * C
        self.post.append(f'<circle cx="{fm(X)}" cy="{fm(Y)}" r="{fm(R+4)}" fill="#7a6a58" stroke="{INK}" stroke-width="1.5"/><circle cx="{fm(X)}" cy="{fm(Y)}" r="{fm(R)}" fill="#e8892f"/><circle cx="{fm(X)}" cy="{fm(Y)}" r="{fm(R*0.5)}" fill="#f7d35a"/>')

    def body(self, x, y):
        X, Y = x * C, y * C
        self.post.append(f'<g stroke="#7a1f14" stroke-width="3" stroke-linecap="round"><line x1="{fm(X-9)}" y1="{fm(Y-9)}" x2="{fm(X+9)}" y2="{fm(Y+9)}"/><line x1="{fm(X+9)}" y1="{fm(Y-9)}" x2="{fm(X-9)}" y2="{fm(Y+9)}"/></g><circle cx="{fm(X+5)}" cy="{fm(Y+7)}" r="6" fill="#7a1f14" opacity=".35"/>')

    def rubble(self, x, y, w, h, seed, n=None):
        rnd = random.Random(seed)
        n = n or int(w * h * 7)
        g = []
        for _ in range(n):
            px, py = (x + rnd.random() * w) * C, (y + rnd.random() * h) * C
            s = rnd.uniform(2.5, 6.5)
            pts = " ".join(f"{fm(px+s*math.cos(a)*rnd.uniform(.6,1.2))},{fm(py+s*math.sin(a)*rnd.uniform(.6,1.2))}" for a in [0, 1.3, 2.6, 3.9, 5.2])
            g.append(f'<polygon points="{pts}" fill="#bfb39a" stroke="{INK}" stroke-width="1"/>')
        self.post.append("".join(g))

    def tracks(self, pts):
        P = [(x * C, y * C) for x, y in pts]
        d = "M" + " L".join(f"{fm(x)},{fm(y)}" for x, y in P)
        g = [f'<path d="{d}" fill="none" stroke="{WOOD}" stroke-width="15" stroke-dasharray="3 7" opacity=".9"/>',
             f'<path d="{d}" fill="none" stroke="{INK}" stroke-width="12"/>',
             f'<path d="{d}" fill="none" stroke="{FLOOR}" stroke-width="9"/>']
        self.post.append("".join(g))

    def deco_water(self, d_or_blob, fill=WATER, opacity=1.0):
        self.floordeco.append(f'<path d="{d_or_blob}" fill="{fill}" opacity="{opacity}" stroke="{WATER_D}" stroke-width="2"/>')

    def deco_blob(self, cx, cy, rx, ry, seed, fill, stroke=None, jit=0.15, opacity=1.0):
        st = f' stroke="{stroke}" stroke-width="2"' if stroke else ""
        self.floordeco.append(f'<path d="{smooth_path(blob_pts(cx*C, cy*C, rx*C, ry*C, seed, jit=jit))}" fill="{fill}" opacity="{opacity}"{st}/>')

    def deco_poly(self, pts, fill, stroke=None, sw=2, smooth=True, layer="floordeco"):
        P = [(x * C, y * C) for x, y in pts]
        d = smooth_path(P) if smooth else "M" + " L".join(f"{fm(x)},{fm(y)}" for x, y in P) + "Z"
        st = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
        getattr(self, layer).append(f'<path d="{d}" fill="{fill}"{st}/>')

    def planks(self, x1, y1, x2, y2, width=1.0, layer="post"):
        X1, Y1, X2, Y2 = x1 * C, y1 * C, x2 * C, y2 * C
        L = math.hypot(X2 - X1, Y2 - Y1)
        ang = math.degrees(math.atan2(Y2 - Y1, X2 - X1))
        W = width * C
        g = [f'<g transform="translate({fm(X1)},{fm(Y1)}) rotate({fm(ang)})">',
             f'<rect x="0" y="{fm(-W/2)}" width="{fm(L)}" height="{fm(W)}" fill="#b98a55" stroke="{INK}" stroke-width="2"/>']
        n = int(L / 9)
        for i in range(1, n):
            g.append(f'<line x1="{fm(L*i/n)}" y1="{fm(-W/2)}" x2="{fm(L*i/n)}" y2="{fm(W/2)}" stroke="{INK}" stroke-width="0.8" opacity=".7"/>')
        g.append("</g>")
        getattr(self, layer).append("".join(g))

    def rope_bridge(self, x1, y1, x2, y2):
        self.planks(x1, y1, x2, y2, 0.8)
        X1, Y1, X2, Y2 = x1 * C, y1 * C, x2 * C, y2 * C
        L = math.hypot(X2 - X1, Y2 - Y1)
        ang = math.degrees(math.atan2(Y2 - Y1, X2 - X1))
        self.post.append(f'<g transform="translate({fm(X1)},{fm(Y1)}) rotate({fm(ang)})"><line x1="-4" y1="-15" x2="{fm(L+4)}" y2="-15" stroke="{WOOD}" stroke-width="2.5"/><line x1="-4" y1="15" x2="{fm(L+4)}" y2="15" stroke="{WOOD}" stroke-width="2.5"/></g>')

    def tree(self, x, y, r, seed, dead=False):
        rnd = random.Random(seed)
        X, Y, R = x * C, y * C, r * C
        if dead:
            g = [f'<circle cx="{fm(X)}" cy="{fm(Y)}" r="{fm(R*0.25)}" fill="{WOOD}" stroke="{INK}" stroke-width="1.5"/>']
            for i in range(6):
                a = rnd.uniform(0, 6.28)
                g.append(f'<path d="M{fm(X)},{fm(Y)} q{fm(R*0.5*math.cos(a+0.4))},{fm(R*0.5*math.sin(a+0.4))} {fm(R*math.cos(a))},{fm(R*math.sin(a))}" stroke="{INK}" stroke-width="1.8" fill="none"/>')
            self.post.append("".join(g))
            return
        pts = blob_pts(X, Y, R, R, seed, n=14, jit=0.18)
        shade = rnd.choice(["#6f8a4a", "#7a9150", "#66804a"])
        self.post.append(f'<path d="{smooth_path(pts)}" fill="{shade}" stroke="{INK}" stroke-width="1.5" opacity=".95"/><circle cx="{fm(X-R*.25)}" cy="{fm(Y-R*.25)}" r="{fm(R*.35)}" fill="#a4b86f" opacity=".6"/>')

    def reeds(self, x, y, seed):
        rnd = random.Random(seed)
        X, Y = x * C, y * C
        g = []
        for _ in range(5):
            a = rnd.uniform(-0.6, 0.6)
            L = rnd.uniform(7, 12)
            g.append(f'<line x1="{fm(X)}" y1="{fm(Y)}" x2="{fm(X+L*math.sin(a))}" y2="{fm(Y-L*math.cos(a))}" stroke="#4d5e33" stroke-width="1.4"/>')
        self.post.append("".join(g))

    def rock(self, x, y, r, seed):
        pts = blob_pts(x * C, y * C, r * C, r * C * 0.8, seed, n=8, jit=0.25)
        self.post.append(f'<path d="{smooth_path(pts)}" fill="#a39a88" stroke="{INK}" stroke-width="1.5"/>')

    def tent(self, x, y, s=1.0):
        X, Y, S = x * C, y * C, s * C
        self.post.append(f'<polygon points="{fm(X)},{fm(Y-S*.55)} {fm(X+S*.6)},{fm(Y+S*.45)} {fm(X-S*.6)},{fm(Y+S*.45)}" fill="#a88c62" stroke="{INK}" stroke-width="1.8"/><line x1="{fm(X)}" y1="{fm(Y-S*.55)}" x2="{fm(X)}" y2="{fm(Y+S*.45)}" stroke="{INK}" stroke-width="1"/>')

    def cage(self, x, y, s=0.9):
        X, Y, S = (x - s / 2) * C, (y - s / 2) * C, s * C
        g = [f'<rect x="{fm(X)}" y="{fm(Y)}" width="{fm(S)}" height="{fm(S)}" fill="none" stroke="{INK}" stroke-width="2"/>']
        for i in range(1, 4):
            g.append(f'<line x1="{fm(X+S*i/4)}" y1="{fm(Y)}" x2="{fm(X+S*i/4)}" y2="{fm(Y+S)}" stroke="{INK}" stroke-width="1.2"/>')
        self.post.append("".join(g))

    def mask_pole(self, x, y):
        X, Y = x * C, y * C
        self.post.append(f'<circle cx="{fm(X)}" cy="{fm(Y)}" r="7" fill="#d9d4c8" stroke="{INK}" stroke-width="1.5"/><circle cx="{fm(X-2.5)}" cy="{fm(Y-1)}" r="1.4" fill="{INK}"/><circle cx="{fm(X+2.5)}" cy="{fm(Y-1)}" r="1.4" fill="{INK}"/>')

    def boat(self, x, y, ang=0, L=2.2):
        X, Y, Lp = x * C, y * C, L * C
        self.post.append(f'<g transform="translate({fm(X)},{fm(Y)}) rotate({ang})"><path d="M{fm(-Lp/2)},0 Q{fm(-Lp/4)},-13 {fm(Lp/2)},0 Q{fm(-Lp/4)},13 {fm(-Lp/2)},0Z" fill="#9b6a3a" stroke="{INK}" stroke-width="1.8"/><line x1="{fm(-Lp/4)}" y1="-7" x2="{fm(-Lp/4)}" y2="7" stroke="{INK}"/><line x1="{fm(Lp/8)}" y1="-6" x2="{fm(Lp/8)}" y2="6" stroke="{INK}"/></g>')

    def wheel(self, x, y, w, h):
        X, Y, W, H = x * C, y * C, w * C, h * C
        g = [f'<rect x="{fm(X)}" y="{fm(Y)}" width="{fm(W)}" height="{fm(H)}" fill="#9b6a3a" stroke="{INK}" stroke-width="2"/>']
        n = int(h * 3)
        for i in range(1, n):
            g.append(f'<line x1="{fm(X-5)}" y1="{fm(Y+H*i/n)}" x2="{fm(X+W+5)}" y2="{fm(Y+H*i/n)}" stroke="{INK}" stroke-width="2"/>')
        self.post.append("".join(g))

    def text(self, x, y, t, size=13, italic=True, anchor="middle", color=INK, rot=0, weight="normal"):
        st = ' font-style="italic"' if italic else ""
        tr = f' transform="rotate({rot} {fm(x*C)} {fm(y*C)})"' if rot else ""
        self.labels.append(f'<text x="{fm(x*C)}" y="{fm(y*C)}" font-family={FONT!r} font-size="{size}" font-weight="{weight}"{st} text-anchor="{anchor}" fill="{color}" stroke="{FLOOR}" stroke-width="3.5" paint-order="stroke" stroke-linejoin="round"{tr}>{esc(t)}</text>')

    def label(self, t, x, y):
        X, Y = x * C, y * C
        w = 12 + 8.5 * len(t)
        self.labels.append(f'<rect x="{fm(X-w/2)}" y="{fm(Y-11)}" width="{fm(w)}" height="22" rx="11" fill="{INK}" stroke="{FLOOR}" stroke-width="2"/><text x="{fm(X)}" y="{fm(Y+5)}" font-family={FONT!r} font-size="14" font-weight="bold" text-anchor="middle" fill="#f6edd6">{esc(t)}</text>')

    # --- render ---
    def render(self, legend=None):
        M, HEAD, FOOT = 40, 92, 58
        W, H = self.cols * C, self.rows * C
        TW, TH = W + 2 * M, H + HEAD + FOOT
        o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{TW}" height="{TH}" viewBox="0 0 {TW} {TH}">',
             "<defs>",
             f'<pattern id="hatch" width="10" height="10" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="10" height="10" fill="#e4d6b3"/><line x1="0" y1="0" x2="0" y2="10" stroke="{INK}" stroke-width="1.6" opacity=".45"/></pattern>',
             f'<marker id="arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10z" fill="{INK}"/></marker>',
             '<clipPath id="fclip">' + "".join(self.floors) + "</clipPath>",
             f'<clipPath id="mclip"><rect width="{W}" height="{H}"/></clipPath>',
             "</defs>",
             f'<rect width="{TW}" height="{TH}" fill="{PAPER}"/>',
             f'<rect x="8" y="8" width="{TW-16}" height="{TH-16}" fill="none" stroke="{INK}" stroke-width="3"/>',
             f'<rect x="14" y="14" width="{TW-28}" height="{TH-28}" fill="none" stroke="{INK}" stroke-width="1"/>',
             f'<text x="{TW/2}" y="52" font-family={FONT!r} font-size="30" font-weight="bold" text-anchor="middle" fill="{INK}" letter-spacing="1">{esc(self.title)}</text>',
             f'<text x="{TW/2}" y="76" font-family={FONT!r} font-size="15" font-style="italic" text-anchor="middle" fill="{INK}">{esc(self.subtitle)}</text>',
             f'<g transform="translate({M},{HEAD})"><g clip-path="url(#mclip)">']
        if self.outdoor:
            o.append(f'<rect width="{W}" height="{H}" fill="{self.base or GRASS}"/>')
        else:
            o.append(f'<rect width="{W}" height="{H}" fill="url(#hatch)"/>')
        o += self.terrain
        o.append(f'<g fill="{INK}" stroke="{INK}" stroke-width="10" stroke-linejoin="round">' + "".join(self.floors) + "</g>")
        o.append(f'<g fill="{FLOOR}">' + "".join(self.floors) + "</g>")
        o += self.floordeco
        grid = "".join(f"M{x*C},0 V{H} " for x in range(self.cols + 1)) + "".join(f"M0,{y*C} H{W} " for y in range(self.rows + 1))
        if self.outdoor:
            o.append(f'<path d="{grid}" stroke="{GRIDC}" stroke-width="0.8" opacity=".28" fill="none"/>')
        o.append(f'<g clip-path="url(#fclip)"><path d="{grid}" stroke="{GRIDC}" stroke-width="0.8" opacity=".55" fill="none"/></g>')
        o += self.post
        o += self.labels
        o.append("</g>")
        o.append(f'<rect width="{W}" height="{H}" fill="none" stroke="{INK}" stroke-width="2"/></g>')
        # scala
        sy = HEAD + H + 32
        o.append(f'<g transform="translate({M},{sy})">')
        for i in range(5):
            o.append(f'<rect x="{i*C}" y="-6" width="{C}" height="8" fill="{INK if i%2==0 else FLOOR}" stroke="{INK}"/>')
        o.append(f'<text x="0" y="18" font-family={FONT!r} font-size="12" fill="{INK}">0</text><text x="{5*C}" y="18" font-family={FONT!r} font-size="12" text-anchor="middle" fill="{INK}">7,5 m</text>')
        o.append(f'<text x="{5*C+60}" y="2" font-family={FONT!r} font-size="13" font-style="italic" fill="{INK}">1 quadretto = 1,5 m (5 ft)</text></g>')
        if legend:
            o.append(f'<text x="{TW-M}" y="{sy+2}" font-family={FONT!r} font-size="12.5" text-anchor="end" fill="{INK}">{esc(legend)}</text>')
        # rosa dei venti
        cx, cy = TW - M - 26, 50
        o.append(f'<g transform="translate({cx},{cy})"><polygon points="0,-22 6,0 0,22 -6,0" fill="{INK}"/><polygon points="0,-22 6,0 0,0" fill="{FLOOR}" stroke="{INK}"/><text x="0" y="-26" font-family={FONT!r} font-size="13" font-weight="bold" text-anchor="middle" fill="{INK}">N</text></g>')
        o.append("</svg>")
        return "\n".join(o)


# ---------------------------------------------------------------------------
#  1. CAMPANILE
# ---------------------------------------------------------------------------
def mappa_campanile():
    m = Map("03_campanile", 40, 13, "Il Campanile di Brumaria", "Atto I · tre livelli della torre campanaria")
    # Piano terra (A)
    m.rect(4, 3, 7, 7)
    m.rect(6, 10, 3, 2)          # gradini del portone
    m.rect(1, 3, 3, 3)           # sacrestia
    m.rect(1, 7, 3, 3)           # alloggio di Tobia
    m.door(4, 4.5, "v")
    m.door(4, 8.5, "v", "locked")
    m.door(7.5, 10, "h")
    m.spiral(10, 4, 0.85)
    m.well(7.5, 7.3, 0.5, "#7fa7a8")
    m.post.append(f'<circle cx="{7.5*C}" cy="{5.3*C}" r="{1.1*C}" fill="none" stroke="{INK}" stroke-width="1.5" stroke-dasharray="5 4"/>')
    m.table(1.3, 3.3, 1.2, 0.6); m.chest(3.3, 5.4); m.crate(1.5, 5.4, 0.5)
    m.bed(1.2, 7.2); m.table(2.6, 8.9, 1.1, 0.7); m.barrel(3.5, 7.4, 0.25)
    m.stairs(6, 10.5, 3, 1.5, "n")
    m.text(6.5, 1.6, "PIANO TERRA", 15, False, weight="bold")
    m.label("A1", 7.5, 11.4); m.label("A2", 5.4, 8.6); m.label("A3", 2.5, 4.3)
    m.label("A4", 9.0, 5.4); m.label("A5", 2.0, 9.4)
    m.text(7.5, 3.9, "apertura nel soffitto", 10)
    # Sala delle corde (B)
    m.rect(17, 3, 7, 7)
    m.rect(14, 5, 3, 3)          # ripostiglio
    m.rect(24, 5, 2, 3)          # balcone
    m.door(17, 6.5, "v")
    m.door(24, 6.5, "v")
    m.spiral(23, 4, 0.85)
    m.ladder(18.15, 3.9, 0.7, 1.2)
    for (x, y) in [(19.6, 5.6), (21.4, 5.6), (19.6, 7.4), (21.4, 7.4), (20.5, 6.5)]:
        m.post.append(f'<circle cx="{x*C}" cy="{y*C}" r="5" fill="#c9a24a" stroke="{INK}" stroke-width="1.5"/>')
    m.post.append(f'<circle cx="{20.5*C}" cy="{6.5*C}" r="{1.6*C}" fill="none" stroke="{INK}" stroke-width="1.5" stroke-dasharray="5 4"/>')
    m.barrel(14.5, 5.5); m.barrel(15.2, 5.4); m.crate(16.3, 7.4); m.crate(14.6, 7.4, 0.5)
    m.arch_open(26, 5, 26, 8)
    m.text(20, 1.6, "SALA DELLE CORDE  (+9 m)", 15, False, weight="bold")
    m.label("B1", 22.4, 5.5); m.label("B2", 20.5, 9.2); m.label("B3", 15.5, 6.5)
    m.label("B4", 18.5, 2.4); m.label("B5", 25.0, 9.0)
    m.text(20.5, 3.6, "corde recise", 10)
    # Cella campanaria (C)
    m.rect(30, 3, 7, 7)
    for (x1, y1, x2, y2) in [(31, 3, 36, 3), (31, 10, 36, 10), (30, 4, 30, 9), (37, 4, 37, 9)]:
        m.arch_open(x1, y1, x2, y2)
    for (x, y) in [(30.3, 3.3), (36.7, 3.3), (30.3, 9.7), (36.7, 9.7), (33.5, 3.3), (33.5, 9.7), (30.3, 6.5), (36.7, 6.5)]:
        m.pillar(x, y, 0.3, True)
    m.bell(33.5, 4.5, 0.7); m.bell(33.5, 8.5, 0.7); m.bell(31.6, 6.5, 0.7); m.bell(35.4, 6.5, 0.7)
    m.bell(33.5, 6.5, 1.05)
    m.post.append(f'<rect x="{31*C}" y="{3.9*C}" width="{0.9*C}" height="{0.9*C}" fill="none" stroke="{INK}" stroke-width="2"/><line x1="{31*C}" y1="{3.9*C}" x2="{31.9*C}" y2="{4.8*C}" stroke="{INK}"/>')
    m.body(35.5, 8.7)
    m.text(33.5, 1.6, "CELLA CAMPANARIA  (+18 m)", 15, False, weight="bold")
    m.label("C1", 33.5, 11.0); m.label("C2", 36.0, 11.0); m.label("C3", 38.4, 6.5); m.label("C4", 31.4, 5.4)
    m.text(33.5, 12.3, "Aurora (N) · Vespro (E) · Lucia (O) · Ombra (S) · Madre Nona (centro)", 11)
    return m.render("A4/B1: scala a chiocciola · B4/C4: botola e scala a pioli · ● porta chiusa a chiave")


# ---------------------------------------------------------------------------
#  2. MULINO DELLE PALUDI
# ---------------------------------------------------------------------------
def mappa_mulino():
    m = Map("04_mulino", 34, 24, "Il Mulino della Palude Lenta", "Atto II · la voce «Aurora» (acqua)", outdoor=True, base=SWAMP)
    # canale profondo e gora
    m.terr(f'<path d="{smooth_path([(25.2*C,-1*C),(27.8*C,-1*C),(28.4*C,6*C),(30.6*C,8*C),(29.6*C,11.5*C),(28.6*C,16*C),(29.2*C,25*C),(26*C,25*C),(25.6*C,15*C),(24.8*C,10*C),(24.6*C,5*C)])}" fill="{WATER_D}"/>')
    # pozze
    rnd = random.Random(7)
    for i in range(14):
        m.terr_blob(rnd.uniform(1, 33), rnd.uniform(1, 23), rnd.uniform(1, 2.6), rnd.uniform(0.7, 1.6), 100 + i, WATER, 0.25)
    # isole
    m.terr_blob(8, 18, 4.6, 3.0, 11, MUD, 0.12, INK)
    m.terr_blob(7, 6, 4.6, 3.1, 12, MUD, 0.12, INK)
    m.terr_blob(19, 8.2, 6.6, 5.0, 13, MUD, 0.10, INK)
    m.terr_blob(31.2, 18.6, 2.5, 2.4, 14, MUD, 0.12, INK)
    m.terr_blob(19, 8.2, 5.6, 4.0, 15, GRASS, 0.12)
    m.terr_blob(8, 18, 3.5, 2.1, 16, GRASS, 0.15)
    # passerelle
    m.planks(-0.5, 21.6, 4.4, 19.4, 1.0, "terrain")
    m.planks(11.4, 16.6, 14.6, 11.6, 1.0, "terrain")
    m.planks(6.0, 15.4, 6.6, 8.6, 1.0, "terrain")
    m.planks(11.0, 5.4, 13.8, 6.4, 1.0, "terrain")
    m.planks(21.4, 12.3, 29.4, 17.2, 0.6, "terrain")   # tronco caduto
    # edificio del mulino
    m.rect(16, 5, 6, 6)
    m.rect(22, 5, 3, 6)
    m.wheel(25.15, 6.3, 1.1, 3.4)
    m.post.append(f'<path d="M{22*C},{5*C} V{7.6*C} M{22*C},{8.4*C} V{11*C}" stroke="{INK}" stroke-width="6"/>')
    m.door(22, 8, "v")
    m.door(18.5, 11, "h")
    m.door(16, 6.5, "v")
    m.post.append(f'<circle cx="{19*C}" cy="{8*C}" r="{1.2*C}" fill="#cfc6b2" stroke="{INK}" stroke-width="2"/><circle cx="{19*C}" cy="{8*C}" r="5" fill="{INK}"/>')
    m.post.append(f'<line x1="{19*C}" y1="{8*C}" x2="{25.2*C}" y2="{8*C}" stroke="{WOOD}" stroke-width="5"/>')
    m.crate(16.6, 5.6); m.crate(17.3, 5.6, 0.5); m.barrel(21.4, 10.4); m.barrel(16.6, 10.4)
    m.bed(22.4, 5.3, 1.2, 1.6); m.table(23.5, 9.3, 1.1, 1.2)
    m.post.append(f'<circle cx="{23.3*C}" cy="{7.6*C}" r="{0.5*C}" fill="#3d3a2b" stroke="{INK}" stroke-width="1.5"/>')  # calderone
    m.post.append(f'<path d="M{25.7*C},{8*C} C{26.8*C},{8.3*C} {27.4*C},{9.2*C} {27.6*C},{9.8*C}" stroke="#555" stroke-width="2.5" fill="none" stroke-dasharray="4 2"/>')  # catena
    m.post.append(f'<circle cx="{27.6*C}" cy="{9.9*C}" r="5" fill="#c9a24a" stroke="{INK}" stroke-width="1.5"/>')
    # villaggio bullywug
    for (x, y) in [(5, 5), (8.2, 4.6), (6.4, 7.4), (9.4, 7.0)]:
        m.post.append(f'<circle cx="{x*C}" cy="{y*C}" r="{0.75*C}" fill="#8f7d55" stroke="{INK}" stroke-width="1.8"/><circle cx="{x*C}" cy="{y*C}" r="4" fill="{INK}"/>')
    m.post.append(f'<path d="M{2.8*C},{6.8*C} q{1*C},{1.4*C} {2.2*C},{1.6*C}" stroke="{WOOD}" stroke-width="3" fill="none" stroke-dasharray="2 4"/>')
    m.fire(7.3, 6.0, 0.3)
    # isolotto delle offerte
    m.tree(31.2, 18.4, 1.2, 4, dead=True)
    for (x, y) in [(30.0, 17.4), (32.4, 19.4), (30.6, 19.8)]:
        m.cage(x, y, 0.6)
    # alberi e canne
    for i, (x, y, r) in enumerate([(4.2, 17, .9), (11, 19.5, .8), (14.2, 4.4, 1.0), (23.6, 12.2, .9), (13.2, 10.8, .8), (3.4, 8.2, .7), (10.6, 3.7, .7), (1.5, 12, 1.0), (15, 18, 1.1), (21, 20.5, 1.2), (32, 3, 1.2), (31.5, 12.5, .9), (12.4, 22.4, 1.0)]):
        m.tree(x, y, r, 300 + i, dead=(i % 4 == 0))
    rnd = random.Random(21)
    for i in range(70):
        x, y = rnd.uniform(0.5, 33.5), rnd.uniform(0.5, 23.5)
        if 15 < x < 25.5 and 4.5 < y < 11.5:
            continue
        if 24.5 < x < 30.5:
            continue
        m.reeds(x, y, 500 + i)
    m.text(26.9, 2.5, "canale del mulino", 12, rot=88)
    m.text(26.8, 21.8, "acqua profonda", 11, rot=88)
    m.text(17, 22.6, "acqua bassa e fango: terreno difficile", 12)
    m.text(2.6, 22.9, "da Brumaria", 11)
    m.label("M1", 8, 18.2); m.label("M2", 7.2, 3.4); m.label("M3", 18.0, 9.7)
    m.label("M4", 23.5, 6.3); m.label("M5", 28.9, 10.9); m.label("M6", 31.3, 21.6)
    m.label("M7", 18.6, 14.3)
    return m.render("Passerelle: 1,5 m di larghezza · Acqua bassa: terreno difficile · Canale: nuoto (Atletica CD 12)")


# ---------------------------------------------------------------------------
#  3. MINIERA DI FERROCUPO
# ---------------------------------------------------------------------------
def mappa_miniera():
    m = Map("05_miniera", 40, 30, "La Miniera di Ferrocupo", "Atto II · la voce «Vespro» (terra)")
    m.poly([(0, 26.5), (3, 25.8), (8, 26.2), (13, 27), (15, 30), (0, 30)])      # pendio esterno
    m.rect(4, 22, 2, 4.6)                     # galleria d'ingresso
    m.rect(2, 17, 6, 5)                       # F2 posto di guardia
    m.rect(8, 18, 14, 2)                      # galleria dei carrelli
    m.rect(20, 11.5, 2, 8.5)
    m.rect(13, 20, 1, 1); m.rect(11, 21, 5, 4)  # F3 dormitorio
    m.cave(22, 9, 5.6, 3.8, 31)               # F5 baratro
    m.rect(24.5, 5.2, 3, 2.2)
    m.cave(31, 5, 5.6, 3.6, 32)               # F6 accampamento
    m.rect(34, 7.5, 2, 5.2)
    m.cave(35, 15, 3.6, 3.0, 33)              # F7 tana di Ugo
    m.rect(4, 8.5, 2, 8.6)                    # verso la galleria allagata
    m.cave(6, 6, 3.6, 2.8, 34)                # F8
    m.cave(12.5, 4.6, 3.2, 2.6, 35)           # F9 vena profonda
    m.rect(8.8, 4.8, 1.6, 1.0)                # fessura
    m.poly([(15, 6), (18.6, 6.6), (18.6, 7.5), (15, 6.9)])   # cunicolo stretto
    # dettagli
    m.door(5, 22, "h", "arch")
    m.door(13.5, 21, "h")
    m.door(8, 19, "v", "arch")
    m.tracks([(5, 25.5), (5, 22.5), (6.5, 19), (21, 19), (21, 12.5)])
    m.box(15.6, 18.25, 1.3, 1.5, "#8a6a45")   # carrello
    m.post.append(f'<text x="{16.25*C}" y="{17.7*C}" font-family={FONT!r} font-size="10" text-anchor="middle" fill="{INK}">carrello</text>')
    for x in (10, 13, 16, 19):
        m.pillar(x, 18.12, 0.12, True); m.pillar(x, 19.88, 0.12, True)
    m.table(3, 18, 2, 1); m.barrel(7.3, 17.6); m.crate(7.4, 21.4); m.fire(4.8, 20.4, 0.3)
    m.bed(11.3, 21.3, 0.8, 1.5); m.bed(12.4, 21.3, 0.8, 1.5); m.bed(14.9, 23.2, 0.8, 1.5)
    m.cage(14.8, 21.8, 1.0); m.crate(11.8, 24.3, 0.5)
    # baratro
    m.deco_poly([(16, 8.2), (19, 8.6), (22, 8.1), (25, 8.9), (28.2, 8.6), (28.2, 10.2), (25, 10.6), (22, 9.9), (19, 10.5), (16, 10.1)], "#1d1712", smooth=True)
    m.rope_bridge(22.6, 7.2, 22.6, 11.6)
    m.text(18.0, 7.7, "baratro (profondo 18 m)", 11)
    # accampamento
    m.fire(31, 5, 0.45)
    for (x, y) in [(28.2, 3.4), (33.6, 3.0), (34.4, 6.8), (27.6, 6.6)]:
        m.tent(x, y, 1.1)
    m.crate(30.2, 7.6); m.crate(31.1, 7.8, 0.5); m.barrel(29.4, 2.4); m.cage(32.2, 2.1, 0.9)
    m.text(32.2, 1.1, "Fulvio", 10)
    # tana di Ugo
    m.box(36.3, 13.6, 1.4, 1.2, "#8a6a45"); m.text(37, 13.3, "trono", 10)
    m.chest(37.3, 16.6); m.chest(36.5, 17.2); m.bed(32.6, 14.4, 1.2, 1.8); m.fire(34.6, 16.2, 0.3)
    m.post.append(f'<circle cx="{33.4*C}" cy="{17.0*C}" r="9" fill="#9d8d70" stroke="{INK}"/>')
    # galleria allagata
    m.deco_blob(6.2, 6.4, 3.0, 2.0, 41, WATER, WATER_D, 0.2)
    m.deco_blob(5, 11.5, 0.9, 2.2, 42, WATER, WATER_D, 0.2)
    for (x, y) in [(4.2, 4.6), (7.8, 4.4), (8.4, 7.6), (3.6, 7.2)]:
        m.rock(x, y, 0.35, int(x * 10 + y))
    # vena profonda
    for i, (x, y) in enumerate([(11, 3.4), (12.8, 2.8), (14.3, 3.8), (14.6, 5.6), (10.6, 5.8)]):
        m.post.append(f'<polygon points="{x*C},{y*C-9} {x*C+5},{y*C} {x*C},{y*C+9} {x*C-5},{y*C}" fill="#7fb7c9" stroke="{INK}" stroke-width="1.2"/>')
    m.post.append(f'<circle cx="{12.6*C}" cy="{4.9*C}" r="{0.6*C}" fill="#8a6142" stroke="{INK}" stroke-width="1.5" opacity=".9"/>')
    m.post.append(f'<circle cx="{12.6*C}" cy="{4.9*C}" r="5" fill="#c9a24a" stroke="{INK}" stroke-width="1.2"/>')
    m.rubble(17.0, 6.0, 1.3, 1.1, 44, 6)
    m.rubble(20.4, 14.5, 1.4, 1.6, 45)
    m.rubble(8.5, 23.8, 3, 2, 46, 10)
    # etichette
    m.label("F1", 7.3, 27.9); m.label("F2", 5, 18.0); m.label("F3", 13.5, 23.9)
    m.label("F4", 12.0, 19.0); m.label("F5", 25.5, 12.0); m.label("F6", 31, 7.0)
    m.label("F7", 35, 18.6); m.label("F8", 5, 9.0); m.label("F9", 12.5, 6.9)
    m.text(17, 5.4, "cunicolo (Taglia Piccola o", 10); m.text(17, 5.85, "Acrobazia CD 12)", 10)
    m.text(5, 15, "acqua alla vita", 10, rot=-90)
    return m.render("Rotaie: il carrello scende da F4 verso F2 · La galleria F4 è in leggera discesa verso ovest")


# ---------------------------------------------------------------------------
#  4. ABBAZIA DI SAN VELIO
# ---------------------------------------------------------------------------
def mappa_abbazia():
    m = Map("06_abbazia", 44, 23, "L'Abbazia di San Velio", "Atto II · la voce «Lucia» (ossa)")
    # chiesa
    m.rect(2, 4, 7, 15)
    m.circle(5.5, 4.2, 3.5)
    m.rect(2, 20, 7, 2.6)            # sagrato
    m.rect(5, 19, 1, 1); m.door(5.5, 19.5, "h")
    for y in (7, 10, 13, 16):
        m.pillar(3.8, y, 0.32); m.pillar(7.2, y, 0.32)
    m.altar(4.6, 2.2, 1.8, 0.9)
    m.stairs(7.0, 4.3, 1.4, 1.8, "s")
    for i in range(4):
        m.table(3.0 + (i % 2) * 2.5, 8.2 + (i // 2) * 3.2, 0.5, 2.0) if False else None
    for yy in (8, 9.2, 10.4, 11.6, 14, 15.2):
        m.box(4.3, yy, 0.7, 0.35, "#b48a58", 1); m.box(5.9, yy, 0.7, 0.35, "#b48a58", 1)
    m.rubble(2.3, 16.5, 2.2, 2.2, 61)
    # chiostro
    m.rect(10, 8, 9, 9)
    m.gap(9, 12, "v")
    m.deco_poly([(12, 10), (17, 10), (17, 15), (12, 15)], GRASS, INK, 1.5, smooth=False)
    for x in (12, 13.25, 14.5, 15.75, 17):
        m.pillar(x, 10, 0.18); m.pillar(x, 15, 0.18)
    for y in (11.25, 12.5, 13.75):
        m.pillar(12, y, 0.18); m.pillar(17, y, 0.18)
    m.well(14.5, 12.5, 0.6)
    m.tree(13, 14.2, 0.45, 70, dead=True)
    # refettorio, dormitorio
    m.rect(20, 8, 5, 4); m.gap(19, 9, "v")
    m.table(21, 9.2, 3, 0.8); m.box(21, 8.6, 3, 0.35, "#b48a58", 1); m.box(21, 10.2, 3, 0.35, "#b48a58", 1)
    m.rect(20, 13, 5, 4); m.gap(19, 15, "v")
    for x in (20.3, 21.5, 22.7, 23.9):
        m.bed(x, 13.3, 0.75, 1.4)
    m.rubble(21, 15.2, 3.6, 1.5, 62)
    # sala capitolare / biblioteca
    m.rect(10, 3, 9, 4); m.gap(14, 7, "h")
    for x in (10.3, 12.3, 14.3, 16.3):
        m.box(x, 3.25, 1.6, 0.4, "#9b6a3a", 1)
    m.table(13, 4.6, 3, 1)
    # campanile in rovina
    m.rect(20, 3, 4, 4); m.gap(19, 4, "v")
    m.rubble(20.5, 3.5, 3, 3, 63, 12)
    m.post.append(f'<circle cx="{22*C}" cy="{5*C}" r="{1.2*C}" fill="none" stroke="{INK}" stroke-width="1.5" stroke-dasharray="4 3"/>')
    m.text(14.5, 1.6, "LIVELLO SUPERIORE", 15, False, weight="bold")
    # --- CRIPTA ---
    ox = 0
    m.rect(29, 2, 4, 3); m.stairs(29.3, 2.2, 1.4, 2.6, "n")
    m.rect(30, 5, 2, 4)
    m.rect(29, 9, 8, 5)                                  # ossario
    for x in range(30, 37):
        m.post.append(f'<rect x="{x*C+4}" y="{9*C+3}" width="{C-8}" height="10" fill="#e9e1cc" stroke="{INK}" stroke-width="1"/>')
        m.post.append(f'<rect x="{x*C+4}" y="{14*C-13}" width="{C-8}" height="10" fill="#e9e1cc" stroke="{INK}" stroke-width="1"/>')
    m.statue(31, 11.5); m.statue(33, 11.5); m.statue(35, 11.5)
    m.gap(32, 14, "h")
    m.rect(29, 15, 8, 5)                                 # sala dei sarcofagi
    for x in (29.5, 31.3, 33.1, 34.9):
        m.sarcophagus(x, 15.5, 0.9, 1.8)
    m.sarcophagus(30.4, 17.8, 1.8, 0.9); m.sarcophagus(33.6, 17.8, 1.8, 0.9)
    m.gap(37, 11, "v", "sealed")
    m.gap(37, 18, "v", "secret")
    m.rect(38, 9, 5, 11)                                 # tomba dell'abate
    m.sarcophagus(39.9, 12.5, 1.2, 2.4)
    m.altar(39.7, 9.4, 1.6, 0.8)
    m.post.append(f'<rect x="{40.2*C}" y="{9.55*C}" width="12" height="9" fill="#c9a24a" stroke="{INK}"/>')  # carillon
    for (x, y) in [(38.5, 10.5), (42.5, 10.5), (38.5, 17), (42.5, 17)]:
        m.post.append(f'<circle cx="{x*C}" cy="{y*C}" r="6" fill="#c4c9ff" opacity=".7" stroke="{INK}"/>')
    m.pillar(39, 15.5, 0.3); m.pillar(42, 15.5, 0.3); m.pillar(39, 18.5, 0.3); m.pillar(42, 18.5, 0.3)
    m.text(35.5, 1.0, "CRIPTA  (–6 m)", 15, False, weight="bold")
    m.text(31.0, 6.2, "da V3", 10)
    # etichette
    m.label("V1", 5.5, 21.3); m.label("V2", 5.5, 13.3); m.label("V3", 5.5, 1.3)
    m.label("V4", 14.5, 16.3); m.label("V5", 22.5, 11.4); m.label("V6", 22.5, 16.4)
    m.label("V7", 14.5, 6.4); m.label("V8", 22, 2.3); m.label("V9", 31, 3.6)
    m.label("V10", 33, 13.0); m.label("V11", 33, 19.4); m.label("V12", 40.5, 19.0)
    return m.render("≡ porta sigillata (enigma del Coro Muto) · S porta segreta · ✶ statue dei Tre Santi")


# ---------------------------------------------------------------------------
#  5. ISOLA DEL FONDITORE
# ---------------------------------------------------------------------------
def mappa_isola():
    m = Map("07_isola", 36, 28, "L'Isola del Fonditore", "Atto III · la Voce Madre (fuoco) e il Pozzo della Bruma", outdoor=True, base=WATER)
    rnd = random.Random(9)
    for i in range(30):   # increspature
        x, y = rnd.uniform(0, 36) * C, rnd.uniform(0, 28) * C
        m.terr(f'<path d="M{fm(x)},{fm(y)} q8,-5 16,0 q8,5 16,0" stroke="{WATER_D}" stroke-width="1.5" fill="none" opacity=".6"/>')
    m.terr_blob(19, 14, 13.4, 10.6, 81, "#b6ab8c", 0.09, INK, 2.5)
    m.terr_blob(19, 14, 12.2, 9.4, 82, "#bfc28f", 0.10)
    # banchi di bruma
    for i in range(10):
        m.terr_blob(rnd.uniform(0, 36), rnd.uniform(0, 28), rnd.uniform(2, 4), rnd.uniform(1, 2), 90 + i, "#ffffff", 0.3)
    m.terrain = [t.replace('fill="#ffffff"', 'fill="#ffffff" opacity=".35"') for t in m.terrain]
    # pontile e sentiero
    m.planks(17, 21.6, 17, 27.8, 2.0, "terrain")
    m.terr(f'<path d="M{17*C},{21.8*C} C{17.4*C},{19.5*C} {16.6*C},{18*C} {17.5*C},{16.3*C}" stroke="#d8c8a0" stroke-width="{1.6*C}" fill="none" stroke-linecap="round"/>')
    m.terr(f'<path d="M{24*C},{15.5*C} C{26*C},{18*C} {28*C},{19*C} {29.5*C},{20.2*C}" stroke="#d8c8a0" stroke-width="{1.2*C}" fill="none" stroke-linecap="round"/>')
    for (x, y) in [(15.8, 21), (18.3, 20.2), (15.7, 18.8), (18.6, 18.0), (16.0, 17.0)]:
        m.mask_pole(x, y)
    m.boat(15.2, 24.6, 90); m.boat(19.0, 25.8, 85)
    # fonderia
    m.rect(12, 8, 12, 8)
    m.door(17.5, 16, "h"); m.door(18.5, 16, "h")
    m.rect(25, 8, 5, 4); m.gap(24, 9, "v", "locked")
    m.rect(25, 13, 5, 3); m.gap(24, 14, "v")
    m.circle(18, 4.8, 2.8)
    m.rect(17, 7.0, 2, 1.4); m.door(18, 8, "h")
    for x in (13, 15, 21, 23):
        m.box(x - 0.7, 8.15, 1.4, 1.0, "#6b4a35")
        m.post.append(f'<circle cx="{x*C}" cy="{8.7*C}" r="7" fill="#e8892f"/>')
    m.post.append(f'<circle cx="{18*C}" cy="{11*C}" r="{1.5*C}" fill="#5b4636" stroke="{INK}" stroke-width="3"/><circle cx="{18*C}" cy="{11*C}" r="{1.05*C}" fill="#f08a2c"/><circle cx="{18*C}" cy="{11*C}" r="{0.5*C}" fill="#ffd66b"/>')
    m.post.append(f'<rect x="{14.5*C}" y="{13.2*C}" width="{7*C}" height="{1.6*C}" fill="#2b241e" stroke="{INK}" stroke-width="2"/>')
    m.bell(18, 14.0, 0.62)
    for x in (12.5, 23.5):
        for y in (10.5, 13):
            m.pillar(x, y, 0.3, True)
    m.crate(13, 15.3); m.barrel(22.8, 15.4); m.barrel(23.4, 14.8, 0.25)
    m.bed(25.4, 8.4, 0.9, 1.6); m.table(27, 8.5, 2, 1); m.chest(29.3, 11.4); m.box(26.6, 10.6, 1.6, 0.5, "#9b6a3a", 1)
    for x in (25.6, 26.8, 28.0, 29.2):
        m.post.append(f'<path d="M{x*C},{13.4*C} a{0.5*C},{0.6*C} 0 0 1 {0.9*C},0 v{0.9*C} h-{0.9*C}z" fill="#c8b9a0" stroke="{INK}" stroke-width="1.2"/>')
    # pozzo della bruma
    m.well(18, 4.8, 1.1, "#c9d3d6")
    for i in range(8):
        a = 2 * math.pi * i / 8
        m.pillar(18 + 2.35 * math.cos(a), 4.8 + 2.35 * math.sin(a), 0.22)
    m.post.append(f'<circle cx="{18*C}" cy="{4.8*C}" r="{1.75*C}" fill="none" stroke="#6c7a8c" stroke-width="2" stroke-dasharray="2 5"/>')
    # faro
    m.rect(29, 19.5, 3, 3); m.door(29, 21, "v")
    m.spiral(30.5, 21, 0.9)
    # alberi morti e rocce
    for i, (x, y) in enumerate([(9, 10), (8.5, 17), (11, 20), (25, 5), (28, 7), (10, 6), (26, 21.5), (22.5, 21.5), (13, 3.8), (31, 13)]):
        m.tree(x, y, 0.8, 600 + i, dead=True)
    for i, (x, y) in enumerate([(7, 13), (31.5, 10), (21.5, 3.5), (12, 22.5), (24.5, 23)]):
        m.rock(x, y, 0.45, 700 + i)
    m.text(5.0, 25.8, "Lago Brumo", 18)
    m.text(17.0, 27.2, "verso Brumaria (3 km)", 11)
    m.label("I1", 18.8, 23.6); m.label("I2", 14.4, 19.6); m.label("I3", 18.0, 12.3)
    m.label("I4", 27.5, 11.0); m.label("I5", 27.5, 15.6); m.label("I6", 20.4, 2.4); m.label("I7", 30.5, 23.4)
    return m.render("Fonderia: crogiolo (fuoco), fossa di colata profonda 3 m · Il Pozzo emette Bruma: oscurità leggera entro 9 m")


# ---------------------------------------------------------------------------
#  6. BRUMARIA (pianta illustrata)
# ---------------------------------------------------------------------------
def pt_seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy or 1
    t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def point_in_poly(x, y, poly):
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def mappa_brumaria():
    W, H, M, HEAD, FOOT = 1120, 800, 40, 92, 40
    TW, TH = W + 2 * M, H + HEAD + FOOT
    shore = [(0, 250), (200, 232), (380, 262), (520, 300), (640, 352), (720, 432), (762, 540), (792, 660), (820, 800)]
    lake = shore + [(W, H), (W, 0), (0, 0)]
    palis = [(62, 246), (40, 400), (70, 560), (180, 690), (360, 755), (560, 735), (700, 690), (784, 640)]
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{TW}" height="{TH}" viewBox="0 0 {TW} {TH}">',
         f'<rect width="{TW}" height="{TH}" fill="{PAPER}"/>',
         f'<rect x="8" y="8" width="{TW-16}" height="{TH-16}" fill="none" stroke="{INK}" stroke-width="3"/>',
         f'<rect x="14" y="14" width="{TW-28}" height="{TH-28}" fill="none" stroke="{INK}" stroke-width="1"/>',
         f'<text x="{TW/2}" y="52" font-family={FONT!r} font-size="30" font-weight="bold" text-anchor="middle" fill="{INK}">Brumaria</text>',
         f'<text x="{TW/2}" y="76" font-family={FONT!r} font-size="15" font-style="italic" text-anchor="middle" fill="{INK}">borgo lacustre della Marca di Ventofondo · circa 900 anime</text>',
         f'<clipPath id="mc"><rect width="{W}" height="{H}"/></clipPath>',
         f'<g transform="translate({M},{HEAD})"><g clip-path="url(#mc)">',
         f'<rect width="{W}" height="{H}" fill="#d9d4a6"/>']
    rnd = random.Random(5)
    # campi fuori dalle mura
    for i in range(26):
        x, y = rnd.uniform(0, 800), rnd.uniform(300, 800)
        if point_in_poly(x, y, palis + [(784, 300), (62, 246)]) and not (y > 700):
            continue
        w, h = rnd.uniform(50, 110), rnd.uniform(30, 60)
        col = rnd.choice(["#cfc98f", "#c4c483", "#d6cf9b", "#bfc27d"])
        o.append(f'<g transform="rotate({rnd.uniform(-20,20):.1f} {x:.0f} {y:.0f})"><rect x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}" fill="{col}" stroke="#a09a62" stroke-width="1"/>' +
                 "".join(f'<line x1="{x:.0f}" y1="{y+k*6:.0f}" x2="{x+w:.0f}" y2="{y+k*6:.0f}" stroke="#a09a62" stroke-width=".6"/>' for k in range(1, int(h / 6))) + "</g>")
    # area interna al borgo
    o.append(f'<path d="{smooth_path(palis + [(784, 560), (740, 430), (640, 350), (380, 262), (200, 232)])}" fill="#e2d6b0"/>')
    # lago
    o.append(f'<path d="{smooth_path(shore, closed=False)} L{W},{H} L{W},0 L0,0 Z" fill="{WATER}" stroke="{WATER_D}" stroke-width="3"/>')
    for i in range(40):
        x, y = rnd.uniform(0, W), rnd.uniform(0, H)
        if point_in_poly(x, y, lake) and x > 260:
            o.append(f'<path d="M{x:.0f},{y:.0f} q8,-5 16,0 q8,5 16,0" stroke="{WATER_D}" stroke-width="1.4" fill="none" opacity=".6"/>')
    # strade
    streets = [
        [(42, 420), (200, 440), (316, 466)],
        [(360, 760), (380, 640), (400, 540)],
        [(470, 420), (560, 362), (600, 330)],
        [(490, 482), (620, 520), (720, 560)],
        [(330, 420), (262, 360), (200, 290)],
        [(380, 640), (560, 650), (690, 642)],
        [(200, 440), (230, 560), (300, 650), (380, 640)],
    ]
    for s in streets:
        d = "M" + " L".join(f"{x},{y}" for x, y in s)
        o.append(f'<path d="{d}" stroke="#8d7b55" stroke-width="22" fill="none" stroke-linecap="round" stroke-linejoin="round"/>')
    for s in streets:
        d = "M" + " L".join(f"{x},{y}" for x, y in s)
        o.append(f'<path d="{d}" stroke="#ead9ae" stroke-width="18" fill="none" stroke-linecap="round" stroke-linejoin="round"/>')
    # strada esterna verso sud e verso ovest
    o.append(f'<path d="M360,760 L350,800 M42,420 L0,430" stroke="#c8b78c" stroke-width="16" fill="none"/>')
    # piazza
    o.append(f'<ellipse cx="400" cy="470" rx="92" ry="72" fill="#e9dcb4" stroke="#8d7b55" stroke-width="2"/>')
    o.append(f'<ellipse cx="400" cy="470" rx="80" ry="60" fill="none" stroke="#b9a77d" stroke-width="1" stroke-dasharray="3 4"/>')
    key = {
        1: (383, 453, 34, 34, "Campanile"),
        2: (505, 425, 70, 55, "Tempio della Dama del Rintocco"),
        3: (288, 362, 82, 55, "Palazzo del Consiglio"),
        4: (296, 520, 72, 50, "Locanda «La Lanterna Annegata»"),
        5: (118, 458, 56, 40, "Fucina di Mastro Corrado"),
        6: (550, 382, 66, 42, "Mercato del Pesce"),
        7: (140, 290, 42, 32, "Casa di Nonna Pia"),
        8: (402, 686, 72, 40, "Caserma della Guardia"),
        11: (640, 568, 46, 36, "Casa dei Corvo (abbandonata)"),
    }
    occupied = [(x - 8, y - 8, w + 16, h + 16) for (x, y, w, h, _) in key.values()] + [(300, 390, 200, 160)]
    # case di riempimento
    houses = []
    for s in streets:
        for (ax, ay), (bx, by) in zip(s, s[1:]):
            L = math.hypot(bx - ax, by - ay)
            ang = math.atan2(by - ay, bx - ax)
            nx, ny = -math.sin(ang), math.cos(ang)
            t = 20
            while t < L - 15:
                for side in (-1, 1):
                    if rnd.random() < 0.15:
                        continue
                    off = rnd.uniform(26, 34)
                    cx = ax + math.cos(ang) * t + nx * off * side
                    cy = ay + math.sin(ang) * t + ny * off * side
                    w, h = rnd.uniform(22, 32), rnd.uniform(16, 22)
                    if point_in_poly(cx, cy, lake) or not point_in_poly(cx, cy, palis + [(784, 560), (740, 430), (640, 350), (380, 262), (200, 232)]):
                        continue
                    if any(rx - 4 < cx < rx + rw + 4 and ry - 4 < cy < ry + rh + 4 for rx, ry, rw, rh in occupied):
                        continue
                    if min(pt_seg_dist(cx, cy, *p, *q) for s2 in streets for p, q in zip(s2, s2[1:])) < 20:
                        continue
                    if any(math.hypot(cx - hx, cy - hy) < 24 for hx, hy, *_ in houses):
                        continue
                    houses.append((cx, cy, w, h, math.degrees(ang)))
                t += rnd.uniform(30, 40)
    for (cx, cy, w, h, a) in houses:
        col = rnd.choice(["#b9a07a", "#a88d68", "#c2aa82", "#9f8a6c"])
        o.append(f'<g transform="rotate({a:.1f} {cx:.1f} {cy:.1f})"><rect x="{cx-w/2:.1f}" y="{cy-h/2:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{col}" stroke="{INK}" stroke-width="1.2"/><line x1="{cx-w/2:.1f}" y1="{cy:.1f}" x2="{cx+w/2:.1f}" y2="{cy:.1f}" stroke="{INK}" stroke-width=".7"/></g>')
    # palizzata
    pd = smooth_path(palis, closed=False)
    o.append(f'<path d="{pd}" stroke="{WOOD}" stroke-width="9" fill="none"/><path d="{pd}" stroke="{INK}" stroke-width="9" fill="none" stroke-dasharray="2 5"/>')
    # porte
    for (gx, gy) in [(42, 420), (360, 757)]:
        o.append(f'<rect x="{gx-14}" y="{gy-14}" width="28" height="28" fill="#6b4a35" stroke="{INK}" stroke-width="2"/><rect x="{gx-6}" y="{gy-6}" width="12" height="12" fill="#ead9ae"/>')
    # molo lungo
    o.append(f'<line x1="598" y1="334" x2="720" y2="220" stroke="{INK}" stroke-width="16"/><line x1="598" y1="334" x2="720" y2="220" stroke="#b98a55" stroke-width="12"/>')
    for k in range(1, 18):
        x, y = 598 + 122 * k / 18, 334 - 114 * k / 18
        o.append(f'<line x1="{x-4:.0f}" y1="{y-5:.0f}" x2="{x+4:.0f}" y2="{y+5:.0f}" stroke="{INK}" stroke-width=".8"/>')
    for (bx, by, a) in [(690, 262, 40), (742, 228, 30), (650, 300, 50), (520, 280, -10)]:
        o.append(f'<g transform="translate({bx},{by}) rotate({a})"><path d="M-26,0 Q-12,-11 26,0 Q-12,11 -26,0Z" fill="#9b6a3a" stroke="{INK}" stroke-width="1.6"/></g>')
    # edifici principali
    for n, (x, y, w, h, name) in key.items():
        fill = INK if n == 1 else ("#7d8a96" if n == 11 else ROOF)
        o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{INK}" stroke-width="2"/>')
        if n != 1:
            o.append(f'<path d="M{x},{y} L{x+w/2},{y+h/2} L{x+w},{y} M{x},{y+h} L{x+w/2},{y+h/2} L{x+w},{y+h}" stroke="{INK}" stroke-width="1" fill="none" opacity=".6"/>')
    # cimitero dei senza tomba
    for i in range(14):
        x, y = 100 + rnd.uniform(-35, 35), 730 + rnd.uniform(-22, 22)
        o.append(f'<rect x="{x:.0f}" y="{y:.0f}" width="6" height="9" rx="3" fill="#cfc8b8" stroke="{INK}" stroke-width="1"/>')
    # alberi
    for i in range(45):
        x, y = rnd.uniform(0, 820), rnd.uniform(240, 800)
        if point_in_poly(x, y, lake) or point_in_poly(x, y, palis + [(784, 560), (740, 430), (640, 350), (380, 262), (200, 232)]):
            continue
        r = rnd.uniform(8, 14)
        o.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r:.0f}" fill="#7a9150" stroke="{INK}" stroke-width="1.2"/>')
    # numeri
    def num(n, x, y):
        o.append(f'<circle cx="{x}" cy="{y}" r="13" fill="#f6edd6" stroke="{INK}" stroke-width="2"/><text x="{x}" y="{y+5}" font-family={FONT!r} font-size="14" font-weight="bold" text-anchor="middle" fill="{INK}">{n}</text>')
    for n, (x, y, w, h, _) in key.items():
        num(n, x + w / 2, y - 14 if n != 1 else y + h + 16)
    num(9, 42, 390); num(10, 395, 772); num(12, 735, 205); num(13, 100, 700)
    o.append(f'<text x="436" y="420" font-family={FONT!r} font-size="13" font-style="italic" text-anchor="middle" fill="{INK}" stroke="#e9dcb4" stroke-width="3" paint-order="stroke">Piazza del Rintocco</text>')
    o.append(f'<text x="520" y="170" font-family={FONT!r} font-size="34" font-style="italic" text-anchor="middle" fill="{WATER_D}">Lago Brumo</text>')
    o.append(f'<text x="1000" y="140" font-family={FONT!r} font-size="14" font-style="italic" text-anchor="middle" fill="{INK}">Isola del Fonditore (3 km) ↗</text>')
    # legenda
    lx, ly = 830, 300
    names = {**{n: v[4] for n, v in key.items()}, 9: "Porta del Mulino", 10: "Porta dei Pellegrini", 12: "Molo Lungo", 13: "Cimitero dei Senza Tomba"}
    o.append(f'<rect x="{lx}" y="{ly}" width="276" height="{20*len(names)+22}" fill="#f6edd6" stroke="{INK}" stroke-width="1.5" opacity=".93"/>')
    for i, n in enumerate(sorted(names)):
        o.append(f'<text x="{lx+12}" y="{ly+24+20*i}" font-family={FONT!r} font-size="13" fill="{INK}"><tspan font-weight="bold">{n}</tspan>  {esc(names[n])}</text>')
    o.append("</g>")
    o.append(f'<rect width="{W}" height="{H}" fill="none" stroke="{INK}" stroke-width="2"/></g>')
    # scala e rosa dei venti
    o.append(f'<g transform="translate({M},{HEAD+H+24})"><rect x="0" y="-5" width="60" height="7" fill="{INK}"/><rect x="60" y="-5" width="60" height="7" fill="{FLOOR}" stroke="{INK}"/><text x="130" y="2" font-family={FONT!r} font-size="12" fill="{INK}">100 m</text></g>')
    o.append(f'<g transform="translate({TW-M-26},50)"><polygon points="0,-22 6,0 0,22 -6,0" fill="{INK}"/><polygon points="0,-22 6,0 0,0" fill="{FLOOR}" stroke="{INK}"/><text x="0" y="-26" font-family={FONT!r} font-size="13" font-weight="bold" text-anchor="middle" fill="{INK}">N</text></g>')
    o.append("</svg>")
    return "\n".join(o)


# ---------------------------------------------------------------------------
#  7. LA VALLE DI BRUMARIA (mappa regionale)
# ---------------------------------------------------------------------------
def mappa_valle():
    W, H, M, HEAD, FOOT = 1200, 800, 40, 92, 40
    TW, TH = W + 2 * M, H + HEAD + FOOT
    rnd = random.Random(42)
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{TW}" height="{TH}" viewBox="0 0 {TW} {TH}">',
         f'<rect width="{TW}" height="{TH}" fill="{PAPER}"/>',
         f'<rect x="8" y="8" width="{TW-16}" height="{TH-16}" fill="none" stroke="{INK}" stroke-width="3"/>',
         f'<rect x="14" y="14" width="{TW-28}" height="{TH-28}" fill="none" stroke="{INK}" stroke-width="1"/>',
         f'<text x="{TW/2}" y="52" font-family={FONT!r} font-size="30" font-weight="bold" text-anchor="middle" fill="{INK}">La Valle di Brumaria</text>',
         f'<text x="{TW/2}" y="76" font-family={FONT!r} font-size="15" font-style="italic" text-anchor="middle" fill="{INK}">Marca di Ventofondo · mappa del Master e dei giocatori</text>',
         f'<clipPath id="mc"><rect width="{W}" height="{H}"/></clipPath>',
         f'<g transform="translate({M},{HEAD})"><g clip-path="url(#mc)">',
         f'<rect width="{W}" height="{H}" fill="#e8dcb6"/>']
    # palude
    o.append(f'<path d="{smooth_path(blob_pts(300, 640, 230, 120, 3, jit=0.15))}" fill="#c6c79a" opacity=".9"/>')
    for i in range(16):
        o.append(f'<path d="{smooth_path(blob_pts(rnd.uniform(120,480), rnd.uniform(560,720), rnd.uniform(15,35), rnd.uniform(8,16), 50+i, jit=.2))}" fill="{WATER}" stroke="{WATER_D}" stroke-width="1"/>')
    for i in range(90):
        x, y = rnd.uniform(90, 520), rnd.uniform(540, 750)
        if not in_ellipse(x, y, 300, 640, 220, 115):
            continue
        o.append(f'<path d="M{x-6:.0f},{y:.0f} h12 M{x-3:.0f},{y:.0f} l-2,-7 M{x:.0f},{y:.0f} v-9 M{x+3:.0f},{y:.0f} l2,-7" stroke="#55663a" stroke-width="1.2" fill="none"/>')
    # fiume Lenta
    river_in = [(540, -10), (560, 60), (590, 150), (585, 220), (565, 280)]
    river_out = [(700, 520), (650, 590), (560, 650), (440, 655), (330, 640), (180, 690), (-10, 700)]
    for r in (river_in, river_out):
        o.append(f'<path d="{smooth_path(r, closed=False)}" stroke="{WATER_D}" stroke-width="9" fill="none" stroke-linecap="round"/><path d="{smooth_path(r, closed=False)}" stroke="{WATER}" stroke-width="5" fill="none" stroke-linecap="round"/>')
    # lago
    o.append(f'<path d="{smooth_path(blob_pts(720, 380, 235, 155, 8, jit=0.1))}" fill="{WATER}" stroke="{WATER_D}" stroke-width="3"/>')
    for i in range(18):
        x, y = rnd.uniform(560, 900), rnd.uniform(270, 500)
        if in_ellipse(x, y, 720, 380, 200, 125):
            o.append(f'<path d="M{x:.0f},{y:.0f} q7,-4 14,0 q7,4 14,0" stroke="{WATER_D}" stroke-width="1.3" fill="none" opacity=".7"/>')
    o.append(f'<path d="{smooth_path(blob_pts(805, 330, 26, 18, 9, jit=.2))}" fill="#bfc28f" stroke="{INK}" stroke-width="1.5"/>')
    # nebbia sul lago
    for i in range(7):
        o.append(f'<path d="{smooth_path(blob_pts(rnd.uniform(600,860), rnd.uniform(300,460), rnd.uniform(50,90), rnd.uniform(14,24), 70+i, jit=.25))}" fill="#ffffff" opacity=".35"/>')
    # montagne
    def mountain(x, y, s):
        o.append(f'<path d="M{x-s},{y} L{x},{y-1.25*s} L{x+s},{y}" fill="#d9ccaa" stroke="{INK}" stroke-width="1.8" stroke-linejoin="round"/><path d="M{x},{y-1.25*s} L{x+s},{y} L{x+0.15*s},{y} Z" fill="#a8977a" opacity=".8"/><path d="M{x-0.3*s},{y-0.85*s} L{x},{y-1.25*s} L{x+0.3*s},{y-0.85*s}" fill="#fff" stroke="{INK}" stroke-width="1"/>')
    pts = []
    for i in range(80):
        x, y = rnd.uniform(60, 1180), rnd.uniform(30, 230)
        if in_ellipse(x, y, 560, 120, 70, 300):   # valle del fiume
            continue
        if x > 760 and y > 160:
            continue
        pts.append((x, y))
    for x, y in sorted(pts, key=lambda p: p[1]):
        mountain(x, y, rnd.uniform(22, 38))
    # colline
    for i in range(30):
        x, y = rnd.uniform(60, 1180), rnd.uniform(240, 520)
        if in_ellipse(x, y, 720, 380, 270, 190) or (x < 480 and y > 480):
            continue
        o.append(f'<path d="M{x-16:.0f},{y:.0f} q16,-16 32,0" stroke="{INK}" stroke-width="1.5" fill="none"/>')
    # foresta di San Velio
    tr = []
    for i in range(240):
        x, y = rnd.uniform(860, 1200), rnd.uniform(440, 800)
        if in_ellipse(x, y, 1000, 600, 46, 34):
            continue
        tr.append((x, y))
    for i in range(60):
        x, y = rnd.uniform(40, 260), rnd.uniform(260, 520)
        tr.append((x, y))
    for x, y in sorted(tr, key=lambda p: p[1]):
        r = rnd.uniform(8, 12)
        o.append(f'<line x1="{x:.0f}" y1="{y:.0f}" x2="{x:.0f}" y2="{y+r+3:.0f}" stroke="{INK}" stroke-width="1.5"/><circle cx="{x:.0f}" cy="{y:.0f}" r="{r:.0f}" fill="#8aa05b" stroke="{INK}" stroke-width="1.2"/>')
    # strade
    roads = {
        "mulino": [(515, 470), (450, 520), (370, 560), (268, 598)],
        "miniera": [(515, 470), (500, 400), (470, 320), (420, 250), (338, 182)],
        "abbazia": [(515, 470), (570, 560), (700, 600), (850, 612), (995, 600)],
        "sud": [(515, 470), (520, 600), (490, 700), (470, 810)],
    }
    for r in roads.values():
        o.append(f'<path d="{smooth_path(r, closed=False)}" stroke="#7a5b3a" stroke-width="3" stroke-dasharray="9 5" fill="none"/>')
    # località
    def place(x, y, name, kind, size=15, dx=0, dy=-18, italic=False):
        if kind == "town":
            o.append(f'<rect x="{x-11}" y="{y-11}" width="22" height="22" fill="{ROOF}" stroke="{INK}" stroke-width="2"/><rect x="{x-3}" y="{y-20}" width="6" height="12" fill="{INK}"/>')
        elif kind == "ruin":
            o.append(f'<path d="M{x-9},{y+8} v-14 h5 v6 h4 v-10 h5 v18 z" fill="#b5ab95" stroke="{INK}" stroke-width="1.6"/>')
        elif kind == "mine":
            o.append(f'<path d="M{x-11},{y+8} a11,11 0 0 1 22,0 z" fill="#2a2018"/><path d="M{x-8},{y-12} l16,16 M{x+8},{y-12} l-16,16" stroke="{INK}" stroke-width="2.5"/>')
        elif kind == "mill":
            o.append(f'<rect x="{x-8}" y="{y-6}" width="16" height="14" fill="#a88d68" stroke="{INK}" stroke-width="1.6"/><circle cx="{x+12}" cy="{y+2}" r="7" fill="none" stroke="{INK}" stroke-width="2"/><path d="M{x+5},{y+2} h14 M{x+12},{y-5} v14" stroke="{INK}" stroke-width="1.2"/>')
        elif kind == "abbey":
            o.append(f'<rect x="{x-12}" y="{y-6}" width="24" height="14" fill="#cfc6b2" stroke="{INK}" stroke-width="1.6"/><path d="M{x-12},{y-6} l12,-10 l12,10" fill="#a8553a" stroke="{INK}" stroke-width="1.6"/><path d="M{x},{y-24} v10 M{x-4},{y-20} h8" stroke="{INK}" stroke-width="2"/>')
        elif kind == "village":
            for ddx in (-8, 4):
                o.append(f'<rect x="{x+ddx}" y="{y-4}" width="9" height="8" fill="{ROOF}" stroke="{INK}" stroke-width="1.2"/>')
        elif kind == "island":
            o.append(f'<path d="M{x-6},{y+6} v-12 h12 v12 z" fill="#6b4a35" stroke="{INK}"/><circle cx="{x}" cy="{y-10}" r="4" fill="#e8892f"/>')
        elif kind == "bridge":
            o.append(f'<path d="M{x-10},{y-5} q10,-8 20,0 M{x-10},{y+5} q10,-8 20,0" stroke="{INK}" stroke-width="2" fill="none"/>')
        st = ' font-style="italic"' if italic else ""
        o.append(f'<text x="{x+dx}" y="{y+dy}" font-family={FONT!r} font-size="{size}" font-weight="bold"{st} text-anchor="middle" fill="{INK}" stroke="#efe6cc" stroke-width="4" paint-order="stroke">{esc(name)}</text>')

    place(515, 470, "Brumaria", "town", 19, -50, 6)
    place(268, 598, "Mulino della Palude Lenta", "mill", 14, 0, -18)
    place(338, 182, "Miniera di Ferrocupo", "mine", 14, 0, 30)
    place(995, 600, "Abbazia di San Velio", "abbey", 14, 0, 30)
    place(805, 330, "Isola del Fonditore", "island", 14, 0, -24)
    place(495, 715, "Canneto", "village", 13, 40, 5)
    place(882, 205, "Torre dei Venti (rovina)", "ruin", 13, 0, 28)
    place(512, 653, "Ponte Vecchio", "bridge", 12, 54, 18)
    place(600, 120, "Guado della Lenta", "bridge", 12, 80, 5)
    # nomi di regione
    def region(x, y, t, s=22, rot=0, color=INK):
        o.append(f'<text x="{x}" y="{y}" font-family={FONT!r} font-size="{s}" font-style="italic" text-anchor="middle" fill="{color}" letter-spacing="4" opacity=".85" transform="rotate({rot} {x} {y})" stroke="#efe6cc" stroke-width="3" paint-order="stroke">{esc(t)}</text>')
    region(300, 110, "MONTI FERROCUPI", 24)
    region(260, 720, "PALUDE LENTA", 22)
    region(1050, 520, "BOSCO DI SAN VELIO", 18, -8)
    region(720, 450, "LAGO BRUMO", 26, 0, WATER_D)
    region(150, 330, "Selva dei Cardi", 15)
    o.append(f'<text x="600" y="215" font-family={FONT!r} font-size="13" font-style="italic" fill="{WATER_D}" transform="rotate(80 600 215)" stroke="#efe6cc" stroke-width="3" paint-order="stroke">fiume Lenta</text>')
    # tempi di viaggio
    def note(x, y, t):
        o.append(f'<text x="{x}" y="{y}" font-family={FONT!r} font-size="12.5" font-style="italic" text-anchor="middle" fill="#6b3e1e" stroke="#efe6cc" stroke-width="3.5" paint-order="stroke">{esc(t)}</text>')
    note(395, 520, "1 giorno a piedi")
    note(480, 285, "2 giorni a piedi")
    note(480, 302, "(1 giorno in chiatta)")
    note(780, 635, "1 giorno a piedi")
    note(680, 340, "3 km in barca")
    note(470, 780, "verso Porto Salice (5 giorni) ↓")
    o.append("</g>")
    o.append(f'<rect width="{W}" height="{H}" fill="none" stroke="{INK}" stroke-width="2"/></g>')
    o.append(f'<g transform="translate({M},{HEAD+H+24})"><rect x="0" y="-5" width="70" height="7" fill="{INK}"/><rect x="70" y="-5" width="70" height="7" fill="{FLOOR}" stroke="{INK}"/><text x="150" y="2" font-family={FONT!r} font-size="12" fill="{INK}">≈ 10 km   ·   1 giorno di marcia ≈ 30 km su strada, 15 km in palude o montagna</text></g>')
    o.append(f'<g transform="translate({TW-M-26},50)"><polygon points="0,-22 6,0 0,22 -6,0" fill="{INK}"/><polygon points="0,-22 6,0 0,0" fill="{FLOOR}" stroke="{INK}"/><polygon points="-22,0 0,6 22,0 0,-6" fill="{INK}" opacity=".5"/><text x="0" y="-26" font-family={FONT!r} font-size="13" font-weight="bold" text-anchor="middle" fill="{INK}">N</text></g>')
    o.append("</svg>")
    return "\n".join(o)


def main():
    os.makedirs(OUT, exist_ok=True)
    maps = {
        "01_valle_di_brumaria": mappa_valle(),
        "02_brumaria": mappa_brumaria(),
        "03_campanile": mappa_campanile(),
        "04_mulino": mappa_mulino(),
        "05_miniera": mappa_miniera(),
        "06_abbazia": mappa_abbazia(),
        "07_isola_del_fonditore": mappa_isola(),
    }
    have_rsvg = shutil.which("rsvg-convert")
    for name, svg in maps.items():
        p = os.path.join(OUT, name + ".svg")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(svg)
        if have_rsvg:
            png = os.path.join(OUT, "png", name + ".png")
            os.makedirs(os.path.dirname(png), exist_ok=True)
            subprocess.run(["rsvg-convert", "--zoom", "2", "-o", png, p], check=True)
        print("ok", name)


if __name__ == "__main__":
    main()
