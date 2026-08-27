#!/usr/bin/env python3
"""Krok 13: samostatná databáza cien projektových služieb (pd.db).

Použitie:
    python 13_pd_db.py                 # -> pd.db
    python 13_pd_db.py --db mojapd.db

Z data/pd_ceny_shard*.csv postaví čistú databázu len pre projektové
a inžinierske služby (CPV 71xx) – bez stavebných prác:

    pd_zakazky   – jedna zákazka na riadok: PHZ, konečná cena, pomer,
                   počet ponúk, kraj, dátum, odkaz na profil ÚVO
    pd_ceny      – surové cenové záznamy (phz | konecna | ponuka)
    pd_fts       – fulltext nad názvom a obstarávateľom (bez diakritiky)
    pd_statistika– mediány a kvartily podľa veľkostného pásma

Ceny s DPH sa prepočítajú na bez DPH (÷1,2).
"""

import argparse
import csv
import glob
import pathlib
import sqlite3
import statistics

HERE = pathlib.Path(__file__).parent
DATA = HERE / "data"

PASMA = ((0, 20000, "do 20 tis."), (20000, 50000, "20-50 tis."),
         (50000, 150000, "50-150 tis."), (150000, 10**9, "nad 150 tis."))

SCHEMA = """
DROP TABLE IF EXISTS pd_ceny;
CREATE TABLE pd_ceny (
    zakazka_id TEXT, nazov TEXT, obstaravatel TEXT, cpv TEXT, kraj TEXT,
    datum TEXT, druh_ceny TEXT, cena REAL, dph TEXT, uchadzac TEXT,
    zdroj_dokument TEXT, zdroj_url TEXT, stupen TEXT, ic INTEGER,
    ad INTEGER);
CREATE INDEX idx_pdc_zak ON pd_ceny(zakazka_id);

DROP TABLE IF EXISTS pd_zakazky;
CREATE TABLE pd_zakazky (
    zakazka_id TEXT PRIMARY KEY, nazov TEXT, obstaravatel TEXT, cpv TEXT,
    kraj TEXT, datum TEXT, rok TEXT, phz REAL, konecna REAL, pomer REAL,
    pocet_ponuk INTEGER, stupen TEXT, ic INTEGER, ad INTEGER,
    zdroj_url TEXT);
CREATE INDEX idx_pdz_phz ON pd_zakazky(phz);

DROP TABLE IF EXISTS pd_statistika;
CREATE TABLE pd_statistika (
    pasmo TEXT, ukazovatel TEXT, n INTEGER,
    median REAL, p25 REAL, p75 REAL);

DROP TABLE IF EXISTS pd_fts;
CREATE VIRTUAL TABLE pd_fts USING fts5(
    zakazka_id, nazov, obstaravatel,
    tokenize='unicode61 remove_diacritics 2');
"""


def bez_dph(cena, dph):
    return cena / 1.2 if dph == "s DPH" else cena


def kvartily(v):
    v = sorted(v)
    if not v:
        return (None, None, None)
    return (statistics.median(v), v[len(v) // 4], v[3 * len(v) // 4])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="pd.db")
    args = ap.parse_args()

    subory = glob.glob(str(DATA / "pd_ceny_shard*.csv")) + \
        glob.glob(str(DATA / "pd_ceny.csv"))
    if not subory:
        raise SystemExit("nenašiel som data/pd_ceny*.csv")

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
                riadky.append(tuple(r.get(k, "") for k in (
                    "zakazka_id", "nazov", "obstaravatel", "cpv", "kraj",
                    "datum", "druh_ceny", "cena", "dph", "uchadzac",
                    "zdroj_dokument", "zdroj_url", "stupen", "ic", "ad")))
                d = zak.setdefault(r["zakazka_id"], {
                    "nazov": r["nazov"], "obstaravatel": r["obstaravatel"],
                    "cpv": r["cpv"], "kraj": r["kraj"], "datum": r["datum"],
                    "url": r["zdroj_url"], "ponuky": [],
                    "stupen": "", "ic": 0, "ad": 0})
                if r.get("stupen"):
                    d["stupen"] = d["stupen"] or r["stupen"]
                d["ic"] = max(d["ic"], int(r.get("ic") or 0))
                d["ad"] = max(d["ad"], int(r.get("ad") or 0))
                c = bez_dph(r["cena"], r["dph"])
                if r["druh_ceny"] == "phz":
                    d["phz"] = min(c, d.get("phz", c))
                elif r["druh_ceny"] == "konecna":
                    d["konecna"] = min(c, d.get("konecna", c))
                else:
                    d["ponuky"].append(c)

    con.executemany("INSERT INTO pd_ceny VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    riadky)

    zapis = []
    for zid, d in zak.items():
        phz, kon = d.get("phz"), d.get("konecna")
        pomer = round(kon / phz, 3) if phz and kon and phz > 0 else None
        rok = (d["datum"] or "")[-4:]
        zapis.append((zid, d["nazov"], d["obstaravatel"], d["cpv"], d["kraj"],
                      d["datum"], rok if rok.isdigit() else "", phz, kon,
                      pomer, len(d["ponuky"]), d["stupen"], d["ic"], d["ad"],
                      d["url"]))
    con.executemany("INSERT INTO pd_zakazky VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    zapis)
    con.execute("INSERT INTO pd_fts SELECT zakazka_id, nazov, obstaravatel "
                "FROM pd_zakazky")

    # štatistika po veľkostných pásmach
    stat = []
    for lo, hi, popis in PASMA:
        ceny = [z[8] for z in zapis if z[8] and lo <= z[8] < hi]
        m, a, b = kvartily(ceny)
        if m:
            stat.append((popis, "konecna_cena", len(ceny), m, a, b))
        pomery = [z[9] for z in zapis
                  if z[9] and z[7] and lo <= z[7] < hi and 0.1 < z[9] < 3]
        m, a, b = kvartily(pomery)
        if m:
            stat.append((popis, "pomer_konecna_phz", len(pomery), m, a, b))
    vsetky = [z[9] for z in zapis if z[9] and 0.1 < z[9] < 3]
    m, a, b = kvartily(vsetky)
    if m:
        stat.append(("spolu", "pomer_konecna_phz", len(vsetky), m, a, b))
    con.executemany("INSERT INTO pd_statistika VALUES (?,?,?,?,?,?)", stat)
    con.commit()

    q = lambda s: con.execute(s).fetchone()[0]
    print(f"pd_zakazky: {len(zapis)} zákaziek "
          f"({q('SELECT count(*) FROM pd_zakazky WHERE pomer IS NOT NULL')} "
          f"s pomerom, {q('SELECT count(*) FROM pd_zakazky WHERE konecna IS NOT NULL')} "
          f"s konečnou cenou)")
    print(f"pd_ceny: {len(riadky)} záznamov")
    print("\npd_statistika:")
    for r in con.execute("SELECT * FROM pd_statistika"):
        print(f"  {r[0]:12} {r[1]:18} n={r[2]:4}  medián {r[3]:>10,.2f}"
              f"  p25 {r[4]:>10,.2f}  p75 {r[5]:>10,.2f}")
    zn = q("SELECT count(*) FROM pd_zakazky WHERE stupen <> ''")
    print(f"\nrozsah zistený pri {zn} zákazkách "
          f"(stupeň PD; IČ/AD ako príznaky)")
    print(f"hotovo -> {args.db}")
    con.close()


if __name__ == "__main__":
    main()
