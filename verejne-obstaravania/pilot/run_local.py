#!/usr/bin/env python3
"""Lokálny spúšťač zberu – Windows/Linux/macOS, bez bash-u.

Použitie:
    python run_local.py               # celý zber + build databázy
    python run_local.py --vlakna 4    # menej vlákien (šetrnejšie k sieti)
    python run_local.py --len-db      # preskoč zber, len postav ceny.db

Robí to isté ako supervisor.sh: spustí krok 1 (zoznam zákaziek), potom N
vlákien kroku 2, padnuté vlákna reštartuje (pokračujú cez data/hotovo.txt),
priebežne prerieďuje ZIPy a na záver postaví ceny.db.

Potrebné: Python 3.9+, `pip install openpyxl pypdfium2`
Zber celého registra trvá rádovo 12-24 h; možno ho kedykoľvek prerušiť
(Ctrl+C) a znova spustiť – pokračuje tam, kde skončil.
"""

import argparse
import pathlib
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).parent
DATA = HERE / "data"
PY = sys.executable


def spusti(skript, *argy):
    return subprocess.Popen([PY, str(HERE / skript), *argy], cwd=str(HERE))


def pocet_zakaziek():
    csv = DATA / "zakazky.csv"
    if not csv.exists():
        return 0
    with csv.open(encoding="utf-8") as f:
        return sum(1 for _ in f) - 1


def pocet_hotovych():
    subor = DATA / "hotovo.txt"
    if not subor.exists():
        return 0
    return len({r.strip() for r in subor.read_text().split() if r.strip()})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vlakna", type=int, default=6)
    ap.add_argument("--len-db", action="store_true")
    args = ap.parse_args()
    DATA.mkdir(exist_ok=True)

    if not args.len_db:
        if pocet_zakaziek() == 0:
            print("krok 1: sťahujem zoznam zákaziek...", flush=True)
            subprocess.run([PY, str(HERE / "01_zakazky.py"),
                            "--max-stran", "200"], cwd=str(HERE))
        celkom = pocet_zakaziek()
        print(f"krok 2: {celkom} zákaziek, {args.vlakna} vlákien", flush=True)

        procesy = {}
        cyklus = 0
        while pocet_hotovych() < celkom:
            for i in range(args.vlakna):
                p = procesy.get(i)
                if p is None or p.poll() is not None:
                    procesy[i] = spusti("02_dokumenty.py",
                                        "--limit-zakaziek", "999999",
                                        "--shard", f"{i}/{args.vlakna}")
                    if p is not None:
                        print(f"  vlákno {i} spadlo – reštart", flush=True)
            time.sleep(60)
            cyklus += 1
            if cyklus % 30 == 0:          # ~raz za 30 min
                subprocess.run([PY, str(HERE / "07_prune.py")], cwd=str(HERE))
                print(f"  {pocet_hotovych()}/{celkom} zákaziek", flush=True)

        for p in procesy.values():
            if p.poll() is None:
                p.terminate()
        print("zber hotový", flush=True)

    print("build databázy...", flush=True)
    subprocess.run([PY, str(HERE / "04_postav_db.py")], cwd=str(HERE))
    print(f"hotovo -> {DATA / 'ceny.db'}", flush=True)


if __name__ == "__main__":
    main()
