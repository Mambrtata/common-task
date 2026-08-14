# Cenová databáza stavebných prác (pilot)

## Čo to je

Databáza **reálnych cien stavebných prác** vyťažená z verejne zverejnených
dokumentov: ponúk uchádzačov z profilov obstarávateľov na ÚVO
(uvo.gov.sk, § 64 zákona 343/2015) a zmlúv z Centrálneho registra zmlúv
(crz.gov.sk). Nie sú to smerné ceny z cenníka – sú to ceny, za ktoré sa
práce **naozaj vysúťažili**.

Zber pokrýva **pozemné stavby** (19 CPV kódov: školy, škôlky, zdravotníctvo,
sociálne služby, šport a kultúra, bytové domy, polyfunkcia, kancelárie,
obchodné budovy, sklady, prestavby). Ceny sú **bez DPH**.

## Na čo to je

Interné projekčné použitie – finálne rozpočty sa robia v CENKROS-e, táto
databáza slúži na:

1. **Tvorbu výkazu výmer** – z reálnych rozpočtov podobných stavieb zistiť,
   ktoré položky do takého objektu patria a čo k nim sprievodne patrí
   (napr. k ETICS aj lepenie, kotvenie, sieťka, lišty, lešenie, presun hmôt).
2. **Orientačné ocenenie v skorej fáze** (štúdia, DUR) – trhové ceny
   namiesto smerných.
3. **Kontrolu rozpočtu** – porovnať ceny z CENKROS-u s reálnym trhom.
4. **Hľadanie alternatív** – čo použili iní na porovnateľnej stavbe
   (napr. kaskáda menších tepelných čerpadiel namiesto jedného veľkého).

## Schéma databázy (`ceny_spolu.db`)

| tabuľka | obsah |
|---|---|
| `cennik_tskp(kod, mj, popis, n, median, p25, p75)` | katalóg položiek; `n` = počet reálnych cien, z ktorých je medián |
| `cennik_fts(kod, mj, popis)` | FTS5 fulltext nad katalógom, ignoruje diakritiku |
| `cenove_body(zakazka_id, subor, harok, kod, popis, mj, mnozstvo, jedn_cena, zdroj, zdroj_url)` | surové položky z jednotlivých ponúk/zmlúv; `zdroj_url` = odkaz na verejný zdroj |
| `zakazky(id, nazov, obstaravatel, cpv, cpv_popis, kraj, aktualizacia)` | metadáta zákaziek z ÚVO |
| `crz_zmluvy(zmluva_id, datum_davky, predmet, objednavatel, dodavatel, suma)` | metadáta zmlúv z CRZ – **dáva cenám dátum** |
| `diely(prefix, nazov, kategoria)` | číselník dielov TSKP: `ASR-HSV`, `ASR-PSV`, `profesie` |
| `rozpis_vymery(kod, popis_polozky, mj, popis_riadku, vyraz, hodnota, zdroj_subor)` | ako sa výmera odvodzuje z rozmerov (`0,40*0,40*3,35*24`) |

Prepojenia:
- ÚVO: `cenove_body.zakazka_id = zakazky.id`
- CRZ: `cenove_body.zakazka_id = 'crz_' || crz_zmluvy.zmluva_id`
- katalóg ↔ fulltext: `cennik_tskp.kod = cennik_fts.kod AND ...mj = ...mj`

## Typické dotazy

```sql
-- hľadanie položky voľným textom (diakritika nevadí)
SELECT c.kod, c.mj, c.popis, c.n, round(c.median,2), round(c.p25,2)||'-'||round(c.p75,2)
FROM cennik_tskp c JOIN cennik_fts f ON c.kod=f.kod AND c.mj=f.mj
WHERE cennik_fts MATCH 'beton zaklad*' ORDER BY c.n DESC;

-- len ASR (bez profesií ZTI/ÚK/elektro/VZT)
SELECT c.* FROM cennik_tskp c
JOIN diely d ON substr(c.kod,1,length(d.prefix))=d.prefix
WHERE d.kategoria LIKE 'ASR%' AND c.n >= 5;

-- ceny za posledný rok (cez CRZ dátumy)
SELECT b.kod, b.popis, b.jedn_cena, z.datum_davky, b.zdroj_url
FROM cenove_body b JOIN crz_zmluvy z ON b.zakazka_id='crz_'||z.zmluva_id
WHERE b.kod='275313611' AND z.datum_davky > '2025-08-01';

-- ako sa počíta výmera tejto položky
SELECT popis_riadku, vyraz, hodnota FROM rozpis_vymery WHERE kod='331321610';

-- čo býva v rozpočtoch spolu s danou položkou (spoluvýskyt)
SELECT b2.kod, count(DISTINCT b2.zakazka_id) v
FROM cenove_body b1 JOIN cenove_body b2 ON b1.zakazka_id=b2.zakazka_id
WHERE b1.kod='713131145' AND b2.kod<>b1.kod
GROUP BY b2.kod ORDER BY v DESC LIMIT 20;
```

## Pravidlá pri práci s dátami

- **Cenu nikdy neuvádzaj samotnú** – vždy s `n` (počet pozorovaní) a rozpätím
  p25–p75. Pri `n < 3` označ ako málo spoľahlivé.
- **Položky si nevymýšľaj.** Vyberaj len z `cennik_tskp`; keď sa niečo nenájde,
  povedz to a nechaj na doplnenie z CENKROS-u.
- **Výmery nevymýšľaj.** Odvoď len to, čo sa dá spočítať zo zadaných rozmerov;
  zvyšok označ ako „doplniť z výkresov".
- **Pozor na extrémy** – v dátach sú aj chyby extrakcie a taktické ocenenia
  (uchádzač presúva maržu medzi položkami). Medián cez viac ponúk to tlmí,
  ale pri podozrivej cene over `zdroj_url`.
- **Ceny starnú** – pri CRZ dátach filtruj podľa `datum_davky`, pri ÚVO
  pomôže `zakazky.aktualizacia`.
- Ceny sú **bez DPH**; „farebné prevedenie" a atypy bývajú výrazne drahšie
  než štandard – nemiešaj ich do jedného mediánu.

## Pipeline (obnova a rozšírenie dát)

```bash
pip install openpyxl pypdfium2

python run_local.py               # celý zber z ÚVO + build ceny.db
python run_local.py --vlakna 4    # šetrnejšie k sieti
python run_local.py --len-db      # len prebuduj DB z už stiahnutých dát

python 05_crz.py --dni 1460       # zmluvy z CRZ (4 roky dozadu)
python 09_rozpis_vymery.py --db ceny_spolu.db
python 08_zluc.py --do ceny_spolu.db ceny-cloud.db data/ceny.db
```

| skript | čo robí |
|---|---|
| `01_zakazky.py` | zoznam zákaziek podľa CPV kódov (`cpv_kody.txt`) |
| `02_dokumenty.py` | stiahne ponuky uchádzačov z profilov |
| `03_vyhodnotenie.py` | extrakcia položiek (xlsx + textové PDF), report výťažnosti |
| `04_postav_db.py` | postaví `ceny.db` |
| `05_crz.py` | zmluvy a rozpočty z CRZ |
| `06_ocr.py` | OCR skenovaných PDF (pomalé, potrebuje tesseract + slk) |
| `07_prune.py` | prerieďovanie ZIPov (šetrí disk) |
| `08_zluc.py` | zlúči viac `ceny.db` do jednej |
| `09_rozpis_vymery.py` | rozpisy výmer |
| `run_local.py` | spúšťač celého zberu s auto-reštartom vlákien |

`data/` sa neverzuje (surové PDF/xlsx sú medziprodukt, dajú sa stiahnuť znova).
Stav zberu drží `data/hotovo.txt` – reštart pokračuje tam, kde skončil.

## Poznámky k dátam

- Ponuky sa v profile zverejňujú **až po uzavretí zmluvy**, takže bežiace
  súťaže dáta nemajú; povinnosť platí od 31. 3. 2022.
- Cca polovica PDF sú **skeny** – bez OCR z nich nič nie je.
- Skutočné **figúry** (pomenované premenné v KROS-e) sa do exportu dostanú
  len keď sa zaškrtne „s figúrami“, takže vo zverejnených výkazoch nie sú.
  Preto pracujeme s rozpisom výmery (viď `rozpis_vymery`).
- Zdroje sú verejné dokumenty; pri publikovaní dát navonok drž pri každej
  cene `zdroj_url`, nech je dohľadateľná.
