#!/usr/bin/env python3
"""Lokálny spúšťač zberu cien projektových služieb (CPV 71xx).

Použitie:
    python run_local_pd.py               # zber cien
    python run_local_pd.py --vlakna 4    # počet paralelných vlákien
    python run_local_pd.py --stav        # len vypíš, koľko zostáva

Potrebné: `pip install pypdfium2`; v data/ musí byť pd_zakazky.csv.
Prerušenie (Ctrl+C) nevadí – pokračuje cez data/pd_hotovo.txt.
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


def riadky_zoznamu():
    f = DATA / "pd_zakazky.csv"
    if not f.exists():
        raise SystemExit("chýba data/pd_zakazky.csv")
    with f.open(encoding="utf-8") as fh:
        return [r["id"] for r in csv.DictReader(fh)]


def hotove_ids():
    f = DATA / "pd_hotovo.txt"
    if not f.exists():
        return set()
    return {r.strip() for r in f.read_text().split() if r.strip()}


def zostava_pre_vlakno(i, n, ids, hotove):
    """Koľko zákaziek ešte čaká na vlákno i (rovnaké delenie ako v zbere)."""
    return sum(1 for j, zid in enumerate(ids)
               if j % n == i and zid not in hotove)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vlakna", type=int, default=4)
    ap.add_argument("--stav", action="store_true")
    args = ap.parse_args()

    ids = riadky_zoznamu()
    hotove = hotove_ids()
    zostava = sum(1 for zid in set(ids) if zid not in hotove)
    print(f"zákaziek v zozname: {len(set(ids))} | hotových: "
          f"{len(set(ids)) - zostava} | zostáva: {zostava}", flush=True)
    if args.stav or zostava == 0:
        if zostava == 0:
            print("zber je kompletný – niet čo sťahovať", flush=True)
        return

    procesy = {}
    while True:
        hotove = hotove_ids()
        aktivne = 0
        for i in range(args.vlakna):
            if zostava_pre_vlakno(i, args.vlakna, ids, hotove) == 0:
                continue                       # táto časť je hotová
            aktivne += 1
            p = procesy.get(i)
            if p is None or p.poll() is not None:
                if p is not None:
                    print(f"  vlákno {i} skončilo predčasne – reštart",
                          flush=True)
                procesy[i] = subprocess.Popen(
                    [PY, str(HERE / "10_pd_sluzby.py"),
                     "--shard", f"{i}/{args.vlakna}"], cwd=str(HERE))
        if aktivne == 0:
            break
        time.sleep(60)
        hot = len(set(ids)) - sum(1 for zid in set(ids)
                                  if zid not in hotove_ids())
        print(f"  {hot}/{len(set(ids))} zákaziek", flush=True)

    for p in procesy.values():
        if p.poll() is None:
            p.terminate()
    print("hotovo – výsledky v data/pd_ceny_shard*.csv", flush=True)


if __name__ == "__main__":
    main()
