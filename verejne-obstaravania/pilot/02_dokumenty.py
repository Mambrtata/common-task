#!/usr/bin/env python3
"""Krok 2: k zákazkám nájdi dokumenty v profile a stiahni ponuky.

Použitie:
    python3 02_dokumenty.py [--limit-zakaziek N] [--aj-podklady]

Číta data/zakazky.csv, hľadá dokumenty podľa názvu zákazky, sťahuje súbory
typu "Ponuky uchádzačov" (a voliteľne súťažné podklady) do data/subory/<id>/.
Metadáta zapíše do data/dokumenty.csv.
"""

import argparse
import csv
import pathlib
import re
import sys
import unicodedata

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from uvo_common import dokumenty_ids_pre_zakazku, dokument_detail, fetch

HERE = pathlib.Path(__file__).parent
DATA = HERE / "data"

TYPY_PONUKY = ("ponuky uchádzačov", "ponuka")
TYPY_PODKLADY = ("súťažné podklady",)


def normalizuj(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip().lower()


def bezpecny_nazov(s: str) -> str:
    s = normalizuj(s)
    return re.sub(r"[^a-z0-9._-]+", "_", s)[:120] or "subor"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit-zakaziek", type=int, default=20)
    ap.add_argument("--aj-podklady", action="store_true",
                    help="sťahuj aj súťažné podklady (neocenené výkazy)")
    args = ap.parse_args()

    with (DATA / "zakazky.csv").open(encoding="utf-8") as f:
        zakazky = list(csv.DictReader(f))[: args.limit_zakaziek]

    out_rows = []
    for z in zakazky:
        print(f"\n=== [{z['id']}] {z['nazov'][:70]}")
        try:
            doc_ids = dokumenty_ids_pre_zakazku(z["nazov"])
        except RuntimeError as e:
            print(f"  ! vyhľadávanie zlyhalo: {e}")
            continue
        print(f"  dokumentov nájdených: {len(doc_ids)}")

        for did in doc_ids:
            try:
                d = dokument_detail(did)
            except RuntimeError as e:
                print(f"  ! detail {did} zlyhal: {e}")
                continue
            # substring match môže chytiť inú zákazku – over zhodu názvu
            if normalizuj(z["nazov"]) not in normalizuj(d["zakazka"]):
                continue
            typ = d["typ_dokumentu"].lower()
            je_ponuka = any(t in typ for t in TYPY_PONUKY)
            je_podklad = any(t in typ for t in TYPY_PODKLADY)
            if not (je_ponuka or (args.aj_podklady and je_podklad)):
                continue

            ciel = DATA / "subory" / z["id"] / ("ponuky" if je_ponuka else "podklady")
            ciel.mkdir(parents=True, exist_ok=True)
            for i, link in enumerate(d["download_linky"]):
                nazov = (d["nazvy_suborov"][i] if i < len(d["nazvy_suborov"])
                         else f"subor_{i}")
                dst = ciel / f"{did}_{bezpecny_nazov(nazov)}"
                if not dst.exists():
                    try:
                        dst.write_bytes(fetch(link, binary=True))
                        print(f"  + {d['typ_dokumentu']}: {nazov} "
                              f"({dst.stat().st_size // 1024} kB)")
                    except RuntimeError as e:
                        print(f"  ! download zlyhal: {e}")
                        continue
                out_rows.append({
                    "zakazka_id": z["id"], "zakazka": z["nazov"],
                    "doc_id": did, "typ": d["typ_dokumentu"],
                    "dodavatel": d["dodavatel"],
                    "zverejnenie": d["zverejnenie"],
                    "subor": str(dst.relative_to(DATA)),
                })

    out = DATA / "dokumenty.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["zakazka_id", "zakazka", "doc_id",
                                          "typ", "dodavatel", "zverejnenie",
                                          "subor"])
        w.writeheader()
        w.writerows(out_rows)
    print(f"\nSpolu {len(out_rows)} súborov -> {out}")


if __name__ == "__main__":
    main()
