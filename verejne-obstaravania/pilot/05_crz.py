#!/usr/bin/env python3
"""Krok 5: backfill z nočných dávok Centrálneho registra zmlúv.

Použitie:
    python3 05_crz.py [--dni 1460] [--max-pdf-mb 20]

Ide po dňoch dozadu od včerajška: stiahne dennú dávku
crz.gov.sk/export/RRRR-MM-DD.zip, vyfiltruje stavebné zmluvy a stiahne
prílohy vyzerajúce na rozpočet/výkaz do data/subory_crz/<zmluva_id>/.
Metadáta priebežne zapisuje do data/crz_zmluvy.csv.
"""

import argparse
import csv
import datetime as dt
import io
import pathlib
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from uvo_common import fetch

HERE = pathlib.Path(__file__).parent
DATA = HERE / "data"

RE_STAV = re.compile(
    r"(dielo|stavb|rekon[šs]tru|zateplen|pr[íi]stavb|obnov|v[ýy]stavb)", re.I)
RE_ROZP = re.compile(r"(rozpo[čc]|v[ýy]kaz|polo[žz]k|cenov|kalkul)", re.I)
PRIPONY_OK = (".pdf", ".xls", ".xlsx", ".xlsm", ".zip")


def spracuj_den(den: dt.date, writer, max_pdf_mb: float):
    url = f"https://www.crz.gov.sk/export/{den.isoformat()}.zip"
    try:
        raw = fetch(url, binary=True)
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            xml_data = z.read(z.namelist()[0])
        root = ET.fromstring(xml_data)
    except Exception as e:
        print(f"{den}: dávka nedostupná ({e})")
        return 0, 0

    zmluvy = root.findall("zmluva")
    stiahnute = 0
    for z in zmluvy:
        predmet = z.findtext("predmet") or ""
        if not RE_STAV.search(predmet):
            continue
        zid = z.findtext("ID") or ""
        for p in z.findall(".//priloha"):
            nazov = p.findtext("nazov") or ""
            subor = p.findtext("dokument1") or ""
            velkost = int(p.findtext("velkost1") or 0)
            pripona = pathlib.Path(subor).suffix.lower()
            if not subor or pripona not in PRIPONY_OK:
                continue
            if not (RE_ROZP.search(nazov) or RE_ROZP.search(subor)):
                continue
            if pripona == ".pdf" and velkost > max_pdf_mb * 1e6:
                continue
            ciel = DATA / "subory_crz" / zid
            dst = ciel / subor
            if dst.exists():
                continue
            try:
                data = fetch(f"https://www.crz.gov.sk/data/att/{subor}",
                             binary=True)
            except RuntimeError as e:
                print(f"  ! {subor}: {e}")
                continue
            ciel.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(data)
            stiahnute += 1
            writer.writerow({
                "datum_davky": den.isoformat(), "zmluva_id": zid,
                "predmet": predmet[:200],
                "objednavatel": z.findtext("zs2") or "",
                "dodavatel": z.findtext("zs1") or "",
                "suma": z.findtext("suma_spolu") or "",
                "priloha": nazov[:120], "subor": subor,
            })
    return len(zmluvy), stiahnute


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dni", type=int, default=1460)
    ap.add_argument("--max-pdf-mb", type=float, default=20.0)
    args = ap.parse_args()

    DATA.mkdir(exist_ok=True)
    out = DATA / "crz_zmluvy.csv"
    novy = not out.exists()
    with out.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "datum_davky", "zmluva_id", "predmet", "objednavatel",
            "dodavatel", "suma", "priloha", "subor"])
        if novy:
            writer.writeheader()
        spolu = 0
        for i in range(1, args.dni + 1):
            den = dt.date.today() - dt.timedelta(days=i)
            n, s = spracuj_den(den, writer, args.max_pdf_mb)
            spolu += s
            f.flush()
            print(f"{den}: {n} zmlúv, +{s} súborov (spolu {spolu})")


if __name__ == "__main__":
    main()
