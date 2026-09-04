"""Získavanie access tokenu z refresh tokenu."""

from __future__ import annotations

import json
import threading
import time
import urllib.parse
from collections.abc import Callable

from .config import SCOPE_STRING, Config
from .errors import ZohoAuthError
from .transport import Transport, request_with_retries, urlopen_transport

# Token platí hodinu; obnovujeme ho o kúsok skôr, nech nevyprší uprostred volania.
EXPIRY_SKEW_SECONDS = 120


class TokenProvider:
    """Drží access token v pamäti a obnovuje ho, keď mu vyprší platnosť.

    Access token sa zámerne nikam neukladá na disk – na disku (resp.
    v konfigurácii MCP klienta) žije len refresh token.
    """

    def __init__(
        self,
        config: Config,
        *,
        transport: Transport = urlopen_transport,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._config = config
        self._transport = transport
        self._clock = clock
        self._sleep = sleep
        self._lock = threading.Lock()
        self._access_token: str | None = None
        self._expires_at: float = 0.0

    def get_access_token(self, *, force_refresh: bool = False) -> str:
        with self._lock:
            if (
                not force_refresh
                and self._access_token
                and self._clock() < self._expires_at
            ):
                return self._access_token
            token, expires_in = self._refresh()
            self._access_token = token
            self._expires_at = self._clock() + max(expires_in - EXPIRY_SKEW_SECONDS, 0)
            return token

    def invalidate(self) -> None:
        """Zahodí uložený token – volá sa po odpovedi INVALID_OAUTHTOKEN."""
        with self._lock:
            self._access_token = None
            self._expires_at = 0.0

    def _refresh(self) -> tuple[str, int]:
        url = f"{self._config.accounts_base}/oauth/v2/token"
        payload = urllib.parse.urlencode(
            {
                "refresh_token": self._config.refresh_token,
                "client_id": self._config.client_id,
                "client_secret": self._config.client_secret,
                "grant_type": "refresh_token",
                "scope": SCOPE_STRING,
            }
        ).encode("utf-8")

        response = request_with_retries(
            self._transport,
            "POST",
            url,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            body=payload,
            timeout=self._config.timeout,
            max_retries=self._config.max_retries,
            sleep=self._sleep,
        )

        try:
            data = json.loads(response.body)
        except json.JSONDecodeError as exc:
            raise ZohoAuthError(
                f"Token endpoint {url} vrátil odpoveď, ktorá nie je JSON "
                f"(HTTP {response.status})."
            ) from exc

        if not isinstance(data, dict):
            raise ZohoAuthError(f"Token endpoint {url} vrátil neočakávaný JSON.")

        if "error" in data:
            raise ZohoAuthError(_explain_token_error(str(data["error"]), self._config))

        token = data.get("access_token")
        if not token:
            raise ZohoAuthError(
                f"Token endpoint nevrátil access_token (HTTP {response.status}): {data}"
            )

        try:
            expires_in = int(data.get("expires_in", 3600))
        except (TypeError, ValueError):
            expires_in = 3600
        return str(token), expires_in


def _explain_token_error(error: str, config: Config) -> str:
    hints = {
        "invalid_client": (
            "Zoho neuznalo ZOHO_CLIENT_ID / ZOHO_CLIENT_SECRET. Skontroluj, či sú "
            "z tej istej aplikácie a z toho istého dátového centra."
        ),
        "invalid_code": (
            "Refresh token je neplatný alebo bol zrušený. Vygeneruj nový cez "
            "scripts/get_refresh_token.py."
        ),
        "invalid_grant": (
            "Refresh token neplatí. Býva to tým, že bol vydaný v inom dátovom "
            f"centre, než je nastavené ZOHO_DC={config.data_center}."
        ),
    }
    hint = hints.get(error, "")
    base = f"OAuth chyba od Zoho: {error}."
    return f"{base} {hint}".strip()
