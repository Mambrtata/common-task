"""Spoločné pomôcky – najmä falošný transport, aby testy nešli na sieť."""

from __future__ import annotations

import json
import urllib.parse
from typing import Any

import pytest

from zoho_mail_mcp.config import Config
from zoho_mail_mcp.transport import HttpResponse

BASE_ENV = {
    "ZOHO_CLIENT_ID": "cid",
    "ZOHO_CLIENT_SECRET": "secret",
    "ZOHO_REFRESH_TOKEN": "rt",
    "ZOHO_DC": "eu",
}


def zoho_ok(data: Any) -> str:
    return json.dumps({"status": {"code": 200, "description": "success"}, "data": data})


def zoho_error(code: str, description: str = "failure") -> str:
    return json.dumps(
        {"status": {"code": 400, "description": description}, "data": {"errorCode": code}}
    )


class FakeTransport:
    """Odpovedá podľa cesty v URL a zapisuje si, čo dostal."""

    def __init__(self, routes: dict[str, Any] | None = None) -> None:
        # routes: kľúč je cesta bez query; hodnota je HttpResponse, reťazec
        # alebo zoznam odpovedí za sebou (na testovanie opakovaní).
        self.routes = routes or {}
        self.calls: list[dict[str, Any]] = []
        self.token_response = json.dumps({"access_token": "at-1", "expires_in": 3600})

    def __call__(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        body: bytes | None = None,
        timeout: int = 30,
    ) -> HttpResponse:
        parsed = urllib.parse.urlparse(url)
        self.calls.append(
            {
                "method": method,
                "path": parsed.path,
                "query": dict(urllib.parse.parse_qsl(parsed.query)),
                "headers": dict(headers or {}),
                "body": body.decode() if body else None,
                "url": url,
            }
        )

        if parsed.path.endswith("/oauth/v2/token"):
            return _as_response(self.token_response)

        route = self.routes.get(parsed.path)
        if route is None:
            return HttpResponse(status=404, body=zoho_error("URL_RULE_NOT_CONFIGURED"))
        if isinstance(route, list):
            route = route.pop(0) if len(route) > 1 else route[0]
        return _as_response(route)

    def paths(self) -> list[str]:
        return [call["path"] for call in self.calls]


def _as_response(value: Any) -> HttpResponse:
    if isinstance(value, HttpResponse):
        return value
    return HttpResponse(status=200, body=value)


@pytest.fixture
def config() -> Config:
    return Config.from_env(BASE_ENV)


@pytest.fixture
def transport() -> FakeTransport:
    return FakeTransport()


@pytest.fixture
def no_sleep():
    """Namiesto čakania si len zapíše, ako dlho by sa bolo spalo."""
    delays: list[float] = []
    return delays.append, delays
