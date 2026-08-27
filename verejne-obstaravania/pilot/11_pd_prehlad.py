#!/usr/bin/env python3
"""Krok 11: prehľad cien projektových služieb z pd_ceny_shard*.csv.

Použitie:
    python 11_pd_prehlad.py                 # súhrn na obrazovku
    python 11_pd_prehlad.py --csv vystup.csv  # + tabuľka po zákazkách

Pre každú zákazku spáruje predpokladanú hodnotu (PHZ) a konečnú cenu
a spočíta pomer konečná/PHZ – najužitočnejšie číslo pri nastavovaní
vlastnej cenovej ponuky.
"""

import argparse
import collections
import csv
import glob
import pathlib
import statistics

HERE = pathlib.Path(__file__).parent
DATA = HERE / "data"


def nacitaj():
    rows = []
    for f in glob.glob(str(DATA / "pd_ceny_shard*.csv")) + \
             glob.glob(str(DATA / "pd_ceny.csv")):
        with open(f, encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                try:
                    r["cena"] = float(r["cena"])
                except (ValueError, KeyError):
                    continue
                rows.append(r)
    return rows


def bez_dph(r):
    """Prepočet na cenu bez DPH (s DPH -> /1,2; neuvedené necháme tak)."""
    if r.get("dph") == "s DPH":
        return r["cena"] / 1.2
    return r["cena"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="")
    ap.add_argument("--min-cena", type=float, default=1000.0)
    args = ap.parse_args()

    rows = [r for r in nacitaj() if r["cena"] >= args.min_cena]
    if not rows:
        raise SystemExit("žiadne dáta – najprv spusti zber")

    print(f"riadkov: {len(rows)} | zákaziek: "
          f"{len({r['zakazka_id'] for r in rows})}")
    print("podľa druhu:", dict(collections.Counter(
        r["druh_ceny"] for r in rows)))

    # po zákazkách: PHZ a konečná
    zak = collections.defaultdict(dict)
    for r in rows:
        d = zak[r["zakazka_id"]]
        d.setdefault("nazov", r["nazov"])
        d.setdefault("obstaravatel", r["obstaravatel"])
        d.setdefault("kraj", r["kraj"])
        d.setdefault("datum", r["datum"])
        d.setdefault("url", r["zdroj_url"])
        c = bez_dph(r)
        if r["druh_ceny"] == "phz":
            d["phz"] = min(c, d.get("phz", c))
        elif r["druh_ceny"] == "konecna":
            d["konecna"] = min(c, d.get("konecna", c))
        else:
            d.setdefault("ponuky", []).append(c)

    obe = {k: v for k, v in zak.items() if v.get("phz") and v.get("konecna")}
    print(f"\nzákaziek s PHZ aj konečnou cenou: {len(obe)}")
    if obe:
        pomery = sorted(v["konecna"] / v["phz"] for v in obe.values()
                        if 0.1 < v["konecna"] / v["phz"] < 3)
        if pomery:
            print(f"pomer konečná/PHZ: medián {statistics.median(pomery):.2f}"
                  f" | p25 {pomery[len(pomery)//4]:.2f}"
                  f" | p75 {pomery[3*len(pomery)//4]:.2f}"
                  f" (n={len(pomery)})")
            pod = sum(1 for p in pomery if p < 0.95)
            print(f"pod PHZ o viac ako 5 %: {100*pod//len(pomery)} % zákaziek")

    ceny = sorted(v["konecna"] for v in zak.values() if v.get("konecna"))
    if ceny:
        print(f"\nkonečné ceny bez DPH (n={len(ceny)}): "
              f"medián {statistics.median(ceny):,.0f} € | "
              f"p25 {ceny[len(ceny)//4]:,.0f} € | "
              f"p75 {ceny[3*len(ceny)//4]:,.0f} €")
        for lo, hi, popis in ((0, 20000, "do 20 tis."),
                              (20000, 50000, "20–50 tis."),
                              (50000, 150000, "50–150 tis."),
                              (150000, 10**9, "nad 150 tis.")):
            v = [c for c in ceny if lo <= c < hi]
            if v:
                print(f"  {popis:14} n={len(v):4} medián {statistics.median(v):>10,.0f} €")

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["zakazka_id", "nazov", "obstaravatel", "kraj",
                        "datum", "phz_bez_dph", "konecna_bez_dph",
                        "pomer", "pocet_ponuk", "url"])
            for zid, v in sorted(zak.items()):
                pomer = (round(v["konecna"] / v["phz"], 3)
                         if v.get("phz") and v.get("konecna") else "")
                w.writerow([zid, v["nazov"], v["obstaravatel"], v["kraj"],
                            v["datum"], round(v.get("phz", 0)) or "",
                            round(v.get("konecna", 0)) or "", pomer,
                            len(v.get("ponuky", [])), v["url"]])
        print(f"\ntabuľka -> {args.csv}")


if __name__ == "__main__":
    main()
