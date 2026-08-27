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
PAUZA_S = 0.5          # pauza medzi requestami
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

def zakazky_page(cpv: str, page_no: int, druh: str = "PRACE"):
    """Jedna stránka výsledkov vyhľadávania zákaziek pre daný CPV kód.

    Vráti zoznam dictov: id, nazov, obstaravatel, cpv_popis, kraj, aktualizacia.
    """
    url = search_url("/vyhladavanie/vyhladavanie-zakaziek",
                     cpv=cpv, druhZakazky=druh, page=page_no)
    page = fetch(url)
    vysledky = []
    # riadky tabuľky: <tr> ... detail/<id> ... </tr>
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S):
        m = re.search(r"vyhladavanie-zakaziek/detail/(\d+)", tr)
        if not m:
            continue
        # pozor: bunky sa NESMÚ filtrovať na neprázdne – prázdny kraj by
        # posunul mapovanie stĺpcov (dátum by skončil v poli kraj)
        bunky = [clean(td) for td in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
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

def dokumenty_zakazky(zakazka_id: str):
    """Dokumenty zákazky cez tab „Dokumenty" na detaile zákazky.

    Rýchle (2 requesty) na rozdiel od fulltextového vyhľadávania podľa
    názvu, ktoré má za záťaže ~25 s. Vráti list dvojíc (doc_id, typ).
    """
    detail = fetch(f"{BASE}/vyhladavanie/vyhladavanie-zakaziek/detail/{zakazka_id}")
    m = re.search(r'href="(/vyhladavanie/vyhladavanie-zakaziek/dokumenty/'
                  + re.escape(zakazka_id) + r'\?cHash=[0-9a-f]+)"', detail)
    if not m:
        return []
    base_url = BASE + html.unescape(m.group(1))
    vysledky, videne = [], set()
    for page_no in range(1, 11):
        url = base_url if page_no == 1 else f"{base_url}&page={page_no}"
        page = fetch(url)
        nove = False
        for chunk in re.split(r"<tr", page):
            mm = re.search(r"vyhladavanie-dokumentov/detail/(\d+)", chunk)
            if not mm or mm.group(1) in videne:
                continue
            videne.add(mm.group(1))
            nove = True
            bunky = [clean(td) for td in
                     re.findall(r"<td[^>]*>(.*?)</td>", chunk, re.S)]
            typ = bunky[0] if bunky else ""
            vysledky.append((mm.group(1), typ))
        if not nove or len(videne) < 20 * page_no:
            break
    return vysledky


def dokumenty_ids_pre_zakazku(nazov_zakazky: str, max_stran: int = 5):
    """Vyhľadaj dokumenty podľa názvu zákazky (substring match na ÚVO).

    Vráti list dvojíc (doc_id, typ_dokumentu) – typ je priamo vo výsledkoch,
    takže detail stačí otvárať len pri relevantných typoch.
    """
    vysledky, videne = [], set()
    for page_no in range(1, max_stran + 1):
        url = search_url("/vyhladavanie/vyhladavanie-dokumentov",
                         nazovZakazky=nazov_zakazky, page=page_no)
        page = fetch(url)
        nove = False
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S):
            m = re.search(r"vyhladavanie-dokumentov/detail/(\d+)", tr)
            if not m or m.group(1) in videne:
                continue
            videne.add(m.group(1))
            nove = True
            bunky = [clean(td) for td in
                     re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
            typ = bunky[0] if bunky else ""
            vysledky.append((m.group(1), typ))
        if not nove:
            break
    return vysledky


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
    velkosti_mb = []
    for cislo, jednotka in re.findall(
            r"Veľkosť:\s*([\d\s.,]+)\s*(GB|MB|KB|B)", page, re.I):
        n = float(cislo.replace(" ", "").replace(",", "."))
        faktor = {"B": 1e-6, "KB": 1e-3, "MB": 1.0, "GB": 1e3}
        velkosti_mb.append(n * faktor[jednotka.upper()])

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
        "velkosti_mb": velkosti_mb,
    }
