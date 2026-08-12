"""Spoločné funkcie pre pilotné skripty – sťahovanie z uvo.gov.sk.

Iba štandardná knižnica (urllib), žiadne závislosti.
Slušné správanie: User-Agent s kontaktom, pauza medzi requestami, retry.
"""

import html
import re
import time
import urllib.parse
import urllib.request

BASE = "https://www.uvo.gov.sk"
USER_AGENT = "cenova-db-pilot/0.1 (interny pilot; kontakt: jan.kovalcik@gmail.com)"
PAUZA_S = 0.8          # pauza medzi requestami
TIMEOUT_S = 60
RETRY = 3

_last_request = [0.0]


def fetch(url: str, binary: bool = False):
    """GET s pauzou, retry a exponenciálnym backoffom. Vráti text alebo bytes."""
    wait = PAUZA_S - (time.time() - _last_request[0])
    if wait > 0:
        time.sleep(wait)
    err = None
    for pokus in range(RETRY):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
                data = r.read()
            _last_request[0] = time.time()
            return data if binary else data.decode("utf-8", errors="replace")
        except Exception as e:  # network/HTTP – skús znova
            err = e
            time.sleep(2 ** pokus)
    raise RuntimeError(f"nepodarilo sa stiahnuť {url}: {err}")


def clean(text: str) -> str:
    """Odstráň HTML tagy a entity, zredukuj medzery."""
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def search_url(path: str, **params) -> str:
    qs = urllib.parse.urlencode({k: v for k, v in params.items() if v})
    return f"{BASE}{path}?{qs}"


# ---------------------------------------------------------------- zákazky ---

def zakazky_page(cpv: str, page_no: int):
    """Jedna stránka výsledkov vyhľadávania zákaziek pre daný CPV kód.

    Vráti zoznam dictov: id, nazov, obstaravatel, cpv_popis, kraj, aktualizacia.
    """
    url = search_url("/vyhladavanie/vyhladavanie-zakaziek",
                     cpv=cpv, druhZakazky="PRACE", pageNo=page_no)
    page = fetch(url)
    vysledky = []
    # riadky tabuľky: <tr> ... detail/<id> ... </tr>
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S):
        m = re.search(r"vyhladavanie-zakaziek/detail/(\d+)", tr)
        if not m:
            continue
        bunky = [clean(td) for td in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        bunky = [b for b in bunky if b and b not in ("EVO",)]
        zaznam = {
            "id": m.group(1),
            "nazov": bunky[0] if len(bunky) > 0 else "",
            "obstaravatel": bunky[1] if len(bunky) > 1 else "",
            "cpv_popis": bunky[2] if len(bunky) > 2 else "",
            "kraj": bunky[3] if len(bunky) > 3 else "",
            "aktualizacia": bunky[4] if len(bunky) > 4 else "",
            "cpv": cpv,
        }
        vysledky.append(zaznam)
    return vysledky


# -------------------------------------------------------------- dokumenty ---

def dokumenty_ids_pre_zakazku(nazov_zakazky: str, max_stran: int = 5):
    """Vyhľadaj IDs dokumentov podľa názvu zákazky (substring match na ÚVO)."""
    ids = []
    for page_no in range(1, max_stran + 1):
        url = search_url("/vyhladavanie/vyhladavanie-dokumentov",
                         nazovZakazky=nazov_zakazky, pageNo=page_no)
        page = fetch(url)
        found = re.findall(r"vyhladavanie-dokumentov/detail/(\d+)", page)
        nove = [i for i in dict.fromkeys(found) if i not in ids]
        if not nove:
            break
        ids.extend(nove)
    return ids


def dokument_detail(doc_id: str):
    """Detail dokumentu: typ, názvy, dodávateľ a linky na súbory."""
    url = f"{BASE}/vyhladavanie/vyhladavanie-dokumentov/detail/{doc_id}"
    page = fetch(url)

    def pole(label):
        m = re.search(label + r":\s*</th>\s*<td[^>]*>(.*?)</td>", page, re.S)
        return clean(m.group(1)) if m else ""

    subory = []
    for href, blob in re.findall(
            r'href="(/vyhladavanie/vyhladavanie-dokumentov/download/[^"]+)"()', page):
        subory.append(BASE + html.unescape(href))
    nazvy_suborov = [html.unescape(n)
                     for n in re.findall(r"Názov súboru:\s*([^<]+)", page)]

    return {
        "doc_id": doc_id,
        "nazov_dokumentu": pole("Názov dokumentu"),
        "zakazka": pole("Zákazka"),
        "obstaravatel": pole("Obstarávateľ"),
        "typ_dokumentu": pole("Typ dokumentu"),
        "dodavatel": pole("Názov dodávateľa"),
        "zverejnenie": pole("Dátum zverejnenia"),
        "download_linky": subory,
        "nazvy_suborov": [n.strip() for n in nazvy_suborov],
    }
