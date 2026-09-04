"""Chybové typy konektora."""

from __future__ import annotations


class ZohoMailMCPError(Exception):
    """Spoločný predok všetkých chýb konektora."""


class ConfigError(ZohoMailMCPError):
    """Chýbajúca alebo nezmyselná konfigurácia v prostredí."""


class ReadOnlyViolation(ZohoMailMCPError):
    """Pokus o zápisovú operáciu. Konektor je zámerne len na čítanie."""


class ZohoAuthError(ZohoMailMCPError):
    """Nepodarilo sa získať alebo použiť access token."""


class ZohoApiError(ZohoMailMCPError):
    """Zoho Mail API vrátilo chybu."""

    def __init__(
        self,
        message: str,
        *,
        http_status: int | None = None,
        error_code: str | None = None,
        url: str | None = None,
    ) -> None:
        super().__init__(message)
        self.http_status = http_status
        self.error_code = error_code
        self.url = url
