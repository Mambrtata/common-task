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

## Rozsah: pozemné stavby, časť ASR

Primárny záber je **architektonicko-stavebné riešenie (ASR) pozemných stavieb** –
teda stavebná časť budov, bez profesií (ZTI, ÚK, ELI, VZT...).

**Filter zákaziek (CPV):** pozemné stavby = `45210000-2` (stavebné práce na stavbe
budov) a podkódy – napr. `45214xxx` školy, `45215xxx` zdravotníctvo a sociálne
stavby, `45211xxx` bytové budovy, `45213xxx` komerčné/administratívne budovy.
Rekonštrukcie budov bývajú aj pod všeobecným `45000000-7` + upresnenie v názve.

**Filter položiek (TSKP diely) – čo patrí do ASR:**

- **HSV celé**: 1 zemné práce, 2 zakladanie, 3 zvislé a kompletné konštrukcie,
  4 vodorovné konštrukcie, 5 komunikácie (ak sú súčasťou objektu), 6 úpravy
  povrchov/podlahy/výplne otvorov, 9 ostatné konštrukcie a búranie, presuny hmôt.
- **PSV – remeslá ASR**: 711–717 izolácie (hydro, tepelné, akustické),
  762 tesárske, 763 suchá výstavba (SDK), 764 klampiarske, 765 krytiny tvrdé,
  766 stolárske, 767 zámočnícke, 771–776 podlahy a dlažby, 781–784 obklady
  a maľby, 783 nátery, 787 zasklievanie.
- **Vylúčiť (profesie)**: 721–727 zdravotechnika, 731–735 ústredné kúrenie,
  plynoinštalácie, montážne diely M21 elektromontáže, M24 VZT, M33/M36 a pod.

Praktická pomôcka: vo výkazoch výmer pozemných stavieb bývajú časti aj tak
členené samostatne („ASR", „ZTI", „ÚK", „ELI"...) po hárkoch Excelu alebo po
samostatných súboroch – prvé kolo filtra teda vie ísť podľa názvov hárkov/súborov,
druhé kolo podľa TSKP dielov.

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
   s CPV 4521* (pozemné stavby, viď Rozsah vyššie), uložiť ID zákazky,
   obstarávateľa, predpokladanú hodnotu, dátum, región, typ budovy.
2. **Stiahnutie dokumentov**: k zákazke stiahnuť z profilu prílohy – ponuky
   uchádzačov a súťažné podklady; paralelne z CRZ nočných dávok páry
   zmluva o dielo + rozpočet.
3. **Extrakcia položiek**: parsovať Excel výkazy výmer (TSKP kód, popis, MJ,
   množstvo, jednotková cena); PDF cez extrakciu tabuliek/OCR. Ponechať len
   časti ASR (podľa názvov hárkov/súborov a TSKP dielov, viď Rozsah).
4. **Normalizácia**: kľúčovať položky podľa TSKP kódu + MJ; ukladať s metadátami
   (dátum ponuky, región, typ stavby, veľkosť zákazky, víťaz vs. neúspešná ponuka).
5. **Databáza cien**: pre každý TSKP kód štatistika jednotkových cien (medián,
   rozptyl, časový vývoj). Keďže finálny rozpočet ide z CENKROS-u, praktický
   výstup je aj **koeficient reálna cena / smerná cena** po TSKP kódoch alebo
   aspoň po dieloch (HSV/PSV skupiny) – ten sa dá priamo použiť na korekciu
   odhadu v projekčnej fáze.

## Očakávaný výstup

Tri vrstvy, od surových dát po použiteľný nástroj pre projektanta:

1. **Surová tabuľka cenových bodov** – jeden riadok = jedna položka z jednej ponuky:

   | pole | príklad |
   |---|---|
   | zákazka (ID, názov, obstarávateľ) | „Rekonštrukcia ZŠ..." |
   | dátum ponuky, región, typ budovy (CPV) | 2024-05, BB, škola |
   | uchádzač + príznak víťaz/neúspešný | víťaz |
   | TSKP kód, popis, MJ | 311238xxx, murivo z tehál..., m3 |
   | množstvo, jednotková cena, cena spolu | 120 m3, 98,50 €, 11 820 € |

2. **Agregovaný cenník ASR** – pre každý TSKP kód + MJ: počet pozorovaní, medián,
   kvartilové rozpätie (p25–p75), vývoj v čase (po štvrťrokoch) a – kde máme
   smernú cenu – **koeficient reál/CENKROS**.

3. **Koeficienty po dieloch** (HSV 1, 2, 3... / PSV 711, 763, 771...) – fallback
   pre položky s málo pozorovaniami a rýchla korekcia odhadu v skorej fáze.

Technicky: SQLite/Parquet ako zdroj pravdy + Excel export cenníka pre projektantov.

## Očakávaný objem dát (odhady, overí pilot)

- **Zákazky**: pozemné stavby (CPV 4521*) vo vestníku rádovo **stovky až ~1 500
  výsledkov ročne** (nadlimit + podlimit). Pilot školy + administratíva za 2 roky:
  odhadom **300–600 zákaziek**.
- **Výťažnosť**: ponuky v profile sú povinné od 31. 3. 2022; použiteľný Excel
  výkaz výmer čakám pri **50–70 %** zákaziek (zvyšok PDF/skeny/chýbajúce).
- **Ponúk na zákazku**: v stavebníctve typicky **2–5**, priemer ~3.
- **ASR položiek na rozpočet**: malé rekonštrukcie 100–300, novostavby 500–1500;
  priemer ~300–500.
- **Súčet za pilot**: ~400 zákaziek × 3 ponuky × 400 položiek ≈ **rádovo
  200–500 tisíc cenových bodov**. Pri plnom zábere (všetky pozemné stavby od
  2022 doteraz + rozpočty zo zmlúv v CRZ) rádovo **jednotky miliónov**.
- **Pokrytie položiek**: koncentruje sa – **top ~1 000–2 000 bežných ASR položiek**
  (murivá, betóny, omietky, SDK, izolácie, podlahy, zateplenie...) bude mať
  desiatky až stovky pozorovaní → robustné mediány. Dlhý chvost špeciálnych
  položiek ostane riedky → tam nastupujú koeficienty po dieloch.

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
- Rozsah pilotu: navrhujem začať jedným podsegmentom pozemných stavieb (napr.
  školy/úrady, CPV 45214xxx + 45213xxx, za posledné 2 roky) a na ňom overiť
  výťažnosť extrakcie ASR položiek.
