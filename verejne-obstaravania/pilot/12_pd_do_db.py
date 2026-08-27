#!/usr/bin/env python3
"""Krok 12: nahraj ceny projektových služieb do ceny.db.

Použitie:
    python 12_pd_do_db.py --db ceny_spolu.db

Z data/pd_ceny_shard*.csv vytvorí dve tabuľky:
    pd_ceny     – surové záznamy (phz | konecna | ponuka) so zdrojom
    pd_zakazky  – jeden riadok na zákazku: PHZ, konečná cena, pomer,
                  počet ponúk, kraj, dátum, odkaz na profil ÚVO

Ceny s DPH sa prepočítajú na bez DPH (÷1,2), aby boli porovnateľné.
"""

import argparse
import csv
import glob
import pathlib
import sqlite3

HERE = pathlib.Path(__file__).parent
DATA = HERE / "data"

SCHEMA = """
DROP TABLE IF EXISTS pd_ceny;
CREATE TABLE pd_ceny (
    zakazka_id TEXT, nazov TEXT, obstaravatel TEXT, cpv TEXT, kraj TEXT,
    datum TEXT, druh_ceny TEXT, cena REAL, dph TEXT, uchadzac TEXT,
    zdroj_dokument TEXT, zdroj_url TEXT);
CREATE INDEX idx_pdc_zak ON pd_ceny(zakazka_id);

DROP TABLE IF EXISTS pd_zakazky;
CREATE TABLE pd_zakazky (
    zakazka_id TEXT PRIMARY KEY, nazov TEXT, obstaravatel TEXT, cpv TEXT,
    kraj TEXT, datum TEXT, phz REAL, konecna REAL, pomer REAL,
    pocet_ponuk INTEGER, zdroj_url TEXT);
"""


def bez_dph(cena, dph):
    return cena / 1.2 if dph == "s DPH" else cena


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="ceny_spolu.db")
    args = ap.parse_args()

    subory = glob.glob(str(DATA / "pd_ceny_shard*.csv")) + \
        glob.glob(str(DATA / "pd_ceny.csv"))
    if not subory:
        raise SystemExit("nenašiel som data/pd_ceny*.csv – najprv spusti zber")

    con = sqlite3.connect(args.db)
    con.executescript(SCHEMA)

    riadky, zak = [], {}
    for f in subory:
        with open(f, encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                try:
                    r["cena"] = float(r["cena"])
                except (ValueError, KeyError):
                    continue
                riadky.append((r["zakazka_id"], r["nazov"], r["obstaravatel"],
                               r["cpv"], r["kraj"], r["datum"], r["druh_ceny"],
                               r["cena"], r["dph"], r["uchadzac"],
                               r["zdroj_dokument"], r["zdroj_url"]))
                d = zak.setdefault(r["zakazka_id"], {
                    "nazov": r["nazov"], "obstaravatel": r["obstaravatel"],
                    "cpv": r["cpv"], "kraj": r["kraj"], "datum": r["datum"],
                    "url": r["zdroj_url"], "ponuky": []})
                c = bez_dph(r["cena"], r["dph"])
                if r["druh_ceny"] == "phz":
                    d["phz"] = min(c, d.get("phz", c))
                elif r["druh_ceny"] == "konecna":
                    d["konecna"] = min(c, d.get("konecna", c))
                else:
                    d["ponuky"].append(c)

    con.executemany("INSERT INTO pd_ceny VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    riadky)
    zapis = []
    for zid, d in zak.items():
        phz, kon = d.get("phz"), d.get("konecna")
        pomer = round(kon / phz, 3) if phz and kon and phz > 0 else None
        zapis.append((zid, d["nazov"], d["obstaravatel"], d["cpv"], d["kraj"],
                      d["datum"], phz, kon, pomer, len(d["ponuky"]), d["url"]))
    con.executemany("INSERT INTO pd_zakazky VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    zapis)
    con.commit()

    q = lambda s: con.execute(s).fetchone()[0]
    print(f"pd_ceny: {len(riadky)} záznamov")
    print(f"pd_zakazky: {len(zapis)} zákaziek "
          f"({q('SELECT count(*) FROM pd_zakazky WHERE pomer IS NOT NULL')} "
          f"s pomerom konečná/PHZ)")
    print(f"hotovo -> {args.db}")
    con.close()


if __name__ == "__main__":
    main()
