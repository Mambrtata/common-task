#!/usr/bin/env python3
"""Krok 7: prerieď stiahnuté ZIPy – nechaj len rozpočtové súbory.

Použitie:
    python3 07_prune.py [--min-vek-s 180]

Z každého ZIPu v data/subory vytiahne členy relevantné pre rozpočty
(Excel vždy; PDF len s rozpočtovým názvom, do 20 MB) vedľa archívu
(prefix <zip>__) a ZIP zmaže. Šetrí disk ~10× a sprístupní PDF rozpočty
vnútri archívov, ktoré extrakcia z archívov nečítala.
"""

import argparse
import pathlib
import re
import sys
import time
import unicodedata
import zipfile

HERE = pathlib.Path(__file__).parent
DATA = HERE / "data"

RE_ROZPOCET = re.compile(
    r"(rozpoc|vykaz|cenov|kalkul|polozk|zadanie|kriteri|aukci|\bc2\b|\bvv\b)")
RE_SKEN = re.compile(r"(sken|scan)")


def normalizuj(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip().lower()


def bezpecny(s: str) -> str:
    return re.sub(r"[^a-z0-9._-]+", "_", normalizuj(s))[:100]


def clen_relevantny(nazov: str, velkost: int) -> bool:
    n = normalizuj(nazov)
    pripona = pathlib.Path(n).suffix
    if pripona in (".xlsx", ".xlsm", ".xls"):
        return True
    if pripona == ".pdf":
        if RE_SKEN.search(n) or velkost > 20e6:
            return False
        return bool(RE_ROZPOCET.search(n))
    return False


def preried_zip(zippath: pathlib.Path) -> tuple:
    """Vráti (usporene_B, extrahovanych)."""
    velkost_zip = zippath.stat().st_size
    extrahovane = 0
    try:
        with zipfile.ZipFile(zippath) as z:
            for info in z.infolist():
                if info.is_dir():
                    continue
                if not clen_relevantny(info.filename, info.file_size):
                    continue
                meno = bezpecny(pathlib.Path(info.filename).name)
                dst = zippath.parent / f"{zippath.stem[:40]}__{meno}"
                if not dst.exists():
                    dst.write_bytes(z.read(info))
                extrahovane += 1
    except (zipfile.BadZipFile, NotImplementedError, RuntimeError):
        # poškodený/šifrovaný archív – zmaž, nedá sa využiť
        pass
    zippath.unlink()
    return velkost_zip, extrahovane


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-vek-s", type=int, default=180,
                    help="nechaj ZIPy mladšie ako toto (možno sa ešte sťahujú)")
    args = ap.parse_args()

    teraz = time.time()
    usporene, zipov, suborov = 0, 0, 0
    for zippath in sorted(DATA.rglob("subory/**/*.zip")):
        if teraz - zippath.stat().st_mtime < args.min_vek_s:
            continue
        v, e = preried_zip(zippath)
        usporene += v
        zipov += 1
        suborov += e
    print(f"prerieďených {zipov} ZIPov, extrahovaných {suborov} súborov, "
          f"ušetrené {usporene / 1e9:.1f} GB")


if __name__ == "__main__":
    main()
