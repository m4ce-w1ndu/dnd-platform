#!/usr/bin/env python3
"""Compone i documenti HTML stampabili a partire dai sorgenti in ./sorgenti/.

Uso:  python3 componi.py
Per ottenere un PDF: apri il file .html in Firefox/Chrome -> Stampa -> «Salva come PDF»
(attiva «Stampa sfondi» per avere i riquadri colorati).
"""
import os

QUI = os.path.dirname(os.path.abspath(__file__))
RADICE = os.path.dirname(QUI)

CSS = r"""
:root{--ink:#2a2018;--paper:#f6efdc;--card:#fffaf0;--accent:#7a2e1c;--accent2:#355e5f;--muted:#6b5c48;--box:#efe2c2;--read:#e6eef0;--rule:#c9b48a}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--ink:#ece3cf;--paper:#1d1a16;--card:#26221c;--accent:#e29a7d;--accent2:#8cc3c3;--muted:#b3a58c;--box:#332c22;--read:#22302f;--rule:#5c5140}}
:root[data-theme="dark"]{--ink:#ece3cf;--paper:#1d1a16;--card:#26221c;--accent:#e29a7d;--accent2:#8cc3c3;--muted:#b3a58c;--box:#332c22;--read:#22302f;--rule:#5c5140}
*{box-sizing:border-box}
html{background:var(--paper)}
body{margin:0 auto;max-width:900px;padding:24px 16px 80px;background:var(--paper);color:var(--ink);font:17px/1.6 'Noto Serif','DejaVu Serif',Georgia,serif}
h1,h2,h3,h4{font-family:'Noto Serif','DejaVu Serif',Georgia,serif;color:var(--accent);line-height:1.25}
h1{font-size:2.3em;text-align:center;margin:.2em 0}
h2{font-size:1.65em;border-bottom:3px double var(--rule);padding-bottom:.2em;margin-top:2.2em}
h3{font-size:1.25em;margin-top:1.6em}
h4{font-size:1.05em;margin:1.2em 0 .3em;color:var(--accent2)}
a{color:var(--accent2)}
.copertina{text-align:center;padding:40px 0 20px;border-bottom:3px double var(--rule)}
.copertina .sotto{font-style:italic;color:var(--muted);font-size:1.15em}
.copertina .info{display:inline-block;margin-top:1em;padding:.6em 1.2em;border:1px solid var(--rule);border-radius:8px;background:var(--card)}
.indice{columns:2;column-gap:2em;background:var(--card);border:1px solid var(--rule);padding:1em 1.5em;border-radius:8px}
.indice a{text-decoration:none}
.leggi{background:var(--read);border-left:6px solid var(--accent2);padding:.8em 1.1em;margin:1em 0;font-style:italic;border-radius:0 6px 6px 0}
.leggi::before{content:"📜 Leggi ad alta voce";display:block;font-style:normal;font-weight:bold;font-size:.8em;letter-spacing:.05em;color:var(--accent2);margin-bottom:.3em}
.nota{background:var(--box);border:1px solid var(--rule);padding:.8em 1.1em;margin:1em 0;border-radius:6px}
.nota>b:first-child,.consiglio>b:first-child{color:var(--accent)}
.consiglio{background:var(--card);border:2px dashed var(--accent2);padding:.8em 1.1em;margin:1em 0;border-radius:6px}
.consiglio::before{content:"💡 Consiglio per chi fa il Master per la prima volta";display:block;font-weight:bold;font-size:.85em;color:var(--accent2);margin-bottom:.3em}
.sei{background:var(--card);border-left:6px solid #a8822c;padding:.5em 1em;margin:.8em 0;border-radius:0 6px 6px 0}
.sei::before{content:"👥 Con 6 giocatori: ";font-weight:bold;color:#a8822c}
.scontro{border:2px solid var(--accent);border-radius:8px;padding:.6em 1em;margin:1em 0;background:var(--card)}
.scontro .tit{font-weight:bold;color:var(--accent)}
.scontro .diff{float:right;font-size:.85em;padding:.1em .6em;border-radius:20px;background:var(--box)}
table{border-collapse:collapse;width:100%;margin:1em 0;font-size:.93em;background:var(--card)}
th,td{border:1px solid var(--rule);padding:.35em .55em;vertical-align:top;text-align:left}
th{background:var(--box)}
.stat{background:var(--card);border-top:5px solid var(--accent);border-bottom:5px solid var(--accent);padding:.7em 1em;margin:1.2em 0;font-size:.93em;break-inside:avoid;box-shadow:0 1px 4px rgba(0,0,0,.12)}
.stat h4{margin:0;font-size:1.3em;color:var(--accent)}
.stat .tipo{font-style:italic;color:var(--muted);margin-bottom:.4em}
.stat .car{display:grid;grid-template-columns:repeat(6,1fr);text-align:center;border-top:1px solid var(--accent);border-bottom:1px solid var(--accent);margin:.5em 0;padding:.3em 0}
.stat .car b{display:block;color:var(--accent)}
.stat p{margin:.3em 0}
.mappa{margin:1.2em 0;text-align:center;break-inside:avoid}
.mappa img{max-width:100%;border:1px solid var(--rule);background:#efe3c4}
.mappa figcaption{font-style:italic;color:var(--muted);font-size:.9em}
.chiave dt{font-weight:bold;color:var(--accent);margin-top:.8em}
.chiave dd{margin:0 0 0 1.2em}
.handout{background:#f3e6c3;color:#3b2a18;border:1px solid #b59a64;padding:1.4em 1.8em;margin:1.2em 0;font-family:'Noto Serif','DejaVu Serif',Georgia,serif;font-style:italic;box-shadow:2px 3px 8px rgba(0,0,0,.25);transform:rotate(-.4deg);break-inside:avoid}
.clessidra{display:flex;gap:6px;margin:.6em 0}
.clessidra span{width:44px;height:44px;border:2px solid var(--ink);border-radius:6px;display:flex;align-items:center;justify-content:center;font-weight:bold}
.scheda{background:var(--card);border:2px solid var(--accent);border-radius:10px;padding:1em 1.3em;margin:1.5em 0;break-inside:avoid-page}
.scheda .intest{display:flex;justify-content:space-between;flex-wrap:wrap;gap:.5em;border-bottom:2px solid var(--accent);padding-bottom:.4em;margin-bottom:.6em}
.scheda .nome{font-size:1.6em;font-weight:bold;color:var(--accent)}
.scheda .cl{font-style:italic;color:var(--muted)}
.big{display:grid;grid-template-columns:repeat(auto-fit,minmax(90px,1fr));gap:8px;margin:.6em 0}
.big div{border:2px solid var(--ink);border-radius:8px;text-align:center;padding:.3em}
.big b{display:block;font-size:1.5em}
.big small{display:block;font-size:.75em;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:1.2em}
.chip{display:inline-block;background:var(--box);border-radius:20px;padding:0 .6em;margin:.1em;font-size:.88em}
@media (max-width:640px){.indice{columns:1}.cols{grid-template-columns:1fr}.stat .car{grid-template-columns:repeat(3,1fr)}body{font-size:16px}}
@media print{
 :root{--ink:#2a2018;--paper:#fff;--card:#fff;--accent:#7a2e1c;--accent2:#355e5f;--muted:#5a4c3a;--box:#f1e7cf;--read:#e9f0f1;--rule:#bfa77a}
 body{max-width:none;padding:0;font-size:11pt}
 h2{break-before:page}
 h2.nobreak{break-before:auto}
 .scheda{break-before:page;border:none;padding:0}
 .scheda.prima{break-before:auto}
 .mappa{break-before:page}
 .mappa img{max-height:24cm}
 a{color:inherit;text-decoration:none}
 .nostampa{display:none}
}
@page{size:A4;margin:1.6cm}
"""


def componi(sorgente, uscita, titolo, descrizione):
    corpo = ""
    for nome in (sorgente if isinstance(sorgente, list) else [sorgente]):
        with open(os.path.join(QUI, "sorgenti", nome), encoding="utf-8") as f:
            corpo += f.read() + "\n"
    html = f"""<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{titolo}</title>
<meta name="description" content="{descrizione}">
<style>{CSS}</style>
</head>
<body>
{corpo}
</body>
</html>
"""
    with open(os.path.join(RADICE, uscita), "w", encoding="utf-8") as f:
        f.write(html)
    print("ok", uscita, f"({len(html)//1024} KB)")


if __name__ == "__main__":
    componi(["master_1.html", "master_2.html", "master_3.html"], "1_Manuale_del_Master.html", "Manuale del Master", "Le Campane di Brumaria: avventura completa di D&D 5e per 5-6 giocatori principianti.")
    componi("giocatore.html", "2_Guida_del_Giocatore.html", "Guida del Giocatore", "Regole semplici e ambientazione per chi gioca a D&D per la prima volta.")
    componi("schede.html", "3_Schede_dei_Personaggi.html", "Schede dei Personaggi", "Sei personaggi pronti da giocare, dal 1° al 4° livello.")
