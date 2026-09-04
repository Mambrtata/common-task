"""Bezpečné ukladanie príloh na disk.

Názov súboru pochádza z e-mailu, teda od cudzieho odosielateľa. Nikdy sa
nepoužíva tak, ako prišiel – inak by stačila príloha menom `../../etc/passwd`.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from .errors import ZohoMailMCPError

MAX_NAME_LENGTH = 100
DEFAULT_NAME = "priloha"

# Povolíme len znaky, pri ktorých nehrozí prekvapenie v ceste ani v shelli.
# Oddeľovače ciest sem patria tiež – nahradia sa, nedelí sa podľa nich, lebo
# lomka býva súčasťou názvu ("Faktúra 8/2026.pdf") a delením by sa stratil
# celý začiatok mena.
_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")
_LEADING_DOTS = re.compile(r"^\.+")


class AttachmentTooLarge(ZohoMailMCPError):
    """Príloha presahuje nastavený strop."""


def safe_filename(name: str | None) -> str:
    """Zo vstupu od odosielateľa spraví neškodný názov súboru."""
    text = (name or "").strip()

    # Diakritiku prepíšeme na ASCII, nech je názov použiteľný všade.
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")

    text = _UNSAFE.sub("_", text)
    text = _LEADING_DOTS.sub("", text)  # ".." aj skryté súbory
    text = text.strip("._")

    if not text:
        return DEFAULT_NAME

    if len(text) > MAX_NAME_LENGTH:
        stem, dot, suffix = text.rpartition(".")
        if dot and len(suffix) <= 10:
            keep = MAX_NAME_LENGTH - len(suffix) - 1
            text = f"{stem[:keep]}.{suffix}"
        else:
            text = text[:MAX_NAME_LENGTH]

    return text


def unique_path(directory: Path, filename: str) -> Path:
    """Nájde voľné meno, nech nová príloha neprepíše staršiu."""
    candidate = directory / filename
    if not candidate.exists():
        return candidate

    stem, dot, suffix = filename.rpartition(".")
    if not dot:
        stem, suffix = filename, ""
    for index in range(1, 1000):
        name = f"{stem}-{index}.{suffix}" if suffix else f"{stem}-{index}"
        candidate = directory / name
        if not candidate.exists():
            return candidate
    raise ZohoMailMCPError(f"V {directory} sa nedá nájsť voľné meno pre {filename!r}.")


def save_attachment(
    directory: Path, filename: str | None, content: bytes, *, max_bytes: int
) -> Path:
    """Uloží prílohu do priečinka a vráti skutočnú cestu."""
    if len(content) > max_bytes:
        raise AttachmentTooLarge(
            f"Príloha má {len(content)} B, strop je {max_bytes} B. "
            "Zvýšiť sa dá cez ZOHO_MAX_ATTACHMENT_BYTES."
        )

    directory.mkdir(parents=True, exist_ok=True)
    target = unique_path(directory, safe_filename(filename))
    target.write_bytes(content)
    target.chmod(0o640)
    return target


def resolve_inside(directory: Path, name: str) -> Path:
    """Preloží meno na cestu a overí, že naozaj leží v priečinku.

    Chráni endpoint na sťahovanie: bez tejto kontroly by `../../etc/shadow`
    prešlo, aj keď sa názvy pri ukladaní čistia.
    """
    root = directory.resolve()
    candidate = (root / name).resolve()
    if candidate != root and root not in candidate.parents:
        raise ZohoMailMCPError(f"Cesta {name!r} vedie mimo priečinka s prílohami.")
    return candidate
