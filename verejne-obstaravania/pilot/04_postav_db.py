#!/usr/bin/env python3
"""Krok 4: postav ceny.db (SQLite) zo stiahnutých súborov.

Použitie:
    python3 04_postav_db.py [--db data/ceny.db]

Schéma:
    zakazky      – metadáta zákaziek (z data/zakazky.csv)
    cenove_body  – surové položky z výkazov (1 riadok = položka z 1 súboru)
    cennik_tskp  – agregovaný katalóg: kod+mj -> n, median, p25, p75, popis
    cennik_fts   – FTS5 fulltext nad katalógom (hľadanie popisom)

Ceny sú bez DPH (rozpočty sa oceňujú bez DPH). Jednotková cena sa preberá
len keď je spoľahlivo identifikovaná:
  - xlsx: trojica množstvo × jedn.cena ≈ spolu (tolerancia 2 %)
  - PDF (KROS export): dvojica čísel za MJ = množstvo, jedn. cena
"""

import argparse
import csv
import importlib.util
import pathlib
import sqlite3
import statistics
import sys
from collections import Counter, defaultdict

HERE = pathlib.Path(__file__).parent
DATA = HERE / "data"

# extrakčné funkcie zdieľame s krokom 3
spec = importlib.util.spec_from_file_location("vyhodnotenie",
                                              HERE / "03_vyhodnotenie.py")
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)


def normalizuj_polozku(kod: str, popis: str):
    """Zjednoť KROS varianty: '275313611.S' aj '275313611' + popis '.S ...'
    -> kod bez prípony, popis bez úvodného '.S'."""
    kod = kod.split(".")[0].split("-")[0]
    popis = __import__("re").sub(r"^\.\w{1,3}\s+", "", popis).strip()
    return kod, popis


def na_float(x) -> float:
    try:
        return float(str(x).replace(" ", "").replace(",", "."))
    except ValueError:
        return 0.0


def mnozstvo_a_cena(cisla, zdroj):
    """Vráti (množstvo, jedn_cena) alebo (množstvo, None), ak cenu nevieme
    spoľahlivo určiť."""
    c = [na_float(x) for x in cisla]
    if zdroj == "pdf":
        # KROS PDF: prvé dve čísla za MJ sú množstvo a jednotková cena
        if len(c) >= 2 and c[0] > 0 and c[1] > 0:
            return c[0], c[1]
        return (c[0] if c else 0), None
    # xlsx: prijmi cenu len keď množstvo × cena ≈ spolu
    if len(c) >= 3 and c[0] > 0 and c[1] > 0:
        if abs(c[0] * c[1] - c[2]) <= max(0.02 * abs(c[2]), 0.05):
            return c[0], c[1]
    return (c[0] if c else 0), None


SCHEMA = """
CREATE TABLE IF NOT EXISTS zakazky (
    id TEXT PRIMARY KEY, nazov TEXT, obstaravatel TEXT,
    cpv TEXT, cpv_popis TEXT, kraj TEXT, aktualizacia TEXT);
CREATE TABLE IF NOT EXISTS cenove_body (
    zakazka_id TEXT, subor TEXT, harok TEXT,
    kod TEXT, popis TEXT, mj TEXT,
    mnozstvo REAL, jedn_cena REAL, zdroj TEXT,
    zdroj_url TEXT);
CREATE INDEX IF NOT EXISTS idx_cb_kod ON cenove_body(kod);
"""

AGREGACIA = """
DROP TABLE IF EXISTS cennik_tskp;
CREATE TABLE cennik_tskp (
    kod TEXT, mj TEXT, popis TEXT,
    n INTEGER, median REAL, p25 REAL, p75 REAL,
    PRIMARY KEY (kod, mj));
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DATA / "ceny.db"))
    args = ap.parse_args()

    con = sqlite3.connect(args.db)
    con.executescript(SCHEMA)

    # --- zákazky ---
    with (DATA / "zakazky.csv").open(encoding="utf-8") as f:
        zak = list(csv.DictReader(f))
    con.execute("DELETE FROM zakazky")
    con.executemany(
        "INSERT OR REPLACE INTO zakazky VALUES (?,?,?,?,?,?,?)",
        [(z["id"], z["nazov"], z["obstaravatel"], z["cpv"],
          z["cpv_popis"], z["kraj"], z["aktualizacia"]) for z in zak])

    # --- CRZ zmluvy (metadáta: dátum, strany, suma) ---
    crz_csv = DATA / "crz_zmluvy.csv"
    if crz_csv.exists():
        con.execute("""CREATE TABLE IF NOT EXISTS crz_zmluvy (
            zmluva_id TEXT PRIMARY KEY, datum_davky TEXT, predmet TEXT,
            objednavatel TEXT, dodavatel TEXT, suma REAL)""")
        con.execute("DELETE FROM crz_zmluvy")
        with crz_csv.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                con.execute("INSERT OR IGNORE INTO crz_zmluvy VALUES "
                            "(?,?,?,?,?,?)",
                            (r["zmluva_id"], r["datum_davky"], r["predmet"],
                             r["objednavatel"], r["dodavatel"],
                             na_float(r["suma"])))
        n_crz = con.execute("SELECT count(*) FROM crz_zmluvy").fetchone()[0]
        print(f"crz_zmluvy: {n_crz} zmlúv "
              f"(join: cenove_body.zakazka_id = 'crz_'||zmluva_id)")

    # --- cenové body ---
    con.execute("DELETE FROM cenove_body")
    riadky, subory, s_cenou = [], 0, 0
    zdroje = [(DATA / "subory", ""), (DATA / "subory_crz", "crz_")]
    adresare = [(d, pref) for base, pref in zdroje if base.exists()
                for d in sorted(base.iterdir()) if d.is_dir()]
    for zdir, prefix in adresare:
        for f in zdir.rglob("*"):
            if not f.is_file():
                continue
            polozky = []
            for meno, data in v.najdi_xlsx(f):
                polozky += [(p, "xlsx", meno) for p in v.extrahuj_polozky(data)]
            if f.suffix.lower() == ".pdf":
                pdf_pol, _ = v.extrahuj_polozky_pdf(f)
                polozky += [(p, "pdf", f.name) for p in pdf_pol]
            if polozky:
                subory += 1
            for p, zdroj, meno in polozky:
                mn, cena = mnozstvo_a_cena(p["cisla"], zdroj)
                if cena is not None:
                    s_cenou += 1
                kod, popis = normalizuj_polozku(p["kod"], p["popis"])
                # dohľadateľný pôvod ceny – odkaz na verejný zdroj
                if prefix:
                    url = f"https://www.crz.gov.sk/zmluva/{zdir.name}/"
                else:
                    url = ("https://www.uvo.gov.sk/vyhladavanie/"
                           f"vyhladavanie-zakaziek/detail/{zdir.name}")
                riadky.append((prefix + zdir.name, meno, p["harok"], kod,
                               popis, p["mj"], mn, cena, zdroj, url))
    con.executemany("INSERT INTO cenove_body VALUES (?,?,?,?,?,?,?,?,?,?)",
                    riadky)
    print(f"cenove_body: {len(riadky)} položiek "
          f"({s_cenou} s jedn. cenou) z {subory} súborov")

    # --- katalóg: agregácia po kod+mj ---
    con.executescript(AGREGACIA)
    skupiny = defaultdict(list)
    popisy = defaultdict(Counter)
    for kod, mj, popis, cena in con.execute(
            "SELECT kod, mj, popis, jedn_cena FROM cenove_body "
            "WHERE jedn_cena IS NOT NULL AND jedn_cena > 0"):
        skupiny[(kod, mj)].append(cena)
        if popis:
            popisy[(kod, mj)][popis] += 1
    agg = []
    for (kod, mj), ceny in skupiny.items():
        ceny.sort()
        q = statistics.quantiles(ceny, n=4) if len(ceny) >= 2 else \
            [ceny[0], ceny[0], ceny[0]]
        pop = popisy[(kod, mj)].most_common(1)
        agg.append((kod, mj, pop[0][0] if pop else "", len(ceny),
                    statistics.median(ceny), q[0], q[2]))
    con.executemany("INSERT INTO cennik_tskp VALUES (?,?,?,?,?,?,?)", agg)
    print(f"cennik_tskp: {len(agg)} položiek katalógu")

    # --- číselník dielov (filter ASR vs. profesie cez prefix kódu) ---
    con.executescript("""
        DROP TABLE IF EXISTS diely;
        CREATE TABLE diely (prefix TEXT PRIMARY KEY, nazov TEXT, kategoria TEXT);
    """)
    con.executemany("INSERT INTO diely VALUES (?,?,?)", [
        ("1", "Zemné práce", "ASR-HSV"),
        ("2", "Zakladanie", "ASR-HSV"),
        ("3", "Zvislé a kompletné konštrukcie", "ASR-HSV"),
        ("4", "Vodorovné konštrukcie", "ASR-HSV"),
        ("5", "Komunikácie", "ASR-HSV"),
        ("6", "Úpravy povrchov, podlahy, výplne", "ASR-HSV"),
        ("9", "Ostatné konštrukcie, búranie, presuny", "ASR-HSV"),
        ("711", "Izolácie proti vode", "ASR-PSV"),
        ("712", "Povlakové krytiny", "ASR-PSV"),
        ("713", "Tepelné izolácie", "ASR-PSV"),
        ("721", "ZTI – kanalizácia", "profesie"),
        ("722", "ZTI – vodovod", "profesie"),
        ("723", "ZTI – plynovod", "profesie"),
        ("725", "ZTI – zariaďovacie predmety", "profesie"),
        ("731", "ÚK – kotolne", "profesie"),
        ("732", "ÚK – strojovne", "profesie"),
        ("733", "ÚK – rozvod potrubia", "profesie"),
        ("734", "ÚK – armatúry", "profesie"),
        ("735", "ÚK – vykurovacie telesá", "profesie"),
        ("762", "Konštrukcie tesárske", "ASR-PSV"),
        ("763", "Suchá výstavba (SDK)", "ASR-PSV"),
        ("764", "Klampiarske konštrukcie", "ASR-PSV"),
        ("765", "Krytiny tvrdé", "ASR-PSV"),
        ("766", "Stolárske konštrukcie", "ASR-PSV"),
        ("767", "Zámočnícke konštrukcie", "ASR-PSV"),
        ("771", "Podlahy z dlaždíc", "ASR-PSV"),
        ("775", "Podlahy vlysové a parketové", "ASR-PSV"),
        ("776", "Podlahy povlakové", "ASR-PSV"),
        ("781", "Obklady", "ASR-PSV"),
        ("783", "Nátery", "ASR-PSV"),
        ("784", "Maľby", "ASR-PSV"),
        ("210", "Elektromontáže (M21)", "profesie"),
        ("220", "Montáže oznamovacích zariadení (M22)", "profesie"),
        ("240", "Vzduchotechnika (M24)", "profesie"),
    ])

    # --- fulltext ---
    con.executescript("""
        DROP TABLE IF EXISTS cennik_fts;
        CREATE VIRTUAL TABLE cennik_fts USING fts5(
            kod, mj, popis, tokenize='unicode61 remove_diacritics 2');
    """)
    con.execute("INSERT INTO cennik_fts SELECT kod, mj, popis "
                "FROM cennik_tskp")
    con.commit()
    con.close()
    print(f"hotovo -> {args.db}")


if __name__ == "__main__":
    main()
