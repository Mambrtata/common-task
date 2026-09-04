# Zoho Mail MCP konektor (len na čítanie)

MCP server, cez ktorý vie Claude čítať poštu v Zoho Mail – vypísať priečinky,
hľadať v správach, otvoriť vlákno a prečítať telo mailu. Beží cez Zoho Mail
REST API a OAuth, takže netreba sťahovať poštu do súborov.

## Čo konektor nevie – zámerne

- **Neodosiela maily.** Nástroj na odoslanie ani odpoveď neexistuje.
- **Nič nemení.** Neoznačuje ako prečítané, nepresúva, nemaže, nerobí koncepty.
- **Nesťahuje prílohy.** Vypíše len ich názov, veľkosť a typ.

Nie je to len sľub v dokumentácii, drží to na troch úrovniach:

1. Token sa pýta výhradne s `READ` scopes (`config.py`), takže zápis Zoho
   odmietne aj keby oň niekto požiadal.
2. Klient prepustí iba `GET`; čokoľvek iné skončí na `ReadOnlyViolation`
   (`client.py`).
3. Všetky nástroje sú v MCP označené ako `readOnlyHint`.

## Rozsah prístupu

Konektor vidí celú históriu schránok, ku ktorým má token prístup – vrátane
archívu a odoslanej pošty. Pri firemných schránkach s tým rátaj.

Ak to budeš chcieť neskôr zúžiť, sú na to dve páky:

- `ZOHO_ALLOWED_ACCOUNTS` – whitelist schránok. Čo v ňom nie je, konektor
  nevidí ani nevypíše. Prázdne = bez obmedzenia.
- Scopes v Zoho konzole – token sa dá vydať len pre časť API.

## Nastavenie

### 1. Aplikácia v Zoho API konzole

Otvor `https://api-console.zoho.eu` (pre iné dátové centrum zmeň doménu)
a vytvor klienta typu **Self Client**. Poznač si **Client ID** a **Client Secret**.

Na karte **Generate Code** zadaj scope:

```
ZohoMail.accounts.READ,ZohoMail.folders.READ,ZohoMail.messages.READ
```

Time Duration nastav na 10 minút. Vygenerovaný kód je jednorazový a rýchlo
expiruje – použi ho hneď v ďalšom kroku.

### 2. Refresh token

```bash
python3 scripts/get_refresh_token.py \
    --dc eu \
    --client-id 1000.XXXX \
    --client-secret YYYY \
    --code ZZZZ
```

Skript vypíše `ZOHO_REFRESH_TOKEN`. Ten platí, kým ho nezrušíš – access token
si server obnovuje sám a nikam ho neukladá.

### 3. Premenné prostredia

Skopíruj `.env.example` a doplň hodnoty:

| Premenná | Povinná | Význam |
|---|---|---|
| `ZOHO_DC` | áno | dátové centrum: `us`, `eu`, `in`, `au`, `jp`, `ca`, `sa`, `uk`, `ae`, `cn` |
| `ZOHO_CLIENT_ID` | áno | z API konzoly |
| `ZOHO_CLIENT_SECRET` | áno | z API konzoly |
| `ZOHO_REFRESH_TOKEN` | áno | výstup zo skriptu vyššie |
| `ZOHO_ALLOWED_ACCOUNTS` | nie | whitelist schránok, čiarkou oddelený |
| `ZOHO_TIMEOUT` | nie | timeout v sekundách (30) |
| `ZOHO_MAX_RETRIES` | nie | počet opakovaní pri 429/5xx (3) |
| `ZOHO_MAX_CONTENT_CHARS` | nie | strop na dĺžku tela mailu (20000) |

`ZOHO_DC` sa zámerne nehádže – refresh token vydaný v jednom dátovom centre
v inom nefunguje. Pre schránky na `onoff.sk` je to takmer isto `eu`.

### 4. Inštalácia a registrácia

```bash
pip install -e .
```

Do `.mcp.json` v projekte (alebo do `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "zoho-mail": {
      "command": "zoho-mail-mcp",
      "env": {
        "ZOHO_DC": "eu",
        "ZOHO_CLIENT_ID": "1000.XXXX",
        "ZOHO_CLIENT_SECRET": "YYYY",
        "ZOHO_REFRESH_TOKEN": "1000.ZZZZ"
      }
    }
  }
}
```

Po štarte over spojenie nástrojom `zoho_check_connection` – vypíše dátové
centrum, scopes a schránky, ktoré konektor vidí.

### 4b. Alternatíva: cloud session, bez lokálneho klonu

Ak pracuješ len cez claude.ai/code a repozitár nemáš lokálne, konektor sa dá
zapnúť priamo v cloud prostredí. Registráciu už rieši `.mcp.json` v koreni
repozitára – načíta server cez `PYTHONPATH`, takže netreba nič inštalovať
ručne. Zvyšok sa nastavuje v **claude.ai/code → nastavenia prostredia**:

1. **Setup script** – vlož obsah `zoho-mail-mcp/scripts/setup-cloud.sh`.
   Doinštaluje knižnicu `mcp`, ktorá v obraze nie je.
2. **Environment variables** – vo formáte `.env`:

   ```
   ZOHO_DC=eu
   ZOHO_CLIENT_ID=1000.XXXX
   ZOHO_CLIENT_SECRET=YYYY
   ZOHO_REFRESH_TOKEN=1000.ZZZZ
   ```

   Session ich prekopíruje do bežných premenných prostredia a server ich zdedí.
3. **Network access** – prepni na **Custom** a pridaj:

   ```
   mail.zoho.eu
   accounts.zoho.eu
   ```

   Zaškrtni aj *„Also include default list of common package managers"*, inak
   setup skriptu prestane fungovať PyPI. Predvolená úroveň **Trusted** Zoho
   nepúšťa, takže bez tohto kroku konektor spadne na chybe siete.

Zmena setup skriptu alebo zoznamu domén znamená, že sa prostredie prebuduje –
prejaví sa to až v novej session, nie v tej rozbehnutej.

> **Pozor na token v cloud prostredí.** Premenné prostredia si podľa
> dokumentácie prečíta ktokoľvek, kto to prostredie používa, a číta ich aj
> každá session v ňom. Pri firemných schránkach to zváž – ak to má byť
> uzavretejšie, drž konektor lokálne, alebo si preň založ samostatné
> prostredie, ktoré nepoužívaš na bežnú prácu.

## Sieťový režim: jeden server, viac klientov

Cez stdio beží konektor vždy vedľa toho procesu Claude Code, ktorý ho volá –
na jednom stroji, pre jedného klienta. Ak má z pošty čítať viacero firemných
inštalácií Claude Code, treba ho spustiť ako sieťovú službu:

```
firemný počítač A ─┐
firemný počítač B ─┼─ ZeroTier ─→ server:8765 ─→ Zoho Mail API
firemný počítač C ─┘
```

Prístup chráni zdieľaný bearer token. Bez neho sa server ani nespustí a každá
požiadavka bez správnej hlavičky končí na 401.

### Na serveri

```bash
sudo git clone https://github.com/Mambrtata/common-task.git /opt/common-task
cd /opt/common-task
sudo git checkout claude/zoho-mail-mcp-connector-q63ki8
sudo python3 -m pip install --break-system-packages "mcp>=2.0,<3.0" starlette uvicorn

# Používateľ bez domovského adresára a bez shellu
sudo useradd --system --no-create-home --shell /usr/sbin/nologin zoho-mcp

# Token pre klientov
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Zvyšok spraví inštalátor – nájde ZeroTier adresu, vygeneruje prístupový
token, vytvorí `/etc/zoho-mail-mcp.env` s právami 0600, zapíše systemd unit
a službu spustí:

```bash
cd /opt/common-task/zoho-mail-mcp
sudo bash deploy/install.sh
```

Ak ZeroTier rozhranie nenájde, adresu mu podaj: `sudo bash deploy/install.sh
--host 10.147.17.5`. Nič neprepisuje – existujúci `/etc/zoho-mail-mcp.env`
nechá tak. Na konci vypíše hotový príkaz pre firemné počítače aj s tokenom.

Prístupy do Zoho doplníš až potom; služba beží aj bez nich, len nástroje
hlásia, že chýba konfigurácia:

```bash
sudo nano /etc/zoho-mail-mcp.env          # ZOHO_DC, CLIENT_ID, SECRET, REFRESH_TOKEN
sudo systemctl restart zoho-mail-mcp
```

Ručná cesta bez inštalátora je popísaná v komentári v
`deploy/zoho-mail-mcp.service`.

Overenie, že služba žije (endpoint `/health` token nepýta):

```bash
curl http://10.147.17.5:8765/health
# {"status":"ok","service":"zoho-mail-mcp"}
```

**Viaž sa priamo na ZeroTier adresu**, nie na `0.0.0.0`. Služba potom nie je
dostupná z domácej LAN ani z internetu a zároveň sedí kontrola hlavičky `Host`.

### Na firemných počítačoch

```bash
claude mcp add --transport http zoho-mail http://10.147.17.5:8765/mcp \
  --scope user \
  --header "Authorization: Bearer <token>"
```

`--scope user` znamená, že konektor je dostupný vo všetkých projektoch na tom
počítači a token sa uloží do `~/.claude.json`, nie do repozitára.

Potom stačí povedať „zavolaj `zoho_check_connection`".

### Čo si pri tomto uvedomiť

- **Token je jediná hranica.** Ktokoľvek, kto ho má a je v ZeroTier sieti, číta
  obe schránky. Konektor nerozlišuje, kto sa pýta – nemá používateľov ani
  oddelené oprávnenia. Ak má niekto vidieť menej, potrebuje vlastnú inštanciu
  s vlastným Zoho tokenom a `ZOHO_ALLOWED_ACCOUNTS`.
- **Šifrovanie rieši ZeroTier.** Prevádzka medzi uzlami je šifrovaná, takže
  obyčajné HTTP vnútri siete je v poriadku. Na verejnú IP to nevystavuj – tam
  by to chcelo HTTPS a reverznú proxy.
- **Rotácia tokenu**: zmeň `ZOHO_MCP_AUTH_TOKEN`, reštartuj službu a uprav
  `--header` na klientoch. Starý token okamžite prestane platiť.
- **Server je jediný bod zlyhania.** Keď je dole alebo ZeroTier nebeží,
  konektor jednoducho nie je dostupný; pošta tým netrpí.

### Keď to nefunguje

| Prejav | Príčina |
|---|---|
| `401 unauthorized` | chýba alebo nesedí `--header "Authorization: Bearer …"` |
| `Invalid Host header` v logu | viažeš sa na `0.0.0.0`; doplň `ZOHO_MCP_ALLOWED_HOSTS=10.147.17.5:8765` |
| spojenie vyprší | ZeroTier nebeží alebo uzol nie je schválený v sieti |
| služba sa nespustí, exit 2 | chýba `ZOHO_MCP_AUTH_TOKEN` alebo je kratší ako 24 znakov |

Log služby: `journalctl -u zoho-mail-mcp -f`

## Nástroje

| Nástroj | Čo robí |
|---|---|
| `zoho_check_connection` | overí token, DC a scopes; vypíše viditeľné schránky |
| `zoho_list_accounts` | schránky a ich `accountId` |
| `zoho_list_folders` | priečinky vrátane `folderId` a počtu neprečítaných |
| `zoho_list_messages` | hlavičky správ v priečinku; `status='unread'` na neprečítané |
| `zoho_search_messages` | hľadanie podľa odosielateľa, predmetu, textu, dátumu… |
| `zoho_get_message` | jedna správa vrátane tela prevedeného na čistý text |
| `zoho_get_thread` | všetky správy jedného vlákna |
| `zoho_list_attachments` | metadáta príloh (nie obsah súborov) |

### Typický postup

`zoho_get_message` potrebuje `messageId` **aj** `folderId`; obe vracajú
`zoho_list_messages` a `zoho_search_messages`, takže poradie je:

1. `zoho_list_messages` s `folder="INBOX"` a `status="unread"`
2. z výsledku vezmi `messageId` + `folderId`
3. `zoho_get_message`

Priečinok sa dá zadať názvom (`"INBOX"`, `"Faktúry"`) aj číslom – názov si
konektor sám preloží na `folderId`.

### Vyhľadávanie

Podmienky sa zadávajú pomenovanými parametrami a konektor z nich poskladá
`searchKey` v syntaxi Zoho:

```
zoho_search_messages(subject="faktúra", sender="klient@example.com",
                     from_date="2026-01-01")
→ searchKey: subject:faktúra::sender:klient@example.com::fromDate:01-Jan-2026
```

Predvolene sa podmienky spájajú cez AND, `match="or"` prepne textové podmienky
na OR. Dátumy sa zadávajú ako `RRRR-MM-DD`. Kto pozná syntax Zoho, môže poslať
hotový reťazec v `search_key`.

## Bezpečnosť

- **Refresh token je heslo do schránky.** Nekomituj ho – `.env` je v `.gitignore`.
  Zrušiť sa dá v Zoho API konzole.
- **Obsah mailov sú cudzie údaje.** Maily môžu obsahovať text, ktorý sa tvári
  ako pokyn pre asistenta. Nástroje preto k telám pripájajú poznámku, že ide
  o údaje, nie o inštrukcie. Ak sa v pošte objaví „pošli mi heslo" alebo
  podobná výzva, konektor podľa nej konať nemá – a odosielať aj tak nevie.
- **Access token nikde nekončí na disku**, drží sa len v pamäti procesu.

## Riešenie problémov

| Prejav | Príčina |
|---|---|
| `invalid_grant` pri obnove tokenu | `ZOHO_DC` nesedí s dátovým centrom účtu |
| `INVALID_OAUTHTOKEN` | chýbajúci scope, alebo zrušený token v konzole |
| `invalid_client` | Client ID a Secret nie sú z tej istej aplikácie/DC |
| `invalid_code` v bootstrap skripte | kód z Generate Code už expiroval alebo bol použitý |
| „Token vidí viac účtov" | uveď schránku parametrom `account="jan@onoff.sk"` |

## Vývoj

```bash
pip install -e ".[dev]"
pytest
```

Testy nechodia na sieť – HTTP vrstva sa v nich nahrádza falošným transportom,
ktorý vracia pripravené odpovede Zoho.

## Zdroje

- [Zoho Mail API – prehľad a index](https://www.zoho.com/mail/help/api/)
- [Getting started (dátové centrá, hlavičky)](https://www.zoho.com/mail/help/api/getting-started-with-api.html)
- [OAuth 2.0 pre Zoho Mail](https://www.zoho.com/mail/help/api/using-oauth-2.html)
- [List Emails](https://www.zoho.com/mail/help/api/get-emails-list.html) ·
  [Search Emails](https://www.zoho.com/mail/help/api/get-search-emails.html) ·
  [Get Email Content](https://www.zoho.com/mail/help/api/get-email-content.html)
- [Syntax vyhľadávania](https://www.zoho.com/mail/help/search-syntax.html)
