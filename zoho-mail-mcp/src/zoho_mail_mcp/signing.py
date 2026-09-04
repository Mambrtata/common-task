"""Podpísané odkazy na stiahnutie prílohy.

Klient, ktorý volá MCP, hlavičku Authorization nemá po ruke – token drží
jeho konfigurácia, nie model. Odkaz preto nesie vlastný podpis s obmedzenou
platnosťou: dá sa stiahnuť obyčajným curl bez hlavičky, ale len ten súbor
a len chvíľu.
"""

from __future__ import annotations

import hashlib
import hmac
import time
import urllib.parse

DEFAULT_TTL_SECONDS = 3600
SIGNATURE_LENGTH = 32


def sign(name: str, expires_at: int, secret: str) -> str:
    message = f"{name}\n{expires_at}".encode()
    digest = hmac.new(secret.encode("utf-8"), message, hashlib.sha256)
    return digest.hexdigest()[:SIGNATURE_LENGTH]


def signed_query(name: str, secret: str, *, ttl: int = DEFAULT_TTL_SECONDS,
                 now: float | None = None) -> str:
    """Vráti časť URL za otáznikom, aj s podpisom a časom platnosti."""
    expires_at = int((time.time() if now is None else now) + ttl)
    return urllib.parse.urlencode(
        {"exp": expires_at, "sig": sign(name, expires_at, secret)}
    )


def verify(name: str, query: str, secret: str, *, now: float | None = None) -> bool:
    """Overí podpis aj to, že odkaz ešte platí."""
    params = urllib.parse.parse_qs(query)
    signature = (params.get("sig") or [""])[0]
    raw_expiry = (params.get("exp") or [""])[0]
    if not signature or not raw_expiry:
        return False

    try:
        expires_at = int(raw_expiry)
    except ValueError:
        return False

    if (time.time() if now is None else now) > expires_at:
        return False

    return hmac.compare_digest(
        signature.encode("utf-8"), sign(name, expires_at, secret).encode("utf-8")
    )
