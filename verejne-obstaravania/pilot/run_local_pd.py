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

    procesy = {}
    bez_pokroku, posledny = 0, pocet_hotovych()
    while pocet_hotovych() < celkom:
        for i in range(args.vlakna):
            p = procesy.get(i)
            if p is None or p.poll() is not None:
                procesy[i] = subprocess.Popen(
                    [PY, str(HERE / "10_pd_sluzby.py"),
                     "--shard", f"{i}/{args.vlakna}"], cwd=str(HERE))
                if p is not None:
                    print(f"  vlákno {i} spadlo – reštart", flush=True)
        time.sleep(60)

        teraz = pocet_hotovych()
        bez_pokroku = 0 if teraz > posledny else bez_pokroku + 1
        posledny = teraz
        print(f"  {teraz}/{celkom} zákaziek", flush=True)
        if bez_pokroku >= 5:
            print(f"  žiadny pokrok, končím na {teraz}/{celkom}", flush=True)
            break

    for p in procesy.values():
        if p.poll() is None:
            p.terminate()
    print("hotovo – výsledky v data/pd_ceny_shard*.csv", flush=True)


if __name__ == "__main__":
    main()
