"""Prevod HTML tela mailu na čitateľný text."""

from __future__ import annotations

import re
from html.parser import HTMLParser

# Obsah týchto značiek do textu nepatrí.
_SKIPPED = frozenset({"script", "style", "head", "title", "meta", "link", "noscript"})

# Po týchto značkách chceme zalomenie riadku.
_BLOCK = frozenset(
    {
        "address", "article", "blockquote", "br", "div", "figure", "footer",
        "h1", "h2", "h3", "h4", "h5", "h6", "header", "hr", "li", "ol", "p",
        "pre", "section", "table", "tbody", "td", "th", "tr", "ul",
    }
)

_MULTI_BLANK = re.compile(r"\n{3,}")
_TRAILING_SPACE = re.compile(r"[ \t]+\n")
_MULTI_SPACE = re.compile(r"[ \t]{2,}")


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIPPED:
            self._skip_depth += 1
        elif tag in _BLOCK:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIPPED:
            self._skip_depth = max(self._skip_depth - 1, 0)
        elif tag in _BLOCK:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
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

    text = parser.text().replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ")
    text = _MULTI_SPACE.sub(" ", text)
    text = _TRAILING_SPACE.sub("\n", text)
    text = _MULTI_BLANK.sub("\n\n", text)
    return text.strip()


def truncate(text: str, max_chars: int) -> tuple[str, bool]:
    """Skráti text a povie, či sa skracovalo – nech model vie, že mu chýba koniec."""
    if max_chars <= 0 or len(text) <= max_chars:
        return text, False
    return text[:max_chars].rstrip(), True
