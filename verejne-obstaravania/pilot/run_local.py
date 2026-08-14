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
    """Počet UNIKÁTNYCH zákaziek (jedna zákazka býva pod viacerými CPV)."""
    subor = DATA / "zakazky.csv"
    if not subor.exists():
        return 0
    import csv as _csv
    with subor.open(encoding="utf-8") as f:
        return len({r["id"] for r in _csv.DictReader(f)})


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
        cyklus, bez_pokroku, posledny = 0, 0, pocet_hotovych()
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

            # ochrana proti nekonečnej slučke: keď 5 minút nepribudne nič,
            # zvyšné zákazky sú nedostupné (chyby pri sťahovaní) – končíme
            teraz = pocet_hotovych()
            bez_pokroku = 0 if teraz > posledny else bez_pokroku + 1
            posledny = teraz
            if bez_pokroku >= 5:
                print(f"  žiadny pokrok, končím na {teraz}/{celkom} "
                      f"(zvyšok sa nepodarilo stiahnuť)", flush=True)
                break

            if cyklus % 30 == 0:          # ~raz za 30 min
                subprocess.run([PY, str(HERE / "07_prune.py")], cwd=str(HERE))
                print(f"  {teraz}/{celkom} zákaziek", flush=True)

        for p in procesy.values():
            if p.poll() is None:
                p.terminate()
        print("zber hotový", flush=True)

    print("build databázy...", flush=True)
    subprocess.run([PY, str(HERE / "04_postav_db.py")], cwd=str(HERE))
    print(f"hotovo -> {DATA / 'ceny.db'}", flush=True)


if __name__ == "__main__":
    main()
