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
from uvo_common import dokumenty_zakazky, dokument_detail, fetch

HERE = pathlib.Path(__file__).parent
DATA = HERE / "data"

TYPY_PONUKY = ("ponuky uchádzačov", "ponuka")
TYPY_PODKLADY = ("súťažné podklady",)

# sťahujeme len typy, v ktorých vie byť výkaz výmer (zip: ponuky bývajú
# zabalené aj s xlsx vnútri)
PRIPONY_OK = (".pdf", ".xls", ".xlsx", ".xlsm", ".zip")
RE_SKEN = re.compile(r"(sken|scan)")
# PDF berieme len s názvom, ktorý vyzerá na rozpočet / výkaz / cenu
RE_ROZPOCET = re.compile(
    r"(rozpoc|vykaz|cenov|kalkul|polozk|zadanie|kriteri|aukci|\bc2\b|\bvv\b)")


def normalizuj(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip().lower()


def bezpecny_nazov(s: str) -> str:
    s = normalizuj(s)
    return re.sub(r"[^a-z0-9._-]+", "_", s)[:120] or "subor"


def subor_zaujimavy(nazov: str, vsetky: bool) -> bool:
    """Filter súborov pred sťahovaním – šetrí čas aj disk."""
    if vsetky:
        return True
    n = normalizuj(nazov)
    pripona = pathlib.Path(n).suffix
    if pripona not in PRIPONY_OK:
        return False
    if RE_SKEN.search(n):
        return False
    # Excel/zip berieme vždy, PDF len ak názov naznačuje rozpočet/cenu
    if pripona == ".pdf" and not RE_ROZPOCET.search(n):
        return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit-zakaziek", type=int, default=20)
    ap.add_argument("--aj-podklady", action="store_true",
                    help="sťahuj aj súťažné podklady (neocenené výkazy)")
    ap.add_argument("--vsetky-subory", action="store_true",
                    help="vypni filter prípon a názvov (sťahuj všetko)")
    ap.add_argument("--max-pdf-mb", type=float, default=20.0,
                    help="PDF väčšie ako tento limit preskoč (skeny)")
    ap.add_argument("--shard", default="",
                    help="paralelný beh: 'i/N' spracuje riadky s indexom "
                         "i mod N (napr. 0/4)")
    args = ap.parse_args()

    with (DATA / "zakazky.csv").open(encoding="utf-8") as f:
        zakazky = list(csv.DictReader(f))
    # rovnomerná vzorka naprieč zoznamom (čerstvé záznamy sú bežiace súťaže
    # bez ponúk, staršie sú častejšie ukončené so zverejnenými ponukami)
    if len(zakazky) > args.limit_zakaziek:
        krok = len(zakazky) / args.limit_zakaziek
        zakazky = [zakazky[int(i * krok)] for i in range(args.limit_zakaziek)]
    sufix = ""
    if args.shard:
        i, n = (int(x) for x in args.shard.split("/"))
        zakazky = [z for j, z in enumerate(zakazky) if j % n == i]
        sufix = f"_shard{i}"

    # CSV zapisuj priebežne, nech sa pri prerušení behu nič nestratí
    out = DATA / f"dokumenty{sufix}.csv"
    out_f = out.open("w", newline="", encoding="utf-8")
    writer = csv.DictWriter(out_f, fieldnames=["zakazka_id", "zakazka",
                                               "doc_id", "typ", "dodavatel",
                                               "zverejnenie", "subor"])
    writer.writeheader()
    pocet = 0
    for z in zakazky:
        print(f"\n=== [{z['id']}] {z['nazov'][:70]}")
        try:
            dokumenty = dokumenty_zakazky(z["id"])
        except RuntimeError as e:
            print(f"  ! vyhľadávanie zlyhalo: {e}")
            continue
        # typ vidno už vo výsledkoch – detail otváraj len pri relevantných
        relevantne = [
            (did, typ) for did, typ in dokumenty
            if any(t in typ.lower() for t in TYPY_PONUKY)
            or (args.aj_podklady
                and any(t in typ.lower() for t in TYPY_PODKLADY))]
        print(f"  dokumentov: {len(dokumenty)}, relevantných: {len(relevantne)}")

        for did, _typ in relevantne:
            try:
                d = dokument_detail(did)
            except RuntimeError as e:
                print(f"  ! detail {did} zlyhal: {e}")
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
                if not subor_zaujimavy(nazov, args.vsetky_subory):
                    continue
                # veľké PDF = takmer isto sken (text z KROS-u má jednotky MB)
                velkost = (d["velkosti_mb"][i]
                           if i < len(d["velkosti_mb"]) else 0)
                if (nazov.lower().endswith(".pdf")
                        and velkost > args.max_pdf_mb):
                    print(f"  - preskakujem {nazov} "
                          f"({velkost:.0f} MB, zrejme sken)")
                    continue
                dst = ciel / f"{did}_{bezpecny_nazov(nazov)}"
                if not dst.exists():
                    try:
                        dst.write_bytes(fetch(link, binary=True))
                        print(f"  + {d['typ_dokumentu']}: {nazov} "
                              f"({dst.stat().st_size // 1024} kB)")
                    except RuntimeError as e:
                        print(f"  ! download zlyhal: {e}")
                        continue
                writer.writerow({
                    "zakazka_id": z["id"], "zakazka": z["nazov"],
                    "doc_id": did, "typ": d["typ_dokumentu"],
                    "dodavatel": d["dodavatel"],
                    "zverejnenie": d["zverejnenie"],
                    "subor": str(dst.relative_to(DATA)),
                })
                out_f.flush()
                pocet += 1

    out_f.close()
    print(f"\nSpolu {pocet} súborov -> {out}")


if __name__ == "__main__":
    main()
