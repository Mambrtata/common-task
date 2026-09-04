"""Konfigurácia konektora, načítaná z premenných prostredia."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from .errors import ConfigError

# Zoho prevádzkuje viacero dátových centier. Refresh token vydaný v jednom DC
# v inom nefunguje a prejaví sa to ako INVALID_OAUTHTOKEN, preto sa DC volí
# vždy explicitne a nehádame ho.
DATA_CENTERS: dict[str, tuple[str, str]] = {
    "us": ("https://mail.zoho.com", "https://accounts.zoho.com"),
    "eu": ("https://mail.zoho.eu", "https://accounts.zoho.eu"),
    "in": ("https://mail.zoho.in", "https://accounts.zoho.in"),
    "au": ("https://mail.zoho.com.au", "https://accounts.zoho.com.au"),
    "jp": ("https://mail.zoho.jp", "https://accounts.zoho.jp"),
    "ca": ("https://mail.zohocloud.ca", "https://accounts.zohocloud.ca"),
    "sa": ("https://mail.zoho.sa", "https://accounts.zoho.sa"),
    "uk": ("https://mail.zoho.uk", "https://accounts.zoho.uk"),
    "ae": ("https://mail.zoho.ae", "https://accounts.zoho.ae"),
    "cn": ("https://mail.zoho.com.cn", "https://accounts.zoho.com.cn"),
}

# Konektor pýta výhradne READ scopes. Aj keby aplikácia v Zoho konzole mala
# povolené viac, token vydaný s týmto zoznamom nič zapísať nedokáže.
READ_ONLY_SCOPES: tuple[str, ...] = (
    "ZohoMail.accounts.READ",
    "ZohoMail.folders.READ",
    "ZohoMail.messages.READ",
)

SCOPE_STRING = ",".join(READ_ONLY_SCOPES)

# Kam sa ukladajú stiahnuté prílohy. Systemd unit tento priečinok vytvára
# cez StateDirectory, takže je zapisovateľný aj pri ProtectSystem=strict.
DEFAULT_DOWNLOAD_DIR = Path("/var/lib/zoho-mail-mcp/attachments")


def _get(env: Mapping[str, str], name: str, default: str | None = None) -> str | None:
    value = env.get(name)
    if value is None:
        return default
    value = value.strip()
    return value or default


def _get_int(env: Mapping[str, str], name: str, default: int, *, minimum: int = 1) -> int:
    raw = _get(env, name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} musí byť celé číslo, dostal som {raw!r}.") from exc
    if value < minimum:
        raise ConfigError(f"{name} musí byť aspoň {minimum}, dostal som {value}.")
    return value


@dataclass(frozen=True)
class Config:
    """Všetko, čo konektor potrebuje vedieť pri štarte."""

    client_id: str
    client_secret: str
    refresh_token: str
    data_center: str
    api_base: str
    accounts_base: str
    allowed_accounts: frozenset[str] = field(default_factory=frozenset)
    timeout: int = 30
    max_retries: int = 3
    max_content_chars: int = 20_000
    download_dir: Path = DEFAULT_DOWNLOAD_DIR
    max_attachment_bytes: int = 25 * 1024 * 1024

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Config:
        env = os.environ if env is None else env

        missing = [
            name
            for name in ("ZOHO_CLIENT_ID", "ZOHO_CLIENT_SECRET", "ZOHO_REFRESH_TOKEN")
            if not _get(env, name)
        ]
        if missing:
            raise ConfigError(
                "Chýbajú premenné prostredia: "
                + ", ".join(missing)
                + ". Pozri README, časť „Nastavenie“."
            )

        dc = (_get(env, "ZOHO_DC") or "").lower()
        if not dc:
            raise ConfigError(
                "Chýba ZOHO_DC – dátové centrum, v ktorom máš Zoho účet. "
                "Možnosti: " + ", ".join(sorted(DATA_CENTERS)) + ". "
                "Pre schránky na onoff.sk je to takmer isto 'eu'."
            )
        if dc not in DATA_CENTERS:
            raise ConfigError(
                f"Neznáme ZOHO_DC {dc!r}. Možnosti: " + ", ".join(sorted(DATA_CENTERS)) + "."
            )

        default_api, default_accounts = DATA_CENTERS[dc]
        allowed_raw = _get(env, "ZOHO_ALLOWED_ACCOUNTS") or ""
        allowed = frozenset(
            part.strip().lower() for part in allowed_raw.split(",") if part.strip()
        )

        return cls(
            client_id=_get(env, "ZOHO_CLIENT_ID") or "",
            client_secret=_get(env, "ZOHO_CLIENT_SECRET") or "",
            refresh_token=_get(env, "ZOHO_REFRESH_TOKEN") or "",
            data_center=dc,
            api_base=(_get(env, "ZOHO_API_BASE") or default_api).rstrip("/"),
            accounts_base=(_get(env, "ZOHO_ACCOUNTS_BASE") or default_accounts).rstrip("/"),
            allowed_accounts=allowed,
            timeout=_get_int(env, "ZOHO_TIMEOUT", 30),
            max_retries=_get_int(env, "ZOHO_MAX_RETRIES", 3, minimum=0),
            max_content_chars=_get_int(env, "ZOHO_MAX_CONTENT_CHARS", 20_000, minimum=500),
            download_dir=download_dir_from_env(env),
            max_attachment_bytes=_get_int(
                env, "ZOHO_MAX_ATTACHMENT_BYTES", 25 * 1024 * 1024, minimum=1024
            ),
        )

    def account_allowed(self, email: str | None) -> bool:
        """Prázdny whitelist znamená „bez obmedzenia“."""
        if not self.allowed_accounts:
            return True
        return bool(email) and email.lower() in self.allowed_accounts


def download_dir_from_env(env: Mapping[str, str] | None = None) -> Path:
    """Priečinok na prílohy. Potrebuje ho aj HTTP vrstva, ktorá Config nemá."""
    env = os.environ if env is None else env
    return Path(_get(env, "ZOHO_DOWNLOAD_DIR") or str(DEFAULT_DOWNLOAD_DIR))
