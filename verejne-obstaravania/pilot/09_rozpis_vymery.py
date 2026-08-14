#!/usr/bin/env python3
"""Krok 9: vytiahni rozpis výmery z výkazov do tabuľky `rozpis_vymery`.

Použitie:
    python3 09_rozpis_vymery.py [--db ceny_spolu.db]

POZOR na terminológiu: skutočné *figúry* sú v KROS-e pomenované
premenné (Názov / Popis / Aritmetický výraz / Hodnota) a do exportu sa
dostanú len keď obstarávateľ zaškrtne „s figúrami" – vo zverejnených
výkazoch preto prakticky nikdy nie sú (hárok „Figury" býva prázdny).

Tento skript číta *rozpis výmery* – riadky pod položkou, kde je výmera
rozpísaná na rozmery, napr.
    2,6*2,5*1,4
    "objem, výkopy pre základové pätky" 0,5*0,6*0,8*2
    "2.NP" 19+18
    2.621*2.30+3.00*2.445-0.80*2.05*2      (s odpočtom otvorov)

Každý rozpis sa viaže na naposledy videný TSKP kód.

Výsledok: tabuľka rozpis_vymery(kod, popis_polozky, mj, popis_riadku,
vyraz, hodnota, zdroj_subor) – ukazuje, ako sa výmera odvodzuje
z rozmerov konštrukcie.
"""

import argparse
import io
import pathlib
import re
import sqlite3
import warnings
import zipfile

warnings.filterwarnings("ignore")

try:
    import openpyxl
except ImportError:
    raise SystemExit("chýba openpyxl: pip install openpyxl")

HERE = pathlib.Path(__file__).parent
DATA = HERE / "data"

RE_KOD = re.compile(r"^\d{6,9}([.-]\w+)?$")
# Výmera sa počíta násobením a sčítaním; '/' a '-' v rozpočtoch označujú
# rozmery výrobkov (600/600/10) a rozsahy, preto ich ako začiatok výrazu
# neberieme – inak vzniká viac šumu než dát.
RE_VYRAZ = re.compile(r"\d+(?:[.,]\d+)?\s*[*+]\s*\d")
RE_CISTY = re.compile(r"^[\d\s.,+*()-]+$")   # bez '/'
MJ_ZNAME = {"m", "m2", "m3", "kus", "ks", "t", "kg", "sub", "súb", "bm", "hod"}


def vyhodnot(vyraz: str):
    """Bezpečne vyčísli aritmetický výraz (len čísla a + - * / zátvorky)."""
    v = vyraz.replace(",", ".").replace(" ", "")
    if not re.fullmatch(r"[\d.+*/()-]+", v):
        return None
    try:
        return round(float(eval(v, {"__builtins__": {}}, {})), 4)
    except Exception:
        return None


def rozdel(text: str):
    """Z bunky vytiahne (popis, výraz). Popis je text pred výrazom."""
    m = RE_VYRAZ.search(text)
    if not m:
        return None
    # výraz = najdlhší súvislý aritmetický úsek okolo zhody
    zac = m.start()
    while zac > 0 and text[zac - 1] in "0123456789.,+*()- ":
        zac -= 1
    kon = m.end()
    while kon < len(text) and text[kon] in "0123456789.,+*()- ":
        kon += 1
    vyraz = text[zac:kon].strip(" -")
    popis = text[:zac].strip(' "\':;,-')
    if not RE_CISTY.match(vyraz) or not RE_VYRAZ.search(vyraz):
        return None
    # aspoň jedno desatinné číslo alebo násobenie – vylúči "1+2", "3+3"
    if "*" not in vyraz and not re.search(r"\d[.,]\d", vyraz):
        return None
    return popis[:80], vyraz[:120]


def spracuj_zosit(data: bytes, meno: str):
    rozpisy = []
    try:
        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True,
                                    data_only=True)
    except Exception:
        return rozpisy
    for ws in wb.worksheets:
        if "figur" in ws.title.lower():
            continue                      # vyhradený hárok býva prázdny
        kod = popis_pol = mj = None
        for row in ws.iter_rows(values_only=True):
            hodnoty = [c for c in row if c is not None]
            if not hodnoty:
                continue
            # riadok položky? -> zapamätaj kontext
            novy_kod = next((str(c).strip() for c in hodnoty
                             if RE_KOD.match(str(c).strip())), None)
            if novy_kod:
                kod = novy_kod.split(".")[0]
                popis_pol = next((str(c)[:90] for c in hodnoty
                                  if isinstance(c, str) and len(c) > 12
                                  and not RE_KOD.match(c.strip())), "")
                mj = next((str(c).strip().lower() for c in hodnoty
                           if str(c).strip().lower() in MJ_ZNAME), "")
                continue
            # riadok s rozpisom výmery (patrí k poslednej položke)
            if not kod:
                continue
            for c in hodnoty:
                if not isinstance(c, str) or len(c) > 200:
                    continue
                r = rozdel(c)
                if not r:
                    continue
                popis_riadku, vyraz = r
                rozpisy.append((kod, popis_pol or "", mj or "", popis_riadku,
                               vyraz, vyhodnot(vyraz), meno))
    wb.close()
    return rozpisy


def zosity(f: pathlib.Path):
    if f.suffix.lower() in (".xlsx", ".xlsm"):
        return [(f.name, f.read_bytes())]
    if f.suffix.lower() == ".zip":
        out = []
        try:
            with zipfile.ZipFile(f) as z:
                for n in z.namelist():
                    if n.lower().endswith((".xlsx", ".xlsm")):
                        out.append((n, z.read(n)))
        except zipfile.BadZipFile:
            pass
        return out
    return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DATA / "ceny.db"))
    args = ap.parse_args()

    con = sqlite3.connect(args.db)
    con.executescript("""
        DROP TABLE IF EXISTS rozpis_vymery;
        CREATE TABLE rozpis_vymery (
            kod TEXT, popis_polozky TEXT, mj TEXT,
            popis_riadku TEXT, vyraz TEXT, hodnota REAL, zdroj_subor TEXT);
        CREATE INDEX idx_rv_kod ON rozpis_vymery(kod);
    """)

    spolu, suborov = 0, 0
    for base in (DATA / "subory", DATA / "subory_crz"):
        if not base.exists():
            continue
        for f in base.rglob("*"):
            if not f.is_file():
                continue
            for meno, data in zosity(f):
                rv = spracuj_zosit(data, meno)
                if rv:
                    con.executemany(
                        "INSERT INTO rozpis_vymery VALUES (?,?,?,?,?,?,?)", rv)
                    spolu += len(rv)
                    suborov += 1
                    if suborov % 50 == 0:
                        con.commit()
                        print(f"  {suborov} súborov, {spolu} rozpisov",
                              flush=True)
    con.commit()
    print(f"\nrozpis_vymery: {spolu} záznamov z {suborov} súborov -> {args.db}")
    con.close()


if __name__ == "__main__":
    main()
