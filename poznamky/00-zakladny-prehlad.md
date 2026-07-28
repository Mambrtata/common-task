# 00 – Základný prehľad (ťahák na skúšku)

Toto je kostra – čísla a pravidlá, ktoré sa v teste opakujú najčastejšie.
Detaily dopĺňame v samostatných súboroch podľa modulov kurzu.

---

## 1. Tri kategórie prevádzky

| Kategória | Riziko | Čo to znamená |
|---|---|---|
| **Otvorená (Open)** | nízke | Bez povolenia a bez schválenia, ak dodržíš pravidlá. Tu sme my. |
| **Osobitná (Specific)** | stredné | Treba povolenie úradu / STS / LUC + posúdenie rizika (SORA). |
| **Certifikovaná (Certified)** | vysoké | Ako klasické letectvo – certifikácia lietadla, licencia pilota. |

**Základné limity otvorenej kategórie:**
- MTOM dronu **< 25 kg**
- **VLOS** – nepretržitý vizuálny kontakt s dronom priamo očami (nie cez FPV okuliare, nie cez obrazovku)
- max. výška **120 m** nad najbližším bodom povrchu zeme
- **nikdy nad zhromaždeniami ľudí**
- neprepravovať nebezpečný tovar, nezhadzovať materiál
- jeden pilot ovláda naraz **len jeden dron**

---

## 2. Podkategórie A1 / A2 / A3

| Podkat. | Vzťah k ľuďom | Triedy dronov | Výcvik |
|---|---|---|---|
| **A1** | Smie preletieť nad **nezúčastnenými osobami** (C0), ale nemá to robiť zámerne. Nikdy nie nad zhromaždením. | C0 (<250 g), C1 (<900 g) + staré <250 g | C0: stačí manuál. C1: tento online kurz + test |
| **A2** | **Blízko** ľudí – min. **30 m** horizontálne, alebo **5 m** v režime nízkej rýchlosti | C2 (<4 kg) | Navyše osvedčenie A2 (praktický self-training + skúška na úrade) |
| **A3** | **Ďaleko** od ľudí – žiadne nezúčastnené osoby v priestore letu, min. **150 m** od obytných, obchodných, priemyselných a rekreačných zón | C2, C3, C4 (<25 kg) + staré <25 kg | Tento online kurz + test |

> **Pozor na formulácie v teste:** 30 m / 5 m je pri A2, 150 m je pri A3. Nezameniť.

---

## 3. Triedy dronov (C-značky)

| Trieda | Hmotnosť / limit | Podkategória | Vybrané požiadavky |
|---|---|---|---|
| **C0** | < 250 g | A1 | max. rýchlosť 19 m/s, obmedzenie výšky 120 m |
| **C1** | < 900 g **alebo** energia nárazu < 80 J | A1 | 19 m/s vo vodorovnom lete, priama diaľková identifikácia, geo-awareness, výstraha nízkej batérie, svetlá |
| **C2** | < 4 kg | A2 (a A3) | režim nízkej rýchlosti (≤ 3 m/s), diaľková identifikácia, geo-awareness |
| **C3** | < 25 kg, rozmer < 3 m | A3 | diaľková identifikácia, geo-awareness |
| **C4** | < 25 kg | A3 | bez automatických režimov (klasické modely lietadiel) |

**„Legacy" / drony bez C-značky** (kúpené pred prechodným obdobím):
- < 250 g → smie sa lietať v **A1**
- < 25 kg → len v **A3**

---

## 4. Registrácia a vek

**Registruje sa prevádzkovateľ UAS, nie dron.**

Registrácia je povinná, ak dron:
- má MTOM **≥ 250 g**, **alebo**
- pri náraze do človeka prenesie **> 80 J**, **alebo**
- je vybavený **senzorom schopným zachytiť osobné údaje** (kamera!) – okrem hračiek

→ Prakticky: **akýkoľvek dron s kamerou, aj pod 250 g, vyžaduje registráciu.**

- Registračné číslo prevádzkovateľa (e-reg číslo) treba **nalepiť na dron** a nahrať do systému diaľkovej identifikácie.
- Registrácia platí v **jednej krajine** – tej, kde máš pobyt/sídlo. Nie je možné registrovať sa vo viacerých.
- SR: Dopravný úrad, portál `dron.nsat.sk`.

**Minimálny vek diaľkového pilota: 16 rokov.** Členský štát ho môže znížiť až na 12.
Neplatí pre hračky, súkromne vyrobené drony < 250 g a pre let pod dohľadom kvalifikovaného pilota.

---

## 5. Výška a odstupy

- **120 m** nad najbližším bodom zemského povrchu.
  - V kopcovitom teréne sa meria od **terénu pod dronom**, nie od miesta štartu.
- Výnimka: pri umelej prekážke vyššej ako **105 m** smieš na požiadanie prevádzkovateľa prekážky vystúpiť do **15 m nad jej výšku**.
- Pri lete blízko prekážky: max. 120 m, ale hlavne bezpečná vzdialenosť.
- A3: **150 m** horizontálne od obytných, obchodných, priemyselných a rekreačných zón.

---

## 6. Zemepisné zóny (UAS geographical zones)

- Členské štáty vyhlasujú zóny, kde je let **zakázaný, obmedzený alebo podmienený povolením**.
- **Vždy skontroluj pred letom** – v mobilnej appke / na národnom geoportáli.
- Typicky obmedzené: okolie letísk (CTR/ATZ), vojenské priestory, väznice, jadrové elektrárne, nemocnice, chránené územia, národné parky, mestské centrá, dočasné obmedzenia (VIP návštevy, veľké podujatia, zásah záchranárov).
- **Manned aircraft majú vždy prednosť** – ak vidíš/počuješ lietadlo alebo vrtuľník, okamžite klesaj a pristáň.
- Nikdy nelietaj v blízkosti prebiehajúceho zásahu (požiar, letecká záchranka, polícia).

---

## 7. Ľudská výkonnosť – rýchle pripomenutie

- **Nelietaj pod vplyvom** alkoholu, drog ani liekov ovplyvňujúcich pozornosť; ani unavený, chorý či v strese.
- Ostrý obraz vidíš len v úzkom uhle (~2°) – oko musí dron aktívne „hľadať".
- Vzdialený dron ľahko stratíš zo zraku alebo si pomýliš orientáciu (predok/zadok) → pozor pri lete smerom k sebe, ovládanie sa „obráti".
- Sústredenie na obrazovku = strata prehľadu o okolí. Preto VLOS a prípadne pozorovateľ.
- Multitasking a stres znižujú výkon – maj plán letu a postupy pre núdzu vopred.

---

## 8. Súkromie a ochrana údajov (GDPR)

- Ak dron sníma identifikovateľné osoby, SPZ, interiéry domov → spracúvaš **osobné údaje** a platí **GDPR**.
- Výnimka „domáce použitie" je úzka – neplatí, ak zábery zverejníš alebo použiješ komerčne.
- Zásady: minimalizácia údajov, informovanie dotknutých osôb, bezpečné uloženie, nezverejňovať bez súhlasu.
- Neleť zámerne nad súkromnými pozemkami a nesnímaj ľudí bez dôvodu – aj keď je let sám o sebe legálny, snímanie môže byť priestupok.

---

## 9. Poistenie

- **Nariadenie (ES) 785/2004** – poistenie zodpovednosti voči tretím osobám je povinné pre lietadlá; pre drony **≥ 20 kg** vždy.
- Pod 20 kg si podmienky určuje **každý členský štát** – vo väčšine krajín (vrátane SR) je poistenie zodpovednosti povinné alebo dôrazne odporúčané.
- Bežné poistenie domácnosti dron **väčšinou nekryje**, hlavne nie komerčné použitie.

---

## 10. Bezpečnostná ochrana (security)

- Chráň dron a ovládač pred neoprávneným použitím (heslá, aktualizácie firmvéru, šifrované spojenie).
- Pozor na **rušenie/spoofing GPS** a stratu spojenia – vedieť, čo dron urobí (RTH / hover / pristátie).
- Neposkytuj citlivé letové dáta tretím stranám; pozor na to, čo appka posiela do cloudu.
- Nikdy nelietaj nad kritickou infraštruktúrou (elektrárne, prístavy, väznice, letiská, vojenské objekty).
- Podozrivé správanie iných dronov nahlás.

---

## 11. Pred letom – checklist

1. Som fit? (alkohol, únava, lieky, stres)
2. Je dron registrovaný, číslo nalepené?
3. Firmvér a appka aktuálne, batérie nabité a nepoškodené?
4. Vizuálna kontrola: vrtule, rám, kryty, akumulátor (nafúknutý = vyhoď)
5. Počasie: vietor, dážď, teplota, viditeľnosť
6. Geo-zóny a NOTAM skontrolované, mám prípadné povolenie?
7. Priestor: ľudia, prekážky, drôty, zvieratá; kde je núdzové miesto na pristátie?
8. Kompas/IMU kalibrovaný, GPS fix, RTH výška nastavená nad najvyššiu prekážku
9. Poznám hranice A1/A3 pre svoj dron a držím ich

---

## 12. Núdzové situácie

| Situácia | Reakcia |
|---|---|
| Strata spojenia | Dron ide do RTH – nechaj ho, sleduj; predtým maj správne nastavenú výšku RTH |
| Strata VLOS | Zastav, stúpaj/otoč sa opatrne alebo aktivuj RTH; nikdy nepokračuj naslepo |
| Nízka batéria | Okamžitý návrat, nikdy nedoletuj „na doraz" – vietor spotrebu zvyšuje |
| Blíži sa lietadlo/vrtuľník | Okamžite klesaj a pristáň, uvoľni priestor |
| Flyaway | Vypni ovládač? Nie – najprv skús RTH; ak dron zmizne, nahlás udalosť |
| Nehoda so zranením / vážna škoda | Nahlás úradu (v SR Dopravný úrad); zdokumentuj |
