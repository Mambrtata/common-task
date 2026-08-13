#!/usr/bin/env python3
"""Krok 6: OCR skenovaných PDF rozpočtov (tesseract, slk).

Použitie:
    python3 06_ocr.py [--workers 2] [--max-pdf N] [--len-crz]

Nájde PDF bez textovej vrstvy v data/subory a data/subory_crz, spustí OCR
po stranách (220 DPI, psm 6) a text uloží do data/ocr_txt/<hash>.txt
(cache – druhý beh OCR preskočí). Z textu extrahuje položky s prísnou
validáciou: riadok musí mať TSKP kód, MJ a trojicu čísel, kde
množstvo × jedn. cena ≈ spolu (2 % tolerancia). Výstup: data/ocr_polozky.csv.
"""

import argparse
import csv
import hashlib
import io
import pathlib
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor

import pypdfium2 as pdfium

HERE = pathlib.Path(__file__).parent
DATA = HERE / "data"
CACHE = DATA / "ocr_txt"

RE_KOD = re.compile(r"\b(\d{6,9})(?:\.\w{1,4})?\b")
MJ = r"(m2|m3|m|ks|kus|t|kg|súb|sub|bm|hod|m Z|mZ)"   # OCR varianty m2/m3
RE_CISLO = re.compile(r"\d[\d ]*[.,]\d{2,3}|\d+")


def ma_text(pdf_path: pathlib.Path) -> bool:
    try:
        pdf = pdfium.PdfDocument(str(pdf_path))
        for i in range(min(3, len(pdf))):
            try:
                if len(pdf[i].get_textpage().get_text_range()) > 150:
                    pdf.close()
                    return True
            except Exception:
                continue
        pdf.close()
        return False
    except Exception:
        return True   # nečitateľné PDF radšej preskoč


def ocr_pdf(pdf_path: str) -> str:
    """OCR celého PDF, vráti text. Beží v samostatnom procese."""
    texty = []
    pdf = pdfium.PdfDocument(pdf_path)
    with tempfile.TemporaryDirectory() as tmp:
        for i in range(len(pdf)):
            try:
                img = pdf[i].render(scale=220 / 72).to_pil()
                png = f"{tmp}/p.png"
                img.save(png)
                r = subprocess.run(
                    ["tesseract", png, "stdout", "-l", "slk", "--psm", "6"],
                    capture_output=True, text=True, timeout=120)
                texty.append(r.stdout)
            except Exception:
                continue
    pdf.close()
    return "\n".join(texty)


def na_float(s: str) -> float:
    try:
        return float(s.replace(" ", "").replace(",", "."))
    except ValueError:
        return 0.0


def extrahuj(text: str):
    """Z OCR textu vytiahni validované položky."""
    polozky = []
    for riadok in text.splitlines():
        mk = RE_KOD.search(riadok)
        if not mk:
            continue
        za_kodom = riadok[mk.end():]
        mmj = re.search(r"\b" + MJ + r"\b", za_kodom, re.I)
        if not mmj:
            continue
        popis = re.sub(r"[|\[\]_]+", " ", za_kodom[:mmj.start()])
        popis = re.sub(r"\s+", " ", popis).strip(" .-")
        if len(popis) < 10:
            continue
        cisla = [na_float(c) for c in RE_CISLO.findall(za_kodom[mmj.end():])]
        cisla = [c for c in cisla if c > 0]
        # validácia: nájdi trojicu mn*cena≈spolu v posledných číslach
        for a in range(len(cisla) - 2):
            mn, cena, spolu = cisla[a], cisla[a + 1], cisla[a + 2]
            if abs(mn * cena - spolu) <= max(0.02 * spolu, 0.05):
                polozky.append({"kod": mk.group(1), "popis": popis[:90],
                                "mj": mmj.group(1).lower().replace(" ", ""),
                                "mnozstvo": mn, "jedn_cena": cena})
                break
    return polozky


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--max-pdf", type=int, default=100000)
    ap.add_argument("--len-crz", action="store_true",
                    help="spracuj len CRZ súbory")
    args = ap.parse_args()
    CACHE.mkdir(exist_ok=True)

    zdroje = [DATA / "subory_crz"] if args.len_crz else \
             [DATA / "subory_crz", DATA / "subory"]
    kandidati = []
    for base in zdroje:
        if not base.exists():
            continue
        for f in sorted(base.rglob("*.pdf")):
            h = hashlib.md5(str(f.relative_to(DATA)).encode()).hexdigest()
            cache_f = CACHE / f"{h}.txt"
            if cache_f.exists():
                continue
            if ma_text(f):
                cache_f.with_suffix(".skip").touch()   # má text, netreba OCR
                continue
            if not (CACHE / f"{h}.skip").exists():
                kandidati.append((f, cache_f))
            if len(kandidati) >= args.max_pdf:
                break
    print(f"na OCR: {len(kandidati)} PDF", flush=True)

    out = DATA / "ocr_polozky.csv"
    novy = not out.exists()
    with out.open("a", newline="", encoding="utf-8") as fcsv, \
            ProcessPoolExecutor(max_workers=args.workers) as ex:
        w = csv.DictWriter(fcsv, fieldnames=["zdroj_subor", "kod", "popis",
                                             "mj", "mnozstvo", "jedn_cena"])
        if novy:
            w.writeheader()
        vysledky = ex.map(ocr_pdf, [str(f) for f, _ in kandidati])
        for (f, cache_f), text in zip(kandidati, vysledky):
            cache_f.write_text(text, encoding="utf-8")
            pol = extrahuj(text)
            for p in pol:
                w.writerow({"zdroj_subor": str(f.relative_to(DATA)), **p})
            fcsv.flush()
            print(f"{f.name[:60]}: {len(pol)} položiek", flush=True)


if __name__ == "__main__":
    main()
