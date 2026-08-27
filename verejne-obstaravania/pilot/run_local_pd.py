#!/usr/bin/env python3
"""Lokálny spúšťač zberu cien projektových služieb (CPV 71xx).

Použitie:
    python run_local_pd.py                # zber cien pre všetky zákazky
    python run_local_pd.py --vlakna 4     # počet paralelných vlákien

Potrebné: Python 3.9+, `pip install pypdfium2`
V priečinku data/ musí byť pd_zakazky.csv (zoznam zákaziek).
Beh sa dá kedykoľvek prerušiť (Ctrl+C) – pokračuje cez data/pd_hotovo.txt.
Výsledok: data/pd_ceny_shard*.csv
"""

import argparse
import csv
import pathlib
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).parent
DATA = HERE / "data"
PY = sys.executable


def pocet_zakaziek():
    f = DATA / "pd_zakazky.csv"
    if not f.exists():
        return 0
    with f.open(encoding="utf-8") as fh:
        return len({r["id"] for r in csv.DictReader(fh)})


def pocet_hotovych():
    f = DATA / "pd_hotovo.txt"
    if not f.exists():
        return 0
    return len({r.strip() for r in f.read_text().split() if r.strip()})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vlakna", type=int, default=4)
    args = ap.parse_args()

    celkom = pocet_zakaziek()
    if celkom == 0:
        raise SystemExit("chýba data/pd_zakazky.csv – najprv "
                         "`python 10_pd_sluzby.py --zoznam`")
    print(f"zákaziek: {celkom}, vlákien: {args.vlakna}", flush=True)

    def spusti(i):
        return subprocess.Popen(
            [PY, str(HERE / "10_pd_sluzby.py"),
             "--shard", f"{i}/{args.vlakna}"], cwd=str(HERE))

    # Vlákno, ktoré nemá čo robiť, skončí do pár sekúnd. Dvakrát po sebe
    # rýchly koniec = jeho časť je hotová (nie pád) -> nereštartuj ho.
    procesy, hotove, rychle = {}, set(), {}
    while len(hotove) < args.vlakna:
        for i in range(args.vlakna):
            if i in hotove:
                continue
            zaznam = procesy.get(i)
            if zaznam is None:
                procesy[i] = (spusti(i), time.time())
                continue
            p, start = zaznam
            if p.poll() is None:
                continue                      # beží ďalej
            if time.time() - start < 45:      # skončil hneď
                rychle[i] = rychle.get(i, 0) + 1
                if rychle[i] >= 2:
                    hotove.add(i)
                    print(f"  vlákno {i} hotové", flush=True)
                    continue
            else:
                rychle[i] = 0
                print(f"  vlákno {i} spadlo – reštart", flush=True)
            procesy[i] = (spusti(i), time.time())
        time.sleep(60)
        print(f"  {pocet_hotovych()}/{celkom} zákaziek", flush=True)

    for zaznam in procesy.values():
        if zaznam[0].poll() is None:
            zaznam[0].terminate()
    print("hotovo – výsledky v data/pd_ceny_shard*.csv", flush=True)


if __name__ == "__main__":
    main()
