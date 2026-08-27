#!/usr/bin/env python3
"""Krok 10: zber cien projektových a inžinierskych služieb (CPV 71xx).

Použitie:
    python3 10_pd_sluzby.py --zoznam            # len zoznam zákaziek
    python3 10_pd_sluzby.py --limit 500         # zoznam + ceny
    python3 10_pd_sluzby.py --shard 0/4         # paralelný beh

Pri projektových službách nie je výkaz výmer – cena je jedno číslo
v Správe o zákazke, Zápisnici o vyhodnotení ponúk alebo v Návrhu na
plnenie kritérií. Skript ich odtiaľ vyťaží.

Výstup: data/pd_zakazky.csv (zoznam) a data/pd_ceny.csv:
    zakazka_id, nazov, obstaravatel, cpv, kraj, datum, druh_ceny,
    cena, dph, uchadzac, zdroj_dokument, zdroj_url
kde druh_ceny = phz | konecna | ponuka
"""

import argparse
import csv
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from uvo_common import (BASE, dokument_detail, dokumenty_zakazky, fetch,
                        zakazky_page)

try:
    import pypdfium2 as pdfium
except ImportError:
    raise SystemExit("chýba pypdfium2: pip install pypdfium2")

HERE = pathlib.Path(__file__).parent
DATA = HERE / "data"

# Priorita: správa o zákazke má PHZ + konečnú cenu + víťaza v jednom malom
# PDF. Ostatné sa berú, len keď správa chýba alebo z nej nič nevypadlo.
TYPY_PRIORITA = ("správa o zákazke", "informácia o výsledku",
                 "zápisnica o vyhodnotení", "ponuky uchádzačov")

# čísla v slovenskom aj medzinárodnom formáte: 139 860,00 | 12.999,00 | 12999.00
CISLO = r"(\d{1,3}(?:[\s .]\d{3})*(?:,\d{1,2})?|\d+(?:[.,]\d{1,2})?)"
RE_PHZ = re.compile(r"[Pp]redpokladaná hodnota[^0-9]{0,60}" + CISLO
                    + r"\s*(?:EUR|€)", re.I)
RE_KONECNA = re.compile(
    r"(?:celková konečná hodnota|hodnota zákazky|celková zmluvná cena|"
    r"zmluvná cena celkom|cena celkom za celý predmet)[^0-9]{0,60}" + CISLO
    + r"\s*(?:EUR|€)", re.I)
RE_SUMA = re.compile(CISLO + r"\s*(?:EUR|€)")


def na_float(s: str):
    """Zvládne 139 860,00 | 12.999,00 | 12999.00 | 12,5"""
    s = re.sub(r"[\s  ]", "", s).strip()
    if "," in s and "." in s:              # 12.999,00 – bodka sú tisíce
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:                         # 139860,00
        s = s.replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(?:\.\d{3})+", s):   # 12.999
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def dph_priznak(kontext: str) -> str:
    k = kontext.lower()
    if "bez dph" in k:
        return "bez DPH"
    if "s dph" in k or "vrátane dph" in k or "vratane dph" in k:
        return "s DPH"
    return ""


def text_pdf(data: bytes, maxp: int = 20) -> str:
    try:
        pdf = pdfium.PdfDocument(data)
    except Exception:
        return ""
    out = []
    try:
        for i in range(min(len(pdf), maxp)):
            try:
                out.append(pdf[i].get_textpage().get_text_range())
            except Exception:
                continue
    finally:
        pdf.close()
    return re.sub(r"\s+", " ", " ".join(out))


def ceny_z_textu(t: str):
    """Vráti list (druh_ceny, cena, dph)."""
    najdene = []
    for rex, druh in ((RE_PHZ, "phz"), (RE_KONECNA, "konecna")):
        for m in rex.finditer(t):
            c = na_float(m.group(1))
            if not c or c < 100:
                continue
            # "hodnota zákazky" je súčasťou "Predpokladaná hodnota zákazky" –
            # bez tejto kontroly by sa PHZ zapísala aj ako konečná cena
            if druh == "konecna" and "predpoklad" in \
                    t[max(0, m.start() - 25):m.start() + 20].lower():
                continue
            okolie = t[m.start():m.end() + 30]
            najdene.append((druh, c, dph_priznak(okolie)))
    # ponuky: sumy v zápisnici (aspoň 3 rôzne, aby to neboli pokuty a %)
    sumy = []
    for m in RE_SUMA.finditer(t):
        c = na_float(m.group(1))
        if c and c >= 500:
            sumy.append((c, dph_priznak(t[m.start():m.end() + 25])))
    if not najdene and sumy:
        for c, d in sumy[:6]:
            najdene.append(("ponuka", c, d))
    return najdene


def spracuj_zakazku(z, writer, max_mb=5.0, max_dokumentov=2):
    """Vyťaží ceny zo zákazky. Berie dokumenty podľa priority a končí,
    len čo z niektorého vypadli ceny – šetrí requesty aj čas."""
    riadky = 0
    try:
        dokumenty = dokumenty_zakazky(z["id"])
    except RuntimeError:
        return 0

    def poradie(dt):
        for i, typ in enumerate(TYPY_PRIORITA):
            if typ in dt.lower():
                return i
        return 99

    kandidati = sorted(((did, dt) for did, dt in dokumenty
                        if poradie(dt) < 99), key=lambda x: poradie(x[1]))

    for did, typ in kandidati[:max_dokumentov]:
        try:
            d = dokument_detail(did)
        except RuntimeError:
            continue
        for i, link in enumerate(d["download_linky"]):
            nazov = (d["nazvy_suborov"][i] if i < len(d["nazvy_suborov"])
                     else "")
            if not nazov.lower().endswith(".pdf"):
                continue
            vel = d["velkosti_mb"][i] if i < len(d["velkosti_mb"]) else 0
            if vel > max_mb:
                continue
            try:
                t = text_pdf(fetch(link, binary=True))
            except RuntimeError:
                continue
            if len(t) < 200:          # sken bez textovej vrstvy
                continue
            for druh, cena, dph in ceny_z_textu(t):
                writer.writerow({
                    "zakazka_id": z["id"], "nazov": z["nazov"][:150],
                    "obstaravatel": z["obstaravatel"][:90], "cpv": z["cpv"],
                    "kraj": z["kraj"], "datum": z["aktualizacia"],
                    "druh_ceny": druh, "cena": cena, "dph": dph,
                    "uchadzac": d["dodavatel"][:80],
                    "zdroj_dokument": typ,
                    "zdroj_url": f"{BASE}/vyhladavanie/vyhladavanie-zakaziek"
                                 f"/detail/{z['id']}"})
                riadky += 1
        if riadky:            # máme ceny, ďalšie dokumenty netreba
            break
    return riadky


def nacitaj_zoznam(max_stran):
    kody = [r.split("#")[0].strip()
            for r in (HERE / "cpv_sluzby.txt").read_text().splitlines()]
    kody = [k for k in kody if k]
    vsetky, videne = [], set()
    for cpv in kody:
        for page in range(1, max_stran + 1):
            riadky = zakazky_page(cpv, page, druh="SLUZBY")
            nove = [r for r in riadky if r["id"] not in videne]
            videne.update(r["id"] for r in nove)
            vsetky.extend(nove)
            print(f"CPV {cpv} strana {page}: +{len(nove)}", flush=True)
            if len(riadky) < 10 or not nove:
                break
    return vsetky


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-stran", type=int, default=200)
    ap.add_argument("--limit", type=int, default=999999)
    ap.add_argument("--shard", default="")
    ap.add_argument("--zoznam", action="store_true", help="len krok 1")
    args = ap.parse_args()
    DATA.mkdir(exist_ok=True)

    zoznam_csv = DATA / "pd_zakazky.csv"
    if not zoznam_csv.exists():
        zak = nacitaj_zoznam(args.max_stran)
        with zoznam_csv.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["id", "nazov", "obstaravatel",
                                              "cpv", "cpv_popis", "kraj",
                                              "aktualizacia"])
            w.writeheader()
            w.writerows(zak)
        print(f"\nzoznam: {len(zak)} zákaziek -> {zoznam_csv}")
    if args.zoznam:
        return

    with zoznam_csv.open(encoding="utf-8") as f:
        zakazky = list(csv.DictReader(f))[: args.limit]
    sufix = ""
    if args.shard:
        i, n = (int(x) for x in args.shard.split("/"))
        zakazky = [z for j, z in enumerate(zakazky) if j % n == i]
        sufix = f"_shard{i}"

    hotovo_f = DATA / "pd_hotovo.txt"
    hotovo = set(hotovo_f.read_text().split()) if hotovo_f.exists() else set()
    if hotovo:
        pred = len(zakazky)
        zakazky = [z for z in zakazky if z["id"] not in hotovo]
        print(f"preskakujem {pred - len(zakazky)} hotových")

    out = DATA / f"pd_ceny{sufix}.csv"
    novy = not out.exists()
    with out.open("a", newline="", encoding="utf-8") as f, \
            hotovo_f.open("a", encoding="utf-8") as hf:
        w = csv.DictWriter(f, fieldnames=[
            "zakazka_id", "nazov", "obstaravatel", "cpv", "kraj", "datum",
            "druh_ceny", "cena", "dph", "uchadzac", "zdroj_dokument",
            "zdroj_url"])
        if novy:
            w.writeheader()
        spolu = 0
        for k, z in enumerate(zakazky, 1):
            spolu += spracuj_zakazku(z, w)
            hf.write(z["id"] + "\n")
            f.flush(); hf.flush()
            if k % 25 == 0:
                print(f"  {k}/{len(zakazky)} zákaziek, {spolu} cien",
                      flush=True)
    print(f"\nspolu {spolu} cien -> {out}")


if __name__ == "__main__":
    main()
