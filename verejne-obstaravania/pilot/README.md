# Pilot: výťažnosť rozpočtov z verejných obstarávaní

Overuje, aké percento zákaziek na pozemné stavby má v profile na ÚVO
strojovo čitateľné ocenené výkazy výmer (ponuky uchádzačov v Exceli).

Kontext a zdôvodnenie: viď `../01-zdroje-rozpoctov.md`.

## Ako to funguje

Overené endpointy (august 2026, bez API kľúča):

- zoznam zákaziek: `uvo.gov.sk/vyhladavanie/vyhladavanie-zakaziek?cpv=<kód>&druhZakazky=PRACE&pageNo=<n>` (GET)
- dokumenty k zákazke: `uvo.gov.sk/vyhladavanie/vyhladavanie-dokumentov?nazovZakazky=<názov>` (GET)
- detail dokumentu (typ, dodávateľ, súbory): `.../vyhladavanie-dokumentov/detail/<id>`
- download súboru: link `.../vyhladavanie-dokumentov/download/<docId>/<fileId>?cHash=...`
  priamo z detailu (GET, funguje aj bez prihlásenia)

Poznámka: JSON grid API na evo.isepvo.sk (`DocumentSearch/GetAllData`) vracia 405
mimo prehliadača – preto ideme cez HTML vyhľadávanie na uvo.gov.sk, ktoré je
plne funkčné cez GET parametre.

## Spustenie

```bash
pip install openpyxl pypdfium2   # len pre krok 3

python3 01_zakazky.py --max-stran 3        # -> data/zakazky.csv
python3 02_dokumenty.py --limit-zakaziek 20  # -> data/subory/, data/dokumenty.csv
python3 03_vyhodnotenie.py                 # -> data/report.md
```

Skripty robia pauzu ~0,8 s medzi requestami a majú retry s backoffom.
Priečinok `data/` sa neverzuje (viď `.gitignore`).

## Čo hovorí výsledok

`data/report.md` ukáže:

- % zákaziek s aspoň jedným čitateľným výkazom výmer (kľúčové číslo pilotu –
  odhadovali sme 50–70 %),
- rozloženie prípon súborov (xlsx vs. pdf vs. zip),
- počet extrahovaných položiek + ukážku v `data/ukazka_poloziek.csv`
  (vizuálna kontrola, či heuristika TSKP kód + MJ + čísla chytá správne riadky).

## Prvé pozorovania z testovacieho behu (12. 8. 2026)

- Reťaz funguje end-to-end: 111 zákaziek zo 6 CPV kódov za ~10 s, ponuky
  sa našli a stiahli, extrakčná heuristika vytiahla **711 položiek s TSKP
  kódmi** z reálneho výkazu výmer (xlsx, formát KROS so `.S` príponami kódov).
- Zoznam zákaziek je triedený podľa poslednej aktualizácie – čerstvé záznamy
  sú väčšinou **bežiace súťaže bez zverejnených ponúk** (tie sa zverejňujú až
  po uzavretí zmluvy). Na meranie výťažnosti treba ísť hlbšie do stránok
  (`--max-stran 10+`) alebo filtrovať staršie dátumy.
- V malej vzorke boli ponuky **prevažne PDF** (vrátane „Cenová ponuka" =
  ocenený rozpočet ako PDF). Extrakcia tabuliek z PDF bude dôležitejšia,
  než sme čakali – do plnej verzie treba pdfplumber/camelot + OCR fallback.
- Neocenené zadania (výkazy výmer) bývajú aj pod typom **„Iný dokument
  k zákazke"** ako xlsx – oplatí sa sťahovať aj tento typ, nie len ponuky
  a súťažné podklady.

## Ďalší krok po pilote

Ak výťažnosť vyjde rozumne: rozšíriť 03 na plnú extrakciu (kód, popis, MJ,
množstvo, jednotková cena → SQLite `ceny.db`) a doplniť zdroj CRZ (nočné dávky).
