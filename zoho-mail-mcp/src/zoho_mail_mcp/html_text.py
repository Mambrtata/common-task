"""Prevod HTML tela mailu na čitateľný text."""

from __future__ import annotations

import re
from html import unescape
from html.parser import HTMLParser

# Obsah týchto značiek do textu nepatrí. Sú tu len značky, ktoré majú
# koncovú značku a skutočný obsah. Prázdne značky ako <meta> a <link> sem
# nepatria: koncovú značku nemajú, takže by preskakovanie nikdy neskončilo
# a zahodilo by celé telo. Outlook ich do hlavičky dáva vždy.
_SKIPPED = frozenset({"script", "style", "title", "noscript"})

# Po týchto značkách chceme zalomenie riadku.
_BLOCK = frozenset(
    {
        "address", "article", "blockquote", "br", "div", "figure", "footer",
        "h1", "h2", "h3", "h4", "h5", "h6", "header", "hr", "li", "ol", "p",
        "pre", "section", "table", "tbody", "td", "th", "tr", "ul",
    }
)

_SCRIPT_OR_STYLE = re.compile(
    r"<(script|style|title|noscript)\b.*?</\1\s*>", re.IGNORECASE | re.DOTALL
)
_ANY_TAG = re.compile(r"<[^>]*>")
_MULTI_BLANK = re.compile(r"\n{3,}")
_TRAILING_SPACE = re.compile(r"[ \t]+\n")
_MULTI_SPACE = re.compile(r"[ \t]{2,}")


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        # Zásobník otvorených preskakovaných značiek. Keď v maili chýba
        # koncová značka, nezasekne sa preskakovanie navždy – rozbalí sa
        # až po najbližšiu zhodu.
        self._skipping: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIPPED:
            self._skipping.append(tag)
        elif tag in _BLOCK:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIPPED:
            if tag in self._skipping:
                # Zahodíme aj všetko, čo sa medzitým neuzavrelo.
                del self._skipping[self._skipping.index(tag):]
        elif tag in _BLOCK:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skipping:
            self._parts.append(data)

    def text(self) -> str:
        return "".join(self._parts)


def html_to_text(html: str | None) -> str:
    """Zo Zoho `content` (HTML) spraví text bez značiek a prázdnych riadkov navyše."""
    if not html:
        return ""

    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    text = _tidy(parser.text())

    # Poistka: pri rozbitom HTML (napr. neuzavretý <style>) by parser zahodil
    # všetko a vrátil prázdny reťazec. Prázdne telo pritom vyzerá ako mail bez
    # obsahu, hoci obsah má – radšej hrubší prevod než tiché nič.
    if not text:
        stripped = _SCRIPT_OR_STYLE.sub(" ", html)
        stripped = _ANY_TAG.sub(" ", stripped)
        text = _tidy(unescape(stripped))

    return text


def _tidy(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ")
    text = _MULTI_SPACE.sub(" ", text)
    text = _TRAILING_SPACE.sub("\n", text)
    text = _MULTI_BLANK.sub("\n\n", text)
    return text.strip()


def truncate(text: str, max_chars: int) -> tuple[str, bool]:
    """Skráti text a povie, či sa skracovalo – nech model vie, že mu chýba koniec."""
    if max_chars <= 0 or len(text) <= max_chars:
        return text, False
    return text[:max_chars].rstrip(), True
