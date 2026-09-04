"""Tenká HTTP vrstva nad urllib, aby sa dala v testoch vymeniť."""

from __future__ import annotations

import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

# Stavy, pri ktorých má zmysel skúsiť to znova: throttling a dočasné výpadky.
RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: Mapping[str, str] = field(default_factory=dict)
    body: str = ""
    # Prílohy sú binárne, dekódovaním na text by sa poškodili.
    content: bytes = b""

    def header(self, name: str) -> str | None:
        for key, value in self.headers.items():
            if key.lower() == name.lower():
                return value
        return None


Transport = Callable[..., HttpResponse]


def urlopen_transport(
    method: str,
    url: str,
    headers: Mapping[str, str] | None = None,
    body: bytes | None = None,
    timeout: int = 30,
) -> HttpResponse:
    """Vykoná požiadavku. Chyby 4xx/5xx vracia ako odpoveď, nie ako výnimku."""
    request = urllib.request.Request(url, data=body, method=method)
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            return HttpResponse(
                status=response.status,
                headers=dict(response.headers.items()),
                body=raw.decode("utf-8", errors="replace"),
                content=raw,
            )
    except urllib.error.HTTPError as exc:  # Zoho posiela detaily chyby v tele
        raw = exc.read()
        return HttpResponse(
            status=exc.code,
            headers=dict(exc.headers.items()) if exc.headers else {},
            body=raw.decode("utf-8", errors="replace"),
            content=raw,
        )


def request_with_retries(
    transport: Transport,
    method: str,
    url: str,
    *,
    headers: Mapping[str, str] | None = None,
    body: bytes | None = None,
    timeout: int = 30,
    max_retries: int = 3,
    sleep: Callable[[float], None] = time.sleep,
) -> HttpResponse:
    """Opakuje požiadavku pri throttlingu a 5xx, s exponenciálnym čakaním."""
    attempt = 0
    while True:
        response = transport(method, url, headers=headers, body=body, timeout=timeout)
        if response.status not in RETRYABLE_STATUSES or attempt >= max_retries:
            return response

        delay = 2.0**attempt
        retry_after = response.header("Retry-After")
        if retry_after:
            try:
                delay = max(delay, float(retry_after))
            except ValueError:
                pass  # Retry-After ako HTTP dátum – držíme sa vlastného backoffu
        sleep(delay)
        attempt += 1
