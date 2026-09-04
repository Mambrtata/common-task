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


def _candidate_names(filename: str):
    """Postupne filename, filename-1, filename-2, …"""
    yield filename
    stem, dot, suffix = filename.rpartition(".")
    if not dot:
        stem, suffix = filename, ""
    for index in range(1, 1000):
        yield f"{stem}-{index}.{suffix}" if suffix else f"{stem}-{index}"


def _same_content(path: Path, content: bytes) -> bool:
    return path.stat().st_size == len(content) and path.read_bytes() == content


def target_path(directory: Path, filename: str, content: bytes) -> tuple[Path, bool]:
    """Kam prílohu uložiť. Druhá hodnota hovorí, či tam už taká leží.

    Rovnaká príloha stiahnutá druhýkrát nevytvára kópiu – vráti sa pôvodný
    súbor. Kópia vznikne len vtedy, keď sa pod tým istým menom skrýva iný
    obsah, aby sa staršia príloha neprepísala.
    """
    for name in _candidate_names(filename):
        candidate = directory / name
        if not candidate.exists():
            return candidate, False
        if _same_content(candidate, content):
            return candidate, True
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
    target, already_there = target_path(directory, safe_filename(filename), content)
    if already_there:
        return target

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


# --------------------------------------------------------------- čítanie obsahu

# Prípony, ktoré vieme prečítať priamo ako text.
TEXT_SUFFIXES = frozenset(
    {".txt", ".csv", ".tsv", ".md", ".json", ".xml", ".html", ".htm", ".log", ".ics"}
)


class UnsupportedAttachment(ZohoMailMCPError):
    """Z tohto typu prílohy text vytiahnuť nevieme."""


def extract_text(filename: str | None, content: bytes) -> tuple[str, str]:
    """Vráti (text, druh). Druh je 'pdf' alebo 'text'.

    Obrázky, archívy a tabuľky sa nečítajú – na tie treba súbor stiahnuť.
    """
    name = (filename or "").lower()

    if name.endswith(".pdf") or content[:5] == b"%PDF-":
        return _pdf_to_text(content), "pdf"

    if any(name.endswith(suffix) for suffix in TEXT_SUFFIXES):
        return _decode(content), "text"

    # Bez použiteľnej prípony skúsime, či to nie je obyčajný text.
    if _looks_like_text(content):
        return _decode(content), "text"

    raise UnsupportedAttachment(
        f"Prílohu {filename!r} neviem previesť na text. Čítať viem PDF a textové "
        "formáty; ostatné si stiahni cez zoho_download_attachment."
    )


def _pdf_to_text(content: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - závisí od inštalácie
        raise UnsupportedAttachment(
            "Na čítanie PDF chýba knižnica pypdf. Doinštaluj ju: pip install pypdf"
        ) from exc

    import io

    try:
        reader = PdfReader(io.BytesIO(content))
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:
        raise UnsupportedAttachment(
            f"PDF sa nepodarilo prečítať: {exc}. Býva to pri skenoch, kde je "
            "text len obrázok."
        ) from exc

    text = "\n\n".join(page.strip() for page in pages if page.strip())
    if not text.strip():
        raise UnsupportedAttachment(
            "PDF neobsahuje textovú vrstvu – je to zrejme sken. Text by z neho "
            "dostalo až OCR, ktoré konektor nerobí."
        )
    return text


def _decode(content: bytes) -> str:
    for encoding in ("utf-8", "cp1250", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


def _looks_like_text(content: bytes) -> bool:
    head = content[:2048]
    if not head:
        return False
    if b"\x00" in head:  # binárne súbory takmer vždy obsahujú nulový bajt
        return False
    try:
        head.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True
