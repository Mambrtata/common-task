# Výsledky pilotu – august 2026

Vzorka: **94 zákaziek** (rovnomerne z 1 355 zákaziek, CPV: školy, vzdelávanie,
kancelárie, zdravotníctvo, viacúčelové, šport/kultúra; register týchto 6 kódov
má celkovo ~8 900 zákaziek). Stiahnuté ponuky: 1,5 GB, 429 súborov.
Beh 12. 8. 2026, skripty v tomto priečinku.

## Kľúčové čísla

- **62 %** zákaziek zo vzorky malo v profile stiahnuteľné ponuky (58/94);
  zvyšok sú prevažne bežiace súťaže, kde sa ponuky ešte nezverejnili.
- **36 %** zákaziek s ponukami malo aspoň jeden strojovo čitateľný výkaz
  výmer (21/58) – bez OCR, len xlsx + textové PDF.
- **9 755 položiek** extrahovaných (TSKP kód, popis, MJ, množstvo, jedn. cena).
- Formáty: 93 % súborov je PDF; **43 % PDF má textovú vrstvu** (export
  z KROS-u, extrahovateľné), zvyšok skeny → kandidáti na OCR.
- Overený viacnásobný cenový bod: rovnaká TSKP položka ocenená rôznymi
  uchádzačmi rôzne (napr. 131211101 hĺbenie jám: 69,29 vs 66,15 €/m³).

## Interpretácia

- Výťažnosť 36 % je pod pôvodným odhadom 50–70 %, ale OCR skenov a lepšie
  parsovanie PDF tabuliek ju zdvihnú – textová vrstva chýba len časti PDF.
- Ponuky sa zverejňujú po uzavretí zmluvy, takže najlepší zdroj sú zákazky
  staré 6+ mesiacov; čerstvé súťaže treba preskočiť (filter na dátum).
- Extrakčná kvalita na xlsx aj textových PDF je vysoká a kódy sedia s TSKP,
  takže párovanie na CENKROS položky bude priame.

---

# Pilot – výťažnosť extrakcie výkazov výmer

- zákaziek so stiahnutými súbormi: **58**
- zákaziek s aspoň 1 čitateľným výkazom výmer: **21** (36 %)
- súborov spolu: 429
- PDF s textovou vrstvou: 171 (zvyšok PDF sú skeny -> OCR)
- položiek extrahovaných spolu (xlsx + textové PDF): 9755

## Prípony súborov
- .pdf: 401
- .zip: 14
- .xlsx: 7
- .xls: 3
- .7z: 2
- .png: 1
- .rar: 1

## Po zákazkách

| zákazka | súborov | xlsx | pdf text | pdf sken | výkazov | položiek |
|---|---|---|---|---|---|---|
| 140803 | 2 | 0 | 2 | 0 | 0 | 0 |
| 147440 | 10 | 0 | 10 | 0 | 2 | 48 |
| 150918 | 6 | 1 | 2 | 2 | 2 | 593 |
| 151892 | 5 | 0 | 0 | 5 | 0 | 0 |
| 159375 | 2 | 0 | 0 | 2 | 0 | 0 |
| 159422 | 2 | 0 | 2 | 0 | 0 | 0 |
| 400119 | 11 | 0 | 0 | 11 | 0 | 0 |
| 407896 | 4 | 0 | 3 | 1 | 0 | 0 |
| 409955 | 9 | 0 | 0 | 9 | 0 | 0 |
| 410284 | 3 | 0 | 0 | 3 | 0 | 0 |
| 417223 | 4 | 0 | 0 | 4 | 0 | 0 |
| 419242 | 70 | 0 | 37 | 33 | 2 | 385 |
| 420631 | 1 | 0 | 0 | 1 | 0 | 0 |
| 424371 | 5 | 0 | 0 | 4 | 0 | 0 |
| 426518 | 0 | 0 | 0 | 0 | 0 | 0 |
| 431750 | 3 | 0 | 2 | 1 | 0 | 0 |
| 432795 | 3 | 0 | 0 | 3 | 0 | 0 |
| 434729 | 6 | 0 | 5 | 1 | 3 | 137 |
| 434921 | 27 | 0 | 4 | 20 | 0 | 0 |
| 435047 | 2 | 0 | 0 | 2 | 0 | 0 |
| 435215 | 41 | 0 | 30 | 11 | 3 | 294 |
| 435989 | 4 | 0 | 4 | 0 | 3 | 1045 |
| 450815 | 1 | 0 | 1 | 0 | 1 | 57 |
| 470908 | 1 | 0 | 0 | 1 | 0 | 0 |
| 473924 | 37 | 0 | 10 | 27 | 0 | 0 |
| 478771 | 1 | 0 | 0 | 1 | 0 | 0 |
| 488889 | 13 | 1 | 1 | 11 | 1 | 660 |
| 493044 | 1 | 0 | 0 | 1 | 0 | 0 |
| 496157 | 41 | 1 | 6 | 34 | 0 | 0 |
| 501262 | 1 | 0 | 0 | 1 | 0 | 0 |
| 501550 | 1 | 0 | 1 | 0 | 1 | 196 |
| 504856 | 1 | 0 | 0 | 1 | 0 | 0 |
| 505062 | 1 | 0 | 0 | 1 | 0 | 0 |
| 505754 | 1 | 0 | 0 | 0 | 0 | 0 |
| 507139 | 6 | 0 | 6 | 0 | 1 | 344 |
| 510485 | 16 | 0 | 12 | 4 | 3 | 441 |
| 512511 | 20 | 0 | 6 | 14 | 0 | 0 |
| 513475 | 11 | 0 | 10 | 1 | 0 | 0 |
| 515584 | 2 | 0 | 1 | 1 | 0 | 0 |
| 516044 | 2 | 0 | 0 | 2 | 0 | 0 |
| 518916 | 1 | 0 | 0 | 1 | 0 | 0 |
| 523235 | 1 | 1 | 0 | 0 | 1 | 38 |
| 526023 | 1 | 0 | 0 | 0 | 0 | 0 |
| 532179 | 2 | 0 | 1 | 0 | 1 | 311 |
| 532500 | 2 | 1 | 0 | 0 | 1 | 698 |
| 533612 | 1 | 0 | 1 | 0 | 0 | 0 |
| 535522 | 10 | 5 | 0 | 5 | 1 | 517 |
| 535560 | 1 | 0 | 1 | 0 | 1 | 23 |
| 540214 | 2 | 0 | 0 | 0 | 0 | 0 |
| 542887 | 6 | 0 | 4 | 2 | 2 | 2022 |
| 543256 | 1 | 0 | 0 | 1 | 0 | 0 |
| 544291 | 5 | 8 | 0 | 0 | 2 | 1351 |
| 545214 | 1 | 0 | 0 | 1 | 0 | 0 |
| 547451 | 1 | 0 | 1 | 0 | 1 | 105 |
| 549299 | 1 | 0 | 1 | 0 | 1 | 169 |
| 552837 | 1 | 3 | 0 | 0 | 3 | 321 |
| 556578 | 1 | 0 | 0 | 0 | 0 | 0 |
| 557588 | 14 | 0 | 7 | 7 | 0 | 0 |
---

# Dodatok: široký zber (2. beh, 12. 8. 2026 večer)

Vzorka rozšírená na **200 zákaziek z 3 048** (19 CPV kódov – celé pozemné
stavby vrátane bytoviek, polyfunkcie, komercie). Zber so zrýchleným filtrom
(typ dokumentu z výsledkov vyhľadávania, len rozpočtovo relevantné súbory,
PDF > 20 MB preskočené ako skeny). Na disku 2,1 GB / 598 súborov.

## Finálne čísla (kumulatívne, obe vzorky)

- zákaziek s aspoň 1 čitateľným výkazom výmer: **41 zo 135** so súbormi (30 %)
- extrahovaných položiek: **28 591**, z toho **25 278 s jednotkovou cenou**
- katalóg `cennik_tskp`: **7 676 položiek**, z toho 2 598 s n ≥ 3
  a 1 596 s n ≥ 5
- PDF s textovou vrstvou: 229 zo 498 (46 %)
- segmenty s dátami: školy (ZŠ/SŠ/MŠ), kancelárske budovy, zdravotníctvo,
  nemocnice, polyfunkčné budovy
- vo výkazoch potvrdený výskyt **figúr** (rozpisov výmer) vrátane popisov
  a odpočtov otvorov – plán: tabuľka `figury` v ďalšej verzii DB

Snapshot databázy: `ceny-pilot-2026-08.db` (v tomto priečinku).
