#!/usr/bin/env python3
"""Kontrola cenovej ponuky proti databáze reálnych cien.

Použitie:
    python 14_kontrola_cp.py "cesta/k/ponuke.xlsx"
    python 14_kontrola_cp.py ponuka.xlsx --db ceny_spolu.db --csv kontrola.csv
    python 14_kontrola_cp.py ponuka.xlsx --min-dopad 200   # len položky s dopadom nad 200 €

Prejde položky z xlsx (aj viac hárkov, aj zip s xlsx), ku každej nájde
porovnateľnú položku v katalógu `cennik_tskp` – najprv podľa TSKP kódu,
ak kód chýba alebo nie je v databáze, tak podľa popisu (prekryv slov,
bez ohľadu na diakritiku) pri rovnakej MJ. Vypíše:

    j. cena v ponuke | medián trhu (p25–p75, n) | odchýlka % | dopad v €

„Dopad" = (cena v ponuke − medián) × množstvo, teda o koľko eur je tá
jedna položka nad/pod trhom. Tabuľka je zoradená podľa dopadu, takže
hore sú položky, kde sa dá najviac ušetriť.

Pozor: medián je z verejných súťaží (bez DPH) a pri n < 3 je len
orientačný. Rozdiel nemusí byť nadsadená cena – môže ísť o iný výrobok,
malé množstvo, náročný prístup alebo taktické ocenenie. Skript hľadá, na
čo sa treba pozrieť, nerozhoduje.
"""

import argparse
import csv
import importlib.util
import io
import pathlib
import re
import sqlite3
import sys
import unicodedata
import zipfile

HERE = pathlib.Path(__file__).parent

spec = importlib.util.spec_from_file_location("vyhodnotenie",
                                              HERE / "03_vyhodnotenie.py")
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)
# KROS „vlastná položka" je cenníková položka s pripojenou príponou
# (625250058 -> 62525005810), takže kód môže mať aj 10-12 číslic. Krok 3
# ich zámerne nepozná (do databázy sa majú dostať len čisté cenníkové
# kódy), tu ich ale potrebujeme rozoznať a skrátiť na základ.
v.RE_TSKP = re.compile(r"^\d{6,12}([.-]\w+)?$")

spec4 = importlib.util.spec_from_file_location("postav",
                                               HERE / "04_postav_db.py")
# 04 má pri importe argparse až v main(), takže sa dá bezpečne načítať
p4 = importlib.util.module_from_spec(spec4)
spec4.loader.exec_module(p4)

# slová, ktoré o položke nič nepovedia – do porovnania popisov nejdú
STOP = {"a", "s", "so", "v", "vo", "na", "z", "zo", "do", "pre", "pri", "o",
        "montaz", "montaze", "dodavka", "dodanie", "vratane", "vcitane",
        "vcetne", "d+m", "m+d", "ks", "mm", "cm", "m", "m2", "m3", "hr",
        "hrubky", "hrubka", "typ", "ref", "napr", "apod", "pod", "podla",
        "ostatne", "ine", "praca", "prace", "celkom", "spolu", "poznamka"}


def bez_diakritiky(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s).lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def tokeny(popis: str):
    slova = re.findall(r"[a-z0-9]+", bez_diakritiky(popis))
    return {s for s in slova if len(s) > 2 and s not in STOP}


RE_HRUBKA = re.compile(r"(?:hr\.?|hrubk\w*)\s*(?:do\s*)?(\d{1,3}(?:[.,]\d+)?)\s*(mm|cm)")


def hrubka_mm(popis: str):
    """Hrúbka z popisu v mm – '…hr. 25 mm', 'hrúbky 4 cm'. Inak None.

    Tá istá veta pri inej hrúbke je iná položka (poter 5 vs. 25 mm), preto
    sa hrúbky musia zhodovať, inak by medián klamal.
    """
    m = RE_HRUBKA.search(bez_diakritiky(popis))
    if not m:
        return None
    cislo = float(m.group(1).replace(",", "."))
    return cislo * (10 if m.group(2) == "cm" else 1)


def nacitaj_katalog(db_cesta):
    db = sqlite3.connect(db_cesta)
    try:
        riadky = db.execute(
            "SELECT kod, mj, popis, n, median, p25, p75 FROM cennik_tskp"
        ).fetchall()
    except sqlite3.OperationalError as e:
        raise SystemExit(f"v {db_cesta} nie je tabuľka cennik_tskp ({e})")
    podla_kodu, podla_mj = {}, {}
    for kod, mj, popis, n, med, p25, p75 in riadky:
        zaznam = (kod, mj, popis, n, med, p25, p75, tokeny(popis))
        podla_kodu.setdefault((kod, (mj or "").lower()), []).append(zaznam)
        podla_mj.setdefault((mj or "").lower(), []).append(zaznam)
    return podla_kodu, podla_mj


def najdi(polozka, podla_kodu, podla_mj):
    """Vráti (zaznam_z_katalogu, ako_sme_nasli) alebo (None, dovod).

    Pri hľadaní podľa popisu musí zhoda platiť na OBE strany. Keď položka
    z ponuky obsahuje veci, ktoré katalógová položka nepokrýva (typicky
    „zateplenie + fólie + práca" proti samotnej montáži izolácie), nie je
    to tá istá položka – porovnanie by vyšlo ako niekoľkonásobné
    predraženie, hoci v ponuke je len zlúčených viac vrstiev. Taký riadok
    označíme ako skladaný a cenu k nemu nedáme.
    """
    mj = (polozka["mj"] or "").lower()
    kod = polozka["kod"].split(".")[0].split("-")[0] if polozka["kod"] else ""
    if len(kod) > 9:
        kod = kod[:9]          # KROS vlastná položka -> cenníkový základ
    if kod:
        # zhodný kód a MJ je najsilnejšia zhoda; vyber najčastejší variant
        kand = podla_kodu.get((kod, mj))
        if kand:
            return max(kand, key=lambda z: z[3]), "kód"
    tok = tokeny(polozka["popis"])
    if len(tok) < 2:
        return None, ""
    hr_cp = hrubka_mm(polozka["popis"])
    najlepsi, najskore, najpokr_kat = None, 0.0, 0.0
    for zaznam in podla_mj.get(mj, ()):
        spolocne = tok & zaznam[7]
        if len(spolocne) < 2:
            continue
        if hr_cp:
            hr_kat = hrubka_mm(zaznam[2])
            if hr_kat and abs(hr_kat - hr_cp) > 0.25 * hr_cp:
                continue      # rovnaké slová, iná hrúbka = iná položka
        pokrytie_cp = len(spolocne) / len(tok)        # koľko z ponuky vysvetlí
        pokrytie_kat = len(spolocne) / len(zaznam[7])  # a naopak
        skore = min(pokrytie_cp, pokrytie_kat)
        if skore > najskore or (skore == najskore and najlepsi
                                and zaznam[3] > najlepsi[3]):
            najlepsi, najskore, najpokr_kat = zaznam, skore, pokrytie_kat
    if najlepsi and najskore >= 0.6:
        return najlepsi, f"popis ({najskore:.0%})"
    if najlepsi and najpokr_kat >= 0.6:
        # katalógová položka je len časťou toho, čo je v riadku ponuky
        return None, "skladaná – rozpíš po vrstvách"
    return None, ""


# MJ, ktoré sa v ponukách objavujú (navyše k tým z kroku 3)
MJ_CP = set(v.MJ_ZNAME) | {"m²", "m³", "kpl", "kpl.", "komplet", "súbor",
                           "subor", "súb.", "sub.", "bm", "mb", "hod.",
                           "hodina", "l", "ms", "pár", "par", "bal"}


def mnozstvo_a_cena(cisla):
    """Z čísel v riadku vyber (množstvo, jednotková cena).

    Krok 4 hľadá trojicu v susedných bunkách, čo v KROS exporte neplatí:
    stĺpce sú „Množstvo | Montáž | Materiál | Cena celkom", takže pri
    nulovom materiáli susedná trojica nevyjde. Preto hľadáme ľubovoľnú
    dvojicu (jedn. cena, cena celkom), pre ktorú platí
    množstvo × jedn. cena ≈ cena celkom. To zároveň odfiltruje riadky,
    kde sa čísla len tak povaľujú (hmotnosti, sutina).
    """
    if not cisla:
        return 0, None
    mn = cisla[0]
    if mn <= 0:
        return mn, None
    for i in range(1, len(cisla)):
        jc = cisla[i]
        if jc <= 0:
            continue
        for k in range(1, len(cisla)):
            if k == i or cisla[k] <= 0:
                continue
            if abs(mn * jc - cisla[k]) <= max(0.02 * cisla[k], 0.05):
                return mn, jc
    return mn, None


def polozky_xlsx(data: bytes, subor: str):
    """Riadky, ktoré vyzerajú ako položka výkazu – s kódom aj bez neho.

    Kód nie je podmienka: vlastná ponuka firmy ho zvyčajne nemá, a aj
    v KROS exporte bývajú vlastné položky („Elektroinštalácia, súb").
    """
    import openpyxl
    polozky = []
    try:
        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True,
                                    data_only=True)
    except Exception:
        return polozky
    for ws in wb.worksheets:
        for row in ws.iter_rows(values_only=True):
            hodnoty = [c for c in row if c is not None]
            if len(hodnoty) < 3:
                continue
            mj = next((str(c).strip().lower() for c in hodnoty
                       if str(c).strip().lower() in MJ_CP), None)
            if not mj:
                continue
            kod = next((str(c).strip() for c in hodnoty
                        if v.RE_TSKP.match(str(c).strip())), "")
            popis = max((str(c) for c in hodnoty
                         if isinstance(c, str) and len(str(c).strip()) > 8
                         and not v.RE_TSKP.match(str(c).strip())),
                        key=len, default="")
            if not popis and not kod:
                continue
            cisla = [c for c in hodnoty if isinstance(c, (int, float))
                     and not isinstance(c, bool)]
            if len(cisla) < 2:
                continue
            mn, cena = mnozstvo_a_cena(cisla)
            kod, popis = p4.normalizuj_polozku(kod, popis.strip())
            polozky.append({"subor": subor, "harok": ws.title, "kod": kod,
                            "popis": popis[:120], "mj": mj,
                            "mnozstvo": mn, "jedn_cena": cena})
    wb.close()
    return polozky


def kandidati(polozka, podla_mj, kolko=3):
    """Položky z katalógu, z ktorých sa dá skladaný riadok ponuky zložiť.

    Pri „zateplenie + fólie + práca" jedna katalógová položka nestačí;
    toto vráti vrstvy, ktoré v riadku sedia, nech je z čoho poskladať
    vlastný prepočet.
    """
    mj = (polozka["mj"] or "").lower()
    tok = tokeny(polozka["popis"])
    if len(tok) < 2:
        return []
    hr_cp = hrubka_mm(polozka["popis"])
    skore = []
    for zaznam in podla_mj.get(mj, ()):
        spolocne = tok & zaznam[7]
        if len(spolocne) < 2 or zaznam[3] < 3:
            continue
        if hr_cp:
            hr_kat = hrubka_mm(zaznam[2])
            if hr_kat and abs(hr_kat - hr_cp) > 0.25 * hr_cp:
                continue
        skore.append((len(spolocne) / len(zaznam[7]), zaznam[3], zaznam))
    skore.sort(key=lambda t: (-t[0], -t[1]))
    return [z for _, _, z in skore[:kolko]]


def polozky_bez_kodov(data: bytes, subor: str):
    """Ponuky od firiem často TSKP kódy nemajú – riadok potom rozoznáme
    podľa popisu, MJ a dvojice čísel (množstvo, jedn. cena)."""
    import openpyxl
    polozky = []
    try:
        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True,
                                    data_only=True)
    except Exception:
        return polozky
    for ws in wb.worksheets:
        for row in ws.iter_rows(values_only=True):
            hodnoty = [c for c in row if c is not None]
            if len(hodnoty) < 3:
                continue
            mj = next((str(c).strip().lower() for c in hodnoty
                       if str(c).strip().lower() in MJ_CP), None)
            if not mj:
                continue
            popis = max((str(c) for c in hodnoty if isinstance(c, str)
                         and len(str(c)) > 8), key=len, default="")
            if not popis:
                continue
            cisla = [c for c in hodnoty if isinstance(c, (int, float))
                     and not isinstance(c, bool) and c > 0]
            if len(cisla) < 2:
                continue
            mn, cena = cisla[0], cisla[1]
            # keď je v riadku aj "spolu", over trojicu a radšej jej ver
            if len(cisla) >= 3 and abs(mn * cena - cisla[2]) > \
                    max(0.02 * cisla[2], 0.05):
                for i in range(len(cisla) - 2):
                    a, b, c3 = cisla[i], cisla[i + 1], cisla[i + 2]
                    if abs(a * b - c3) <= max(0.02 * c3, 0.05):
                        mn, cena = a, b
                        break
            polozky.append({"subor": subor, "harok": ws.title, "kod": "",
                            "popis": popis.strip()[:120], "mj": mj,
                            "mnozstvo": mn, "jedn_cena": cena})
    wb.close()
    return polozky


def polozky_zo_suboru(cesta: pathlib.Path):
    """Položky z xlsx/zip/PDF ponuky."""
    vysledok = []
    if cesta.suffix.lower() == ".pdf":
        najdene, ma_text = v.extrahuj_polozky_pdf(cesta)
        if not ma_text:
            print(f"!! {cesta.name} je zrejme sken – bez OCR sa z neho nič "
                  f"nevytiahne", file=sys.stderr)
        for p in najdene:
            kod, popis = p4.normalizuj_polozku(p.get("kod", ""),
                                               p.get("popis", ""))
            mn, cena = p4.mnozstvo_a_cena(p.get("cisla", []), "pdf")
            vysledok.append({"subor": cesta.name, "harok": "pdf",
                             "kod": kod, "popis": popis,
                             "mj": p.get("mj", ""), "mnozstvo": mn,
                             "jedn_cena": cena})
        return vysledok
    for meno, data in v.najdi_xlsx(cesta) or []:
        vysledok += polozky_xlsx(data, meno)
    return vysledok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ponuky", nargs="+",
                    help="xlsx, zip alebo textové PDF s cenovou ponukou")
    ap.add_argument("--db", default="ceny_spolu.db")
    ap.add_argument("--csv", help="kam zapísať celú tabuľku")
    ap.add_argument("--min-dopad", type=float, default=0.0,
                    help="vypíš len položky s dopadom nad X € (abs.)")
    ap.add_argument("--min-n", type=int, default=2,
                    help="porovnávaj len s položkami, ktoré majú aspoň n cien "
                         "(default 2; pri n < 3 je medián len orientačný)")
    args = ap.parse_args()

    if not pathlib.Path(args.db).exists():
        raise SystemExit(f"databáza {args.db} neexistuje")
    podla_kodu, podla_mj = nacitaj_katalog(args.db)

    vsetky = []
    for p in args.ponuky:
        cesta = pathlib.Path(p)
        if not cesta.exists():
            print(f"!! {p} neexistuje", file=sys.stderr)
            continue
        najdene = polozky_zo_suboru(cesta)
        print(f"{cesta.name}: {len(najdene)} položiek", file=sys.stderr)
        vsetky += najdene

    if not vsetky:
        raise SystemExit("v ponuke sa nenašli položky (je to výkaz s kódmi, "
                         "MJ, množstvami a cenami? sken bez OCR nestačí)")

    vysledky, suma_cp, bez_zhody = [], 0.0, 0
    for p in vsetky:
        cena = p["jedn_cena"]
        if cena:
            suma_cp += cena * (p["mnozstvo"] or 0)
        zaznam, ako = najdi(p, podla_kodu, podla_mj)
        if not zaznam or zaznam[3] < args.min_n or not cena:
            bez_zhody += 1
            if zaznam and zaznam[3] < args.min_n:
                ako = f"málo dát (n={zaznam[3]})"
            vysledky.append({**p, "zhoda": ako or "—", "kat_kod": "",
                             "kat_popis": "", "n": "", "median": "",
                             "p25": "", "p75": "", "odchylka": "",
                             "dopad": 0.0,
                             "kandidati": kandidati(p, podla_mj) if cena else []})
            continue
        med = zaznam[4] or 0
        dopad = (cena - med) * (p["mnozstvo"] or 0)
        vysledky.append({**p, "zhoda": ako, "kat_kod": zaznam[0],
                         "kat_popis": zaznam[2], "n": zaznam[3],
                         "median": round(med, 2), "p25": round(zaznam[5], 2),
                         "p75": round(zaznam[6], 2),
                         "odchylka": round((cena / med - 1) * 100, 1) if med else "",
                         "dopad": dopad, "kandidati": []})

    vysledky.sort(key=lambda r: -abs(r["dopad"]))
    nad = sum(r["dopad"] for r in vysledky if r["dopad"] > 0)
    pod = sum(r["dopad"] for r in vysledky if r["dopad"] < 0)

    print()
    print(f"{'položka':<46}{'MJ':<5}{'množ.':>10}{'cena CP':>10}"
          f"{'medián':>10}{'p25-p75':>21}{'odch.':>8}{'dopad €':>11}  zhoda")
    print("-" * 140)
    for r in vysledky:
        if abs(r["dopad"]) < args.min_dopad:
            continue
        popis = (r["popis"] or r["kat_popis"])[:44]
        odch = f"{r['odchylka']:+.0f}%" if r["odchylka"] != "" else "—"
        med = f"{r['median']:.2f}" if r["median"] != "" else "—"
        rozp = (f"{r['p25']:.2f}-{r['p75']:.2f} (n={r['n']})"
                if r["median"] != "" else "—")
        print(f"{popis:<46}{(r['mj'] or ''):<5}{(r['mnozstvo'] or 0):>10.2f}"
              f"{(r['jedn_cena'] or 0):>10.2f}{med:>10}{rozp:>21}{odch:>8}"
              f"{r['dopad']:>11.0f}  {r['zhoda']}")
        for z in r.get("kandidati", ()):
            print(f"{'':>4}→ z čoho zložiť: {z[0]:<11}{z[1]:<4}"
                  f"medián {z[4]:>8.2f} (n={z[3]})  {z[2][:58]}")

    print("-" * 140)
    def eur(x, znak=""):
        return format(x, f"{znak},.0f").replace(",", " ") + " €"

    print(f"položiek v ponuke: {len(vysledky)}, z toho bez porovnania: {bez_zhody}")
    print(f"suma ponuky (bez DPH, z čitateľných položiek): {eur(suma_cp)}")
    print(f"nad mediánom trhu:  {eur(nad, '+')}")
    print(f"pod mediánom trhu:  {eur(pod)}")
    print(f"čistý rozdiel:      {eur(nad + pod, '+')}")
    print("\nPozn.: medián je z verejných súťaží, bez DPH. Pri n < 3 ber cenu "
          "len ako orientačnú.\nRozdiel over v položke – iný výrobok, malé "
          "množstvo či horší prístup ho vysvetlia.")

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8-sig") as f:
            polia = [k for k in vysledky[0] if k != "kandidati"]
            w = csv.DictWriter(f, fieldnames=polia, delimiter=";",
                               extrasaction="ignore")
            w.writeheader()
            w.writerows(vysledky)
        print(f"\ntabuľka -> {args.csv}")


if __name__ == "__main__":
    main()
