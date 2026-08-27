#!/usr/bin/env python3
"""Spúšťač SQL dotazov nad ceny_spolu.db – bez inštalácie čohokoľvek.

Použitie:
    python dotaz.py "SELECT * FROM pd_zakazky LIMIT 5"
    python dotaz.py --subor dotaz.sql
    python dotaz.py --csv vystup.csv "SELECT ..."
    python dotaz.py --tabulky            # zoznam tabuliek a stĺpcov

Príklady dotazov nájdeš v CLAUDE.md.
"""

import argparse
import csv
import pathlib
import sqlite3
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sql", nargs="?", default="")
    ap.add_argument("--db", default="ceny_spolu.db")
    ap.add_argument("--subor", default="", help="načítaj SQL zo súboru")
    ap.add_argument("--csv", default="", help="výsledok ulož do CSV")
    ap.add_argument("--tabulky", action="store_true")
    ap.add_argument("--limit", type=int, default=40)
    args = ap.parse_args()

    if not pathlib.Path(args.db).exists():
        raise SystemExit(f"nenašiel som {args.db}")
    con = sqlite3.connect(args.db)

    if args.tabulky:
        for (meno,) in con.execute("SELECT name FROM sqlite_master "
                                   "WHERE type='table' AND name NOT LIKE "
                                   "'%_fts_%' ORDER BY name"):
            stlpce = [r[1] for r in con.execute(f"PRAGMA table_info({meno})")]
            pocet = con.execute(f"SELECT count(*) FROM {meno}").fetchone()[0]
            print(f"{meno}  ({pocet:,} riadkov)\n    {', '.join(stlpce)}")
        return

    sql = pathlib.Path(args.subor).read_text(encoding="utf-8") \
        if args.subor else args.sql
    if not sql.strip():
        raise SystemExit('zadaj dotaz, napr.:  python dotaz.py "SELECT * '
                         'FROM pd_zakazky LIMIT 5"')

    try:
        kurzor = con.execute(sql)
    except sqlite3.Error as e:
        raise SystemExit(f"chyba v SQL: {e}")
    hlavicka = [d[0] for d in kurzor.description] if kurzor.description else []
    riadky = kurzor.fetchall()

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(hlavicka)
            w.writerows(riadky)
        print(f"{len(riadky)} riadkov -> {args.csv}")
        return

    if not riadky:
        print("(žiadne výsledky)")
        return
    sirky = [max(len(str(h)), *(len(str(r[i])[:40]) for r in riadky[:args.limit]))
             for i, h in enumerate(hlavicka)]
    print(" | ".join(str(h).ljust(s) for h, s in zip(hlavicka, sirky)))
    print("-+-".join("-" * s for s in sirky))
    for r in riadky[:args.limit]:
        print(" | ".join(str(x)[:40].ljust(s) for x, s in zip(r, sirky)))
    if len(riadky) > args.limit:
        print(f"... ({len(riadky)} riadkov spolu, zobrazených {args.limit}; "
              f"použi --csv na uloženie všetkých)")


if __name__ == "__main__":
    main()
