#!/usr/bin/env python3
"""Krok 1: zoznam zákaziek (pozemné stavby) z vyhľadávania na uvo.gov.sk.

Použitie:
    python3 01_zakazky.py [--max-stran N]

Číta CPV kódy z cpv_kody.txt, výsledok zapíše do data/zakazky.csv.
"""

import argparse
import csv
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from uvo_common import zakazky_page

HERE = pathlib.Path(__file__).parent
DATA = HERE / "data"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-stran", type=int, default=3,
                    help="max. stránok výsledkov na jeden CPV kód (10/stránka)")
    args = ap.parse_args()

    cpv_kody = [r.split("#")[0].strip() for r in
                (HERE / "cpv_kody.txt").read_text().splitlines()]
    cpv_kody = [c for c in cpv_kody if c]

    DATA.mkdir(exist_ok=True)
    vsetky, videne = [], set()
    for cpv in cpv_kody:
        for page_no in range(1, args.max_stran + 1):
            riadky = zakazky_page(cpv, page_no)
            nove = [r for r in riadky if r["id"] not in videne]
            videne.update(r["id"] for r in nove)
            vsetky.extend(nove)
            print(f"CPV {cpv} strana {page_no}: +{len(nove)} zákaziek")
            # za poslednou stránkou vracia server tie isté riadky
            if len(riadky) < 10 or not nove:
                break

    out = DATA / "zakazky.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "nazov", "obstaravatel",
                                          "cpv", "cpv_popis", "kraj",
                                          "aktualizacia"])
        w.writeheader()
        w.writerows(vsetky)
    print(f"\nSpolu {len(vsetky)} zákaziek -> {out}")


if __name__ == "__main__":
    main()
