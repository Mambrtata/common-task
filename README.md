# Poznámky – UAS Remote Pilot, Open Category A1/A3

Poznámky k e-learningovému kurzu **UAS-OPEN-A1+A3** (EUROCONTROL + Direction de l'Aviation Civile Luxembourg),
ktorý je podľa **Nariadenia EÚ 2019/947** podmienkou na lietanie s dronom v otvorenej kategórii A1 a A3.

## Ako pracujeme

1. Prechádzaš kurz modul po module.
2. Posielaš mi obsah modulu (text, screenshot, zhrnutie vlastnými slovami, otázky z kvízu).
3. Ja to spracujem do poznámok v tomto repozitári + doplním kontext a to, čo býva v teste.

## Štruktúra

| Súbor | Obsah |
|---|---|
| `poznamky/00-zakladny-prehlad.md` | Ťahák – najdôležitejšie čísla a pravidlá na skúšku |
| `poznamky/01-letecka-bezpecnost.md` | Air safety |
| `poznamky/02-vzdusny-priestor.md` | Airspace restrictions |
| `poznamky/03-letecke-predpisy.md` | Aviation regulations |
| `poznamky/04-ludska-vykonnost.md` | Human performance limitations |
| `poznamky/05-prevadzkove-postupy.md` | Operational procedures |
| `poznamky/06-znalosti-o-uas.md` | UAS general knowledge |
| `poznamky/07-sukromie-a-udaje.md` | Privacy and data protection |
| `poznamky/08-poistenie.md` | Insurance |
| `poznamky/09-bezpecnostna-ochrana.md` | Security |
| `poznamky/10-slovensko-registracia.md` | SK špecifiká – registrácia prevádzkovateľa cez slovensko.sk |

Súbory k jednotlivým predmetom pribúdajú postupne, ako prechádzame kurzom.

## O skúške

- Online teoretická skúška hneď po kurze, **40 otázok** s výberom z možností.
- Na úspech treba **75 %**, teda **30 správnych odpovedí zo 40**.
- Pokrýva 9 predmetov (viď tabuľka vyššie).
- Výsledkom je **doklad o absolvovaní online výcviku (proof of completion)**, platný **5 rokov**.
- Kurz je zadarmo, počítaj s cca 4 hodinami.

> Poznámka: certifikát vydaný v Luxembursku je platný v celej EÚ, ale **registráciu prevádzkovateľa UAS**
> si robíš v krajine svojho pobytu – pre SR cez slovensko.sk na Dopravnom úrade.
> Viď `poznamky/10-slovensko-registracia.md`.

---

## Zoho Mail konektor

V `zoho-mail-mcp/` je MCP server, cez ktorý vie Claude čítať poštu v Zoho Mail
(priečinky, vyhľadávanie, telá mailov a vlákna). Je zámerne **len na čítanie** –
nič neodosiela ani nemení. Nastavenie a zoznam nástrojov nájdeš
v `zoho-mail-mcp/README.md`.
