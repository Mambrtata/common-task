# Databáza cien projektových a inžinierskych služieb (pd.db)

## Čo to je

Ceny **projektových dokumentácií a inžinierskej činnosti** vysúťažené vo
verejných obstarávaniach na Slovensku (CPV 71xx), vyťažené zo správ
o zákazke a zápisníc zverejnených v profiloch obstarávateľov na
uvo.gov.sk (§ 64 zákona 343/2015). Ceny sú **bez DPH**.

Slúži na **nastavenie vlastnej cenovej ponuky**: aká je cenová hladina
pri danej veľkosti zákazky a ako hlboko pod predpokladanú hodnotu
zákazky (PHZ) chodia víťazi.

## Tabuľky

| tabuľka | obsah |
|---|---|
| `pd_zakazky(zakazka_id, nazov, obstaravatel, cpv, kraj, datum, rok, phz, konecna, pomer, pocet_ponuk, zdroj_url)` | jedna zákazka na riadok; `pomer` = konečná / PHZ |
| `pd_ceny(zakazka_id, ..., druh_ceny, cena, dph, uchadzac, zdroj_dokument, zdroj_url)` | surové záznamy: `phz`, `konecna`, `ponuka` |
| `pd_fts(zakazka_id, nazov, obstaravatel)` | fulltext, diakritika nevadí |
| `pd_statistika(pasmo, ukazovatel, n, median, p25, p75)` | predpočítané mediány a kvartily po veľkostných pásmach |

## Typické dotazy

```sql
-- porovnateľné zákazky podľa veľkosti (toto je hlavný dotaz)
SELECT round(phz) phz, round(konecna) konecna, pomer, pocet_ponuk,
       kraj, datum, nazov, zdroj_url
FROM pd_zakazky
WHERE phz BETWEEN 80000 AND 200000 AND pomer IS NOT NULL
ORDER BY pomer;

-- hľadanie podobného predmetu (fulltext, bez diakritiky)
SELECT z.* FROM pd_zakazky z JOIN pd_fts f ON z.zakazka_id = f.zakazka_id
WHERE pd_fts MATCH 'rekonstrukcia skol*';

-- predpočítaná štatistika
SELECT * FROM pd_statistika WHERE ukazovatel = 'pomer_konecna_phz';

-- jednotlivé ponuky konkrétnej zákazky (rozptyl medzi uchádzačmi)
SELECT druh_ceny, cena, dph, uchadzac FROM pd_ceny
WHERE zakazka_id = '522881' ORDER BY cena;

-- vývoj v čase
SELECT rok, count(*) n, round(avg(pomer),2) FROM pd_zakazky
WHERE pomer IS NOT NULL AND rok <> '' GROUP BY rok ORDER BY rok;
```

## Ako čítať výsledky

- **`pomer` je kľúčové číslo.** Medián okolo 0,94 znamená, že víťaz
  ide typicky ~6 % pod PHZ. p25 ≈ 0,81 = štvrtina víťazov ide 19 % a viac
  pod; p75 = 1,00 = štvrtina vyhrá presne na PHZ.
- **PHZ je strop, nie cieľ.** Trafiť sa naň presne vychádza len tam, kde
  je slabá konkurencia. Bezpečné pásmo býva 5–15 % pod PHZ.
- **Pozor na mimoriadne nízku ponuku (§ 53 ods. 4 zákona 343/2015).**
  Obstarávatelia ju reálne uplatňujú a uchádzača vylúčia, ak ju
  nevysvetlí – hlboký podliez teda nesie riziko.
- **Počet ponúk** hovorí o konkurencii: pri 1–2 ponukách sa víťazí blízko
  PHZ, pri 5+ sa tlačí nadol.
- Pri každej zákazke je `zdroj_url` – otvorením profilu na ÚVO zistíš
  presný rozsah (stupeň PD, inžinierska činnosť, autorský dozor).

## Obmedzenia

- Nie každá zákazka má zverejnené obe čísla; pomer je dostupný pri
  menšine zákaziek (ostatné majú len PHZ alebo len konečnú cenu).
- Rozsah plnenia sa medzi zákazkami líši (samotná PD vs. PD + IČ + AD),
  preto porovnávaj podobné predmety, nie len sumy.
- Zdroj sú textové PDF; skenované dokumenty sa nespracovali.
- Ceny sú bez DPH; pri neplatcoch DPH je konečná cena zároveň zmluvná.

## Obnova dát

```bash
pip install pypdfium2
python 10_pd_sluzby.py --zoznam      # zoznam zákaziek podľa cpv_sluzby.txt
python run_local_pd.py               # stiahne a vyťaží ceny
python 13_pd_db.py                   # postaví pd.db
python 11_pd_prehlad.py --csv pd_prehlad.csv   # súhrn na obrazovku
```
