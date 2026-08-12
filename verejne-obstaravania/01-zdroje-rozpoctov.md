# Rozpočty z verejných obstarávaní ako zdroj cien stavebných konštrukcií

Cieľ: interná databáza jednotkových cien stavebných konštrukcií a prác, postavená na
reálnych ocenených rozpočtoch (výkazoch výmer) z verejných zákaziek na Slovensku.

**Účel je interný projekčný** – orientačné ceny v skorých fázach projektu (štúdia,
DUR, DSP) a realitná kontrola smerných cien. Finálne rozpočty sa aj tak robia
v CENKROS-e, takže databáza nenahrádza cenník, len ho dopĺňa o reálne trhové ceny
z ponúk. To je výhoda aj technicky: CENKROS pracuje s TSKP triednikom, rovnako ako
výkazy výmer z obstarávaní, takže sa dáta mapujú 1:1 na položky, s ktorými sa
pracuje pri finálnom rozpočte.

**Krátka odpoveď: áno, dá sa.** Od 31. 3. 2022 (novela č. 395/2021 Z. z. zákona
č. 343/2015 Z. z. o verejnom obstarávaní) sa v profile obstarávateľa povinne zverejňujú
**ponuky všetkých uchádzačov** – pri stavebných zákazkách teda ocenené výkazy výmer,
typicky v Exceli. K tomu Centrálny register zmlúv obsahuje zmluvy o dielo aj s oceneným
rozpočtom v prílohe. Oba zdroje sú verejné a dajú sa sťahovať hromadne.

## Zdroje dát (od najhodnotnejšieho)

### 1. Profil obstarávateľa na ÚVO / IS EPVO – ponuky uchádzačov

- Podľa **§ 64 zákona č. 343/2015 Z. z.** obstarávateľ v profile zverejňuje po uzavretí
  zmluvy o. i. **ponuky všetkých uchádzačov doručené v lehote na predkladanie ponúk**,
  zápisnice z otvárania a vyhodnotenia ponúk a súťažné podklady.
- Pre databázu cien je to najcennejší zdroj: **jedna zákazka = viac cenových bodov**
  (víťaz + neúspešní uchádzači) na identických položkách výkazu výmer.
- Dokumenty sa hľadajú cez vyhľadávanie dokumentov na [uvo.gov.sk](https://www.uvo.gov.sk)
  a v systéme IS EPVO (evo.isepvo.sk), kde sú prílohy priamo na stiahnutie.
- Ocenené výkazy výmer bývajú exporty z rozpočtárskych programov (CENKROS/ODIS),
  t. j. Excel so štruktúrou **TSKP** (triednik stavebných konštrukcií a prác) –
  kód položky, popis, MJ, množstvo, jednotková cena, spolu. To sa parsuje dobre.

### 2. Centrálny register zmlúv (crz.gov.sk)

- Povinne zverejňované zmluvy štátu a samospráv; **zmluvy o dielo na stavby majú
  ocenený rozpočet / výkaz výmer bežne ako prílohu** (viď napr.
  [vzorová zmluva o dielo v CRZ](https://www.crz.gov.sk/data/att/3799026_dokument1.pdf)).
- Hromadný prístup: CRZ generuje **nočné zmenové dávky (ZIP s XML metadátami
  vrátane liniek na prílohy)** – odporúčaný spôsob namiesto crawlovania stránok.
  Viď [Sťahovanie údajov z CRZ](https://www.crz.gov.sk/stahovanie-udajov-z-crz/)
  a dataset na [data.gov.sk](https://data.gov.sk/sk/dataset/crz).
- Nevýhoda: prílohy sú často PDF (aj skenované) → treba OCR/extrakciu tabuliek;
  Excel prílohy sú zriedkavejšie než v profile na ÚVO.
- Výhoda: zachytáva aj **dodatky** (zmeny cien počas výstavby) – dôležité pre
  reálnu koncovú cenu.

### 3. Súťažné podklady – neocenené výkazy výmer

- Zverejňujú sa v profile ešte pred predložením ponúk. Bez cien, ale dávajú
  **štruktúru položiek a výmery** – hodí sa ako kostra databázy a na kontrolu
  úplnosti ocenených verzií.

### 4. Vestník ÚVO / oznámenia o výsledku

- Len **celkové zmluvné ceny** a identifikácia víťaza, nie položkové ceny.
  Užitočné ako index: podľa oznámení o výsledku (CPV kódy 45xxxxxx = stavebné práce)
  sa dá zostaviť zoznam zákaziek, ku ktorým potom stiahnuť ponuky z profilu.

### 5. Agregátory a API tretích strán

- **uvostat.sk** – agregované dáta z vestníka ÚVO, má [dokumentované API](https://github.com/MiroBabic/uvostat_api).
- **transparex.sk**, platformy Josephine, eZakazky – ďalšie miesta, kde vedia byť
  súťažné dokumenty.
- EÚ úroveň: **TED** – len údaje z oznámení, nie rozpočty.

## Navrhovaný postup (pipeline)

1. **Index zákaziek**: z vestníka ÚVO (príp. cez uvostat API) vyfiltrovať zákazky
   s CPV 45* (stavebné práce), uložiť ID zákazky, obstarávateľa, predpokladanú
   hodnotu, dátum, región.
2. **Stiahnutie dokumentov**: k zákazke stiahnuť z profilu prílohy – ponuky
   uchádzačov a súťažné podklady; paralelne z CRZ nočných dávok páry
   zmluva o dielo + rozpočet.
3. **Extrakcia položiek**: parsovať Excel výkazy výmer (TSKP kód, popis, MJ,
   množstvo, jednotková cena); PDF cez extrakciu tabuliek/OCR.
4. **Normalizácia**: kľúčovať položky podľa TSKP kódu + MJ; ukladať s metadátami
   (dátum ponuky, región, typ stavby, veľkosť zákazky, víťaz vs. neúspešná ponuka).
5. **Databáza cien**: pre každý TSKP kód štatistika jednotkových cien (medián,
   rozptyl, časový vývoj). Keďže finálny rozpočet ide z CENKROS-u, praktický
   výstup je aj **koeficient reálna cena / smerná cena** po TSKP kódoch alebo
   aspoň po dieloch (HSV/PSV skupiny) – ten sa dá priamo použiť na korekciu
   odhadu v projekčnej fáze.

## Na čo si dať pozor

- **Taktické oceňovanie**: uchádzači niektoré položky podhodnocujú a iné
  nadhodnocujú (presúvanie marže). Medián cez viac ponúk a viac zákaziek to tlmí –
  preto sú ponuky všetkých uchádzačov cennejšie než len víťazná cena.
- **Časová hodnota**: ceny stavebných materiálov kolíšu; každý cenový bod musí
  niesť dátum a pri agregácii treba indexovať (napr. na štvrťroky).
- **Autorské práva na popisy položiek**: samotné ceny a kódy sú fakty, ale
  **plné texty popisov položiek z komerčných cenníkových databáz (CENEKON/KROS)
  môžu byť licencované** – pre internú databázu je bezpečnejšie držať TSKP kód +
  vlastný/skrátený popis. Pri čisto internom projekčnom použití (finálny rozpočet
  ide z licencovaného CENKROS-u) je riziko malé, ale ceny nezverejňovať navonok
  s prevzatými popismi.
- **Kvalita vstupov**: časť príloh sú skenované PDF; rátať s tým, že nie všetko
  sa zautomatizuje – merať úspešnosť extrakcie.
- **Staršie zákazky**: povinnosť zverejňovať ponuky platí od 31. 3. 2022;
  pri starších zákazkách je k dispozícii spravidla len zmluva s rozpočtom v CRZ.
- **Podlimitné/malé zákazky**: menej dokumentácie v profile; hlavný zdroj je CRZ.

## Otvorené otázky

- Overiť, či IS EPVO má použiteľné API na hromadné sťahovanie príloh, alebo či
  treba crawler cez verejné vyhľadávanie dokumentov.
- Slovensko sa zapája do európskeho **Public Procurement Data Space (PPDS)** –
  sledovať, či to prinesie lepší strojový prístup k dokumentom
  ([aktualita ÚVO](https://www.uvo.gov.sk/aktualne-temy/aktualita/slovensko-ziska-novy-pristup-k-informaciam-o-verejnom-obstaravani-2025)).
- Rozsah pilotu: navrhujem začať jedným segmentom (napr. pozemné stavby škôl/úradov
  za posledné 2 roky) a na ňom overiť výťažnosť extrakcie.
