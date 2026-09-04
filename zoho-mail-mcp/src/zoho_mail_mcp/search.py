"""Skladanie reťazca `searchKey` pre Zoho Mail vyhľadávanie.

Zoho má vlastnú syntax: `parameter:hodnota`, podmienky sa spájajú cez `::`
(AND) alebo `:or:` (OR). Napríklad:
    subject:faktúra::sender:jano@onoff.sk::has:attachment
"""

from __future__ import annotations

from datetime import date, datetime

from .errors import ZohoMailMCPError

_MONTHS = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)

# Poradie je zámerné – takto sa searchKey číta rovnako, ako ho človek zadá.
_TERMS: tuple[tuple[str, str], ...] = (
    ("text", "entire"),
    ("content", "content"),
    ("subject", "subject"),
    ("sender", "sender"),
    ("to", "to"),
    ("cc", "cc"),
    ("file_name", "fileName"),
    ("file_content", "fileContent"),
    ("has", "has"),
    ("folder", "in"),
    ("label", "label"),
)


class SearchKeyError(ZohoMailMCPError):
    """Vstup sa nedá bezpečne preložiť do syntaxe Zoho."""


def zoho_date(value: str | date | datetime) -> str:
    """Prevedie dátum na tvar, ktorý Zoho očakáva: 12-Sep-2017."""
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return f"{value.day:02d}-{_MONTHS[value.month - 1]}-{value.year}"

    text = str(value).strip()
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise SearchKeyError(
            f"Dátum {text!r} neviem prečítať. Použi tvar RRRR-MM-DD, napr. 2026-01-31."
        ) from exc
    return zoho_date(parsed)


def _clean(name: str, value: str) -> str:
    text = str(value).strip()
    if not text:
        raise SearchKeyError(f"Parameter {name} je prázdny.")
    # `::` a `:or:` sú oddeľovače podmienok; v hodnote by rozbili celý searchKey.
    if "::" in text or ":or:" in text:
        raise SearchKeyError(
            f"Hodnota parametra {name} nesmie obsahovať '::' ani ':or:' – "
            "sú to oddeľovače podmienok. Zadaj podmienky samostatne."
        )
    return text


def build_search_key(
    *,
    text: str | None = None,
    content: str | None = None,
    subject: str | None = None,
    sender: str | None = None,
    to: str | None = None,
    cc: str | None = None,
    file_name: str | None = None,
    file_content: str | None = None,
    has: str | None = None,
    folder: str | None = None,
    label: str | None = None,
    from_date: str | date | None = None,
    to_date: str | date | None = None,
    include_spam_trash: bool | None = None,
    group_result: bool | None = None,
    match: str = "and",
) -> str:
    """Poskladá searchKey z pomenovaných parametrov.

    `match="or"` spojí *textové* podmienky cez `:or:`; dátumy a prepínače sa
    vždy pripájajú cez AND, inak by výsledok nedával zmysel.
    """
    values = locals()
    conditions = [
        f"{zoho_name}:{_clean(arg_name, values[arg_name])}"
        for arg_name, zoho_name in _TERMS
        if values.get(arg_name) is not None
    ]

    if match.lower() not in ("and", "or"):
        raise SearchKeyError(f"match musí byť 'and' alebo 'or', dostal som {match!r}.")
    separator = ":or:" if match.lower() == "or" else "::"

    key = separator.join(conditions)

    filters: list[str] = []
    if from_date is not None:
        filters.append(f"fromDate:{zoho_date(from_date)}")
    if to_date is not None:
        filters.append(f"toDate:{zoho_date(to_date)}")
    if include_spam_trash is not None:
        filters.append(f"inclspamtrash:{'true' if include_spam_trash else 'false'}")
    if group_result is not None:
        filters.append(f"groupResult:{'true' if group_result else 'false'}")

    parts = [part for part in (key, *filters) if part]
    if not parts:
        raise SearchKeyError(
            "Vyhľadávanie potrebuje aspoň jednu podmienku (napr. text, subject, "
            "sender alebo rozsah dátumov)."
        )
    return "::".join(parts)
