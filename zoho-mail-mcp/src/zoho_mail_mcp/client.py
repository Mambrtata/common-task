"""Klient nad Zoho Mail REST API. Zámerne vie iba čítať."""

from __future__ import annotations

import json
import time
import urllib.parse
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import Any

from .config import Config
from .errors import ReadOnlyViolation, ZohoApiError, ZohoAuthError
from .oauth import TokenProvider
from .transport import Transport, request_with_retries, urlopen_transport

# Ako dlho držíme zoznam účtov v pamäti – mení sa raz za uhorkovú sezónu.
ACCOUNTS_CACHE_SECONDS = 300

# Chybové kódy, po ktorých má zmysel zahodiť access token a skúsiť to raz znova.
_TOKEN_ERROR_CODES = frozenset({"INVALID_OAUTHTOKEN", "OAUTH_TOKEN_EXPIRED"})


class ZohoMailClient:
    """Obaľuje Zoho Mail API. Každá metóda je GET – zápis vôbec neumožňuje."""

    def __init__(
        self,
        config: Config,
        *,
        token_provider: TokenProvider | None = None,
        transport: Transport = urlopen_transport,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._config = config
        self._tokens = token_provider or TokenProvider(
            config, transport=transport, sleep=sleep
        )
        self._transport = transport
        self._clock = clock
        self._sleep = sleep
        self._accounts_cache: list[dict[str, Any]] | None = None
        self._accounts_cached_at = 0.0

    # ---------------------------------------------------------------- HTTP

    def _fetch(self, method: str, path: str, params: Mapping[str, Any] | None = None):
        """Spoločná časť: zostaví URL, pošle GET a raz zopakuje pri starom tokene."""
        if method != "GET":
            raise ReadOnlyViolation(
                f"Konektor je len na čítanie, {method} {path} sa nevykoná."
            )

        url = f"{self._config.api_base}{path}{_encode_params(params)}"
        response = self._send(url)

        # Token mohol medzitým vypršať alebo byť zrušený – jeden pokus s novým.
        if response.status in (401, 403) or _error_code_of(response) in _TOKEN_ERROR_CODES:
            self._tokens.invalidate()
            response = self._send(url)

        return url, response

    def _request(self, method: str, path: str, params: Mapping[str, Any] | None = None) -> Any:
        url, response = self._fetch(method, path, params)
        payload = _parse_json(response.body, url, response.status)
        _raise_for_error(payload, url, response.status, _error_code(payload))
        return payload.get("data") if isinstance(payload, dict) else payload

    def _request_bytes(self, path: str, params: Mapping[str, Any] | None = None) -> bytes:
        """Ako _request, ale vráti surové bajty – pre prílohy."""
        url, response = self._fetch("GET", path, params)

        # Pri chybe Zoho pošle JSON aj tam, kde inak posiela súbor.
        if response.status >= 400 or _looks_like_json(response):
            payload = _parse_json(response.body, url, response.status)
            _raise_for_error(payload, url, response.status, _error_code(payload))

        return response.content

    def _send(self, url: str):
        token = self._tokens.get_access_token()
        return request_with_retries(
            self._transport,
            "GET",
            url,
            headers={
                "Authorization": f"Zoho-oauthtoken {token}",
                "Accept": "application/json",
            },
            timeout=self._config.timeout,
            max_retries=self._config.max_retries,
            sleep=self._sleep,
        )

    # ------------------------------------------------------------ účty

    def list_accounts(self, *, refresh: bool = False) -> list[dict[str, Any]]:
        fresh_enough = (
            self._accounts_cache is not None
            and self._clock() - self._accounts_cached_at < ACCOUNTS_CACHE_SECONDS
        )
        if not refresh and fresh_enough:
            return self._accounts_cache  # type: ignore[return-value]

        data = self._request("GET", "/api/accounts")
        accounts = data if isinstance(data, list) else [data] if data else []
        allowed = [
            account
            for account in accounts
            if self._config.account_allowed(_primary_email(account))
        ]
        self._accounts_cache = allowed
        self._accounts_cached_at = self._clock()
        return allowed

    def resolve_account_id(self, account: str | None = None) -> str:
        """Prijme accountId aj e-mailovú adresu; bez argumentu vezme jediný účet."""
        accounts = self.list_accounts()
        if not accounts:
            raise ZohoApiError(
                "Token nevidí žiadny účet. Skontroluj scope ZohoMail.accounts.READ "
                "a prípadný whitelist v ZOHO_ALLOWED_ACCOUNTS."
            )

        if account is None:
            if len(accounts) > 1:
                emails = ", ".join(sorted(filter(None, map(_primary_email, accounts))))
                raise ZohoApiError(
                    f"Token vidí viac účtov ({emails}); uveď, ktorý chceš, "
                    "parametrom 'account'."
                )
            return str(accounts[0].get("accountId"))

        needle = account.strip().lower()
        for candidate in accounts:
            account_id = str(candidate.get("accountId", ""))
            if needle == account_id.lower():
                return account_id
            if needle == (_primary_email(candidate) or "").lower():
                return account_id
            aliases = candidate.get("emailAddress")
            if isinstance(aliases, list):
                for alias in aliases:
                    if isinstance(alias, dict) and needle == str(
                        alias.get("mailId", "")
                    ).lower():
                        return account_id

        known = ", ".join(sorted(filter(None, map(_primary_email, accounts)))) or "žiadny"
        raise ZohoApiError(f"Účet {account!r} som nenašiel. Dostupné účty: {known}.")

    # -------------------------------------------------------- priečinky

    def list_folders(self, account_id: str) -> list[dict[str, Any]]:
        data = self._request("GET", f"/api/accounts/{account_id}/folders")
        return data if isinstance(data, list) else []

    # ------------------------------------------------------------ správy

    def list_messages(self, account_id: str, **params: Any) -> list[dict[str, Any]]:
        data = self._request("GET", f"/api/accounts/{account_id}/messages/view", params)
        return data if isinstance(data, list) else []

    def search_messages(
        self, account_id: str, search_key: str, **params: Any
    ) -> list[dict[str, Any]]:
        data = self._request(
            "GET",
            f"/api/accounts/{account_id}/messages/search",
            {"searchKey": search_key, **params},
        )
        return data if isinstance(data, list) else []

    def get_message_details(
        self, account_id: str, folder_id: str, message_id: str
    ) -> dict[str, Any]:
        data = self._request(
            "GET",
            f"/api/accounts/{account_id}/folders/{folder_id}/messages/{message_id}/details",
        )
        return data if isinstance(data, dict) else {}

    def get_message_content(
        self,
        account_id: str,
        folder_id: str,
        message_id: str,
        *,
        include_block_content: bool = True,
    ) -> dict[str, Any]:
        data = self._request(
            "GET",
            f"/api/accounts/{account_id}/folders/{folder_id}/messages/{message_id}/content",
            {"includeBlockContent": "true" if include_block_content else "false"},
        )
        return data if isinstance(data, dict) else {}

    def get_message_header(
        self, account_id: str, folder_id: str, message_id: str
    ) -> dict[str, Any]:
        data = self._request(
            "GET",
            f"/api/accounts/{account_id}/folders/{folder_id}/messages/{message_id}/header",
        )
        return data if isinstance(data, dict) else {}

    def get_attachment_info(
        self, account_id: str, folder_id: str, message_id: str
    ) -> list[dict[str, Any]]:
        data = self._request(
            "GET",
            f"/api/accounts/{account_id}/folders/{folder_id}"
            f"/messages/{message_id}/attachmentinfo",
        )
        if isinstance(data, dict):
            attachments = data.get("attachments")
            return attachments if isinstance(attachments, list) else [data]
        return data if isinstance(data, list) else []

    def get_attachment_content(
        self, account_id: str, folder_id: str, message_id: str, attachment_id: str
    ) -> bytes:
        return self._request_bytes(
            f"/api/accounts/{account_id}/folders/{folder_id}"
            f"/messages/{message_id}/attachments/{attachment_id}"
        )

    def list_thread_messages(
        self, account_id: str, thread_id: str, **params: Any
    ) -> list[dict[str, Any]]:
        return self.list_messages(account_id, threadId=thread_id, **params)


# ------------------------------------------------------------- pomocníci


def _encode_params(params: Mapping[str, Any] | None) -> str:
    if not params:
        return ""
    pairs = [(key, value) for key, value in params.items() if value is not None]
    if not pairs:
        return ""
    return "?" + urllib.parse.urlencode(
        [(key, _stringify(value)) for key, value in pairs]
    )


def _stringify(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _parse_json(body: str, url: str, http_status: int) -> Any:
    if not body.strip():
        return {}
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise ZohoApiError(
            f"Odpoveď z {url} nie je JSON (HTTP {http_status}).",
            http_status=http_status,
            url=url,
        ) from exc


def _looks_like_json(response: Any) -> bool:
    """Rozlíši chybovú JSON odpoveď od skutočného súboru."""
    content_type = ""
    for key, value in (response.headers or {}).items():
        if key.lower() == "content-type":
            content_type = value.lower()
            break
    if "json" in content_type:
        return True
    # Bez hlavičky sa pozrieme na začiatok tela; súbory sa takto nezačínajú.
    head = response.content[:1].lstrip() if response.content else b""
    return head[:1] == b"{" and b'"status"' in response.content[:200]


def _error_code_of(response: Any) -> str | None:
    """Vytiahne errorCode z odpovede, ak je to vôbec JSON."""
    try:
        return _error_code(json.loads(response.body))
    except (json.JSONDecodeError, TypeError):
        return None


def _error_code(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    data = payload.get("data")
    if isinstance(data, dict) and data.get("errorCode"):
        return str(data["errorCode"])
    if payload.get("errorCode"):
        return str(payload["errorCode"])
    return None


def _raise_for_error(
    payload: Any, url: str, http_status: int, error_code: str | None
) -> None:
    status_block = payload.get("status") if isinstance(payload, dict) else None
    api_status = None
    description = None
    if isinstance(status_block, dict):
        api_status = status_block.get("code")
        description = status_block.get("description")

    failed = http_status >= 400 or error_code is not None
    if isinstance(api_status, int) and api_status >= 400:
        failed = True
    if not failed:
        return

    if error_code in _TOKEN_ERROR_CODES or http_status in (401, 403):
        raise ZohoAuthError(
            f"Zoho odmietlo token ({error_code or http_status}). Overiť: či ZOHO_DC "
            f"({url.split('/')[2]}) sedí s dátovým centrom účtu a či má aplikácia "
            "scopes ZohoMail.accounts.READ, ZohoMail.folders.READ, "
            "ZohoMail.messages.READ."
        )

    detail = description or _describe(payload)
    raise ZohoApiError(
        f"Zoho Mail API vrátilo chybu pri {url}: {detail}"
        + (f" (errorCode {error_code})" if error_code else ""),
        http_status=http_status,
        error_code=error_code,
        url=url,
    )


def _describe(payload: Any) -> str:
    text = json.dumps(payload, ensure_ascii=False)
    return text if len(text) <= 400 else text[:400] + "…"


def _primary_email(account: Mapping[str, Any]) -> str | None:
    primary = account.get("primaryEmailAddress")
    if primary:
        return str(primary)
    addresses = account.get("emailAddress")
    if isinstance(addresses, list):
        for entry in addresses:
            if isinstance(entry, dict) and entry.get("isPrimary") and entry.get("mailId"):
                return str(entry["mailId"])
        for entry in addresses:
            if isinstance(entry, dict) and entry.get("mailId"):
                return str(entry["mailId"])
    return None


def epoch_ms_to_iso(value: Any) -> str | None:
    """Zoho vracia časy ako epoch v milisekundách (a občas ako reťazec)."""
    if value in (None, "", 0, "0"):
        return None
    try:
        millis = int(value)
    except (TypeError, ValueError):
        return None
    try:
        return datetime.fromtimestamp(millis / 1000, tz=timezone.utc).isoformat()
    except (OverflowError, OSError, ValueError):
        return None
