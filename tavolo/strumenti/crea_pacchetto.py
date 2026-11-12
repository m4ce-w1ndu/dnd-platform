#!/usr/bin/env python3
"""Crea un pacchetto avventura (.zip) per il Tavolo Virtuale a partire da una cartella progetto.

La cartella progetto deve contenere un file `pacchetto.json` (vedi FORMATO_AVVENTURE.md, sezione «Sorgente»).

Uso:
    python3 tavolo/strumenti/crea_pacchetto.py avventure/vermiglia              -> tavolo/pacchetti/vermiglia.zip
    python3 tavolo/strumenti/crea_pacchetto.py avventure/vermiglia --pubblica   -> crea e carica sul server (scp + unzip)
"""
import argparse
import json
import os
import re
import subprocess
import sys
import zipfile

QUI = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(QUI, "..", "pacchetti")
IMG_EXT = (".svg", ".png", ".jpg", ".jpeg", ".webp")
CAMPI = ("id", "titolo", "sottotitolo", "descrizione", "livello", "giocatori", "durata", "copertina")


def crea(progetto):
    progetto = os.path.abspath(progetto)
    with open(os.path.join(progetto, "pacchetto.json"), encoding="utf-8") as f:
        src = json.load(f)
    aid = src["id"]
    if not re.match(r"^[a-z0-9][a-z0-9_\-]{0,60}$", aid):
        sys.exit(f"id non valido: {aid!r} (solo minuscole, numeri, - e _)")
    os.makedirs(OUT, exist_ok=True)
    dest = os.path.join(OUT, aid + ".zip")
    manifest = {k: src[k] for k in CAMPI if k in src}
    manifest["formato"] = 1
    manifest["documenti"] = [{k: d[k] for k in ("file", "titolo", "solo_master") if k in d} | {"file": os.path.basename(d["file"])}
                             for d in src.get("documenti", [])]
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"{aid}/avventura.json", json.dumps(manifest, ensure_ascii=False, indent=1))
        for chiave in ("personaggi", "mostri"):
            dati = []
            if src.get(chiave):
                with open(os.path.join(progetto, src[chiave]), encoding="utf-8") as f:
                    dati = json.load(f)
            z.writestr(f"{aid}/{chiave}.json", json.dumps(dati, ensure_ascii=False, indent=1))
        cart = os.path.join(progetto, src.get("mappe_cartella", "mappe"))
        meta_mappe = src.get("mappe", {})
        n_mappe = 0
        for nome in sorted(os.listdir(cart)) if os.path.isdir(cart) else []:
            stem, ext = os.path.splitext(nome)
            if ext.lower() not in IMG_EXT:
                continue
            if meta_mappe and stem not in meta_mappe:
                continue  # se il manifest elenca le mappe, si includono solo quelle
            z.write(os.path.join(cart, nome), f"{aid}/mappe/{nome}")
            meta = meta_mappe.get(stem, {})
            z.writestr(f"{aid}/mappe/{stem}.json", json.dumps(meta, ensure_ascii=False, indent=1))
            n_mappe += 1
        for d in src.get("documenti", []):
            percorso = os.path.join(progetto, d["file"])
            dest_doc = f"{aid}/documenti/{os.path.basename(d['file'])}"
            if not percorso.lower().endswith((".html", ".htm")):
                z.write(percorso, dest_doc)      # PDF, immagini, testo: copiati così come sono
                continue
            with open(percorso, encoding="utf-8") as f:
                html = f.read()
            # i documenti stanno in documenti/, le mappe in mappe/: si corregge il percorso relativo
            # nei sorgenti le immagini puntano a ../../asset/mappe/<id>/ (o a mappe/): nel pacchetto stanno in ../mappe/
            html = re.sub(r'(src|href)="(?:\.\./)*(?:asset/mappe/[^/"]+/|mappe/)', r'\1="../mappe/', html)
            z.writestr(dest_doc, html)
    print(f"✓ {dest}  ({n_mappe} mappe, {len(manifest['documenti'])} documenti, {os.path.getsize(dest) // 1024} KB)")
    return dest, aid


def pubblica(zip_path, aid, host):
    remoto = f"/tmp/{aid}.zip"
    subprocess.run(["scp", "-q", zip_path, f"{host}:{remoto}"], check=True)
    script = f"""set -e
sudo python3 - <<'PY'
import zipfile, shutil, os
base = '/var/lib/tavolo-virtuale/avventure'
dest = os.path.join(base, '{aid}')
tmp = dest + '.nuova'
shutil.rmtree(tmp, ignore_errors=True)
zipfile.ZipFile('{remoto}').extractall(tmp)
src = os.path.join(tmp, '{aid}')
if os.path.exists(dest):
    shutil.rmtree(dest)
os.replace(src, dest)
shutil.rmtree(tmp, ignore_errors=True)
PY
sudo chown -R 1000:1000 /var/lib/tavolo-virtuale/avventure/{aid}
rm -f {remoto}
"""
    subprocess.run(["ssh", host, "bash", "-s"], input=script.encode(), check=True)
    print(f"✓ pubblicata su {host}: il server la vede entro pochi secondi, senza riavvii")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("progetti", nargs="+")
    ap.add_argument("--pubblica", action="store_true", help="carica il pacchetto sul server")
    ap.add_argument("--host", default=os.environ.get("HOST", "immauri@192.168.0.2"))
    a = ap.parse_args()
    for p in a.progetti:
        z, aid = crea(p)
        if a.pubblica:
            pubblica(z, aid, a.host)
