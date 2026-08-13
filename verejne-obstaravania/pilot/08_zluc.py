#!/usr/bin/env python3
"""Krok 8: zlúč viac ceny.db do jednej databázy.

Použitie:
    python3 08_zluc.py --do ceny_spolu.db ceny-cloud.db ceny-lokal.db

Spojí surové tabuľky (cenove_body, zakazky, crz_zmluvy) z viacerých
databáz, odstráni duplicity (rovnaká položka z rovnakého súboru
rovnakej zákazky) a prepočíta katalóg cennik_tskp, fulltext aj číselník
dielov. Vstupné databázy ostávajú nedotknuté.
"""

import argparse
import pathlib
import sqlite3
import statistics
from collections import Counter, defaultdict

DIELY = [
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
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS zakazky (
    id TEXT PRIMARY KEY, nazov TEXT, obstaravatel TEXT,
    cpv TEXT, cpv_popis TEXT, kraj TEXT, aktualizacia TEXT);
CREATE TABLE IF NOT EXISTS crz_zmluvy (
    zmluva_id TEXT PRIMARY KEY, datum_davky TEXT, predmet TEXT,
    objednavatel TEXT, dodavatel TEXT, suma REAL);
CREATE TABLE IF NOT EXISTS cenove_body (
    zakazka_id TEXT, subor TEXT, harok TEXT,
    kod TEXT, popis TEXT, mj TEXT,
    mnozstvo REAL, jedn_cena REAL, zdroj TEXT, zdroj_url TEXT);
CREATE INDEX IF NOT EXISTS idx_cb_kod ON cenove_body(kod);
"""


def stlpce(con, tabulka):
    return [r[1] for r in con.execute(f"PRAGMA table_info({tabulka})")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--do", dest="ciel", default="ceny_spolu.db")
    ap.add_argument("zdroje", nargs="+")
    args = ap.parse_args()

    ciel = pathlib.Path(args.ciel)
    if ciel.exists():
        ciel.unlink()
    out = sqlite3.connect(str(ciel))
    out.executescript(SCHEMA)

    videne = set()
    spolu_cb = 0
    for zdroj in args.zdroje:
        src = sqlite3.connect(f"file:{zdroj}?mode=ro", uri=True)
        # zákazky a CRZ zmluvy – jednoduchý union podľa primárneho kľúča
        for tab, pocet_st in (("zakazky", 7), ("crz_zmluvy", 6)):
            try:
                riadky = src.execute(f"SELECT * FROM {tab}").fetchall()
            except sqlite3.OperationalError:
                continue
            otazniky = ",".join("?" * pocet_st)
            out.executemany(
                f"INSERT OR IGNORE INTO {tab} VALUES ({otazniky})", riadky)

        # cenové body – dedup podľa (zákazka, súbor, kód, popis, mj, cena)
        ma_url = "zdroj_url" in stlpce(src, "cenove_body")
        sql = ("SELECT zakazka_id, subor, harok, kod, popis, mj, mnozstvo, "
               "jedn_cena, zdroj" + (", zdroj_url" if ma_url else "") +
               " FROM cenove_body")
        nove = []
        for r in src.execute(sql):
            if not ma_url:
                r = r + (None,)
            kluc = (r[0], r[1], r[3], r[4], r[5], r[7])
            if kluc in videne:
                continue
            videne.add(kluc)
            nove.append(r)
        out.executemany(
            "INSERT INTO cenove_body VALUES (?,?,?,?,?,?,?,?,?,?)", nove)
        spolu_cb += len(nove)
        print(f"{zdroj}: +{len(nove)} nových cenových bodov")
        src.close()

    # --- prepočet katalógu ---
    out.executescript("""
        DROP TABLE IF EXISTS cennik_tskp;
        CREATE TABLE cennik_tskp (
            kod TEXT, mj TEXT, popis TEXT,
            n INTEGER, median REAL, p25 REAL, p75 REAL,
            PRIMARY KEY (kod, mj));
    """)
    skupiny, popisy = defaultdict(list), defaultdict(Counter)
    for kod, mj, popis, cena in out.execute(
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
    out.executemany("INSERT INTO cennik_tskp VALUES (?,?,?,?,?,?,?)", agg)

    # --- číselník dielov + fulltext ---
    out.executescript("""
        DROP TABLE IF EXISTS diely;
        CREATE TABLE diely (prefix TEXT PRIMARY KEY, nazov TEXT,
                            kategoria TEXT);
        DROP TABLE IF EXISTS cennik_fts;
        CREATE VIRTUAL TABLE cennik_fts USING fts5(
            kod, mj, popis, tokenize='unicode61 remove_diacritics 2');
    """)
    out.executemany("INSERT INTO diely VALUES (?,?,?)", DIELY)
    out.execute("INSERT INTO cennik_fts SELECT kod, mj, popis FROM cennik_tskp")
    out.commit()

    print(f"\nspolu: {spolu_cb} cenových bodov, {len(agg)} položiek katalógu")
    print(f"hotovo -> {ciel}")
    out.close()


if __name__ == "__main__":
    main()
