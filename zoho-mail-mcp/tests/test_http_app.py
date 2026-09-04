"""Testy sieťového režimu: bez tokenu sa k pošte nikto nedostane."""

import json

import pytest
from starlette.testclient import TestClient

from zoho_mail_mcp.errors import ConfigError
from zoho_mail_mcp.http_app import build_app, default_allowed_hosts
from zoho_mail_mcp.server import mcp

TOKEN = "u" * 32
HOST = "10.147.17.5"
PORT = 8765

INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "1"},
    },
}

MCP_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
    "Host": f"{HOST}:{PORT}",
}


@pytest.fixture
def client():
    app = build_app(mcp, token=TOKEN, host=HOST, port=PORT)
    with TestClient(app, base_url=f"http://{HOST}:{PORT}") as test_client:
        yield test_client


def test_health_needs_no_token(client):
    response = client.get("/health", headers={"Host": f"{HOST}:{PORT}"})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_mcp_without_token_is_rejected(client):
    response = client.post("/mcp", json=INITIALIZE, headers=MCP_HEADERS)
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_mcp_with_wrong_token_is_rejected(client):
    headers = {**MCP_HEADERS, "Authorization": f"Bearer {'x' * 32}"}
    response = client.post("/mcp", json=INITIALIZE, headers=headers)
    assert response.status_code == 401


def test_wrong_auth_scheme_is_rejected(client):
    headers = {**MCP_HEADERS, "Authorization": f"Basic {TOKEN}"}
    response = client.post("/mcp", json=INITIALIZE, headers=headers)
    assert response.status_code == 401


def test_almost_correct_token_is_rejected(client):
    headers = {**MCP_HEADERS, "Authorization": f"Bearer {TOKEN[:-1]}"}
    response = client.post("/mcp", json=INITIALIZE, headers=headers)
    assert response.status_code == 401


def test_valid_token_reaches_the_mcp_server(client):
    headers = {**MCP_HEADERS, "Authorization": f"Bearer {TOKEN}"}
    response = client.post("/mcp", json=INITIALIZE, headers=headers)
    assert response.status_code == 200

    payload = _first_json_message(response)
    assert payload["result"]["serverInfo"]["name"] == "zoho-mail"


def test_tools_are_listed_over_http(client):
    headers = {**MCP_HEADERS, "Authorization": f"Bearer {TOKEN}"}
    client.post("/mcp", json=INITIALIZE, headers=headers)
    listing = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
    response = client.post("/mcp", json=listing, headers=headers)
    assert response.status_code == 200

    payload = _first_json_message(response)
    names = {tool["name"] for tool in payload["result"]["tools"]}
    assert "zoho_list_messages" in names
    assert len(names) == 9


def test_foreign_host_header_is_refused(client):
    headers = {
        **MCP_HEADERS,
        "Authorization": f"Bearer {TOKEN}",
        "Host": "utocnik.example.com",
    }
    response = client.post("/mcp", json=INITIALIZE, headers=headers)
    assert response.status_code != 200


@pytest.mark.parametrize(
    "value",
    [
        "Bearer heslo pre používateľa jan: " + TOKEN,  # výzva sudo v hlavičke
        "Bearer tokén-s-diakritikou-dlhý-dosť",
        "Bearer " + "\U0001f600" * 10,
    ],
)
def test_non_ascii_header_is_rejected_not_crashed(client, value):
    """Čokoľvek mimo ASCII musí skončiť na 401, nie na chybe servera.

    Hlavička ide ako bajty – presne tak ju posiela curl. Ako reťazec by ju
    testovací klient odmietol už pri odosielaní a chybu by sme neodhalili.
    """
    headers = {**MCP_HEADERS, "Authorization": value.encode("utf-8")}
    response = client.post("/mcp", json=INITIALIZE, headers=headers)
    assert response.status_code == 401


def test_short_token_is_refused_at_startup():
    with pytest.raises(ConfigError, match="aspoň 24 znakov"):
        build_app(mcp, token="kratky", host=HOST, port=PORT)


def test_empty_token_is_refused_at_startup():
    with pytest.raises(ConfigError):
        build_app(mcp, token="", host=HOST, port=PORT)


def test_allowed_hosts_include_the_bind_address():
    hosts = default_allowed_hosts("10.147.17.5", 8765)
    assert "10.147.17.5:8765" in hosts
    assert "10.147.17.5:*" in hosts


def test_wildcard_bind_cannot_derive_its_address():
    # Pri 0.0.0.0 nevieme, akú adresu klient použije – musí sa doplniť ručne.
    assert default_allowed_hosts("0.0.0.0", 8765) == [
        "localhost",
        "localhost:*",
        "127.0.0.1",
        "127.0.0.1:*",
    ]


def _first_json_message(response):
    """Odpoveď chodí ako SSE stream aj ako čisté JSON – zvládni oboje."""
    if response.headers.get("content-type", "").startswith("text/event-stream"):
        for line in response.text.splitlines():
            if line.startswith("data:"):
                return json.loads(line[len("data:"):].strip())
        raise AssertionError(f"V streame nie sú dáta: {response.text!r}")
    return response.json()


@pytest.fixture
def files_client(tmp_path, monkeypatch):
    """Aplikácia s priečinkom príloh nasmerovaným do dočasného adresára."""
    downloads = tmp_path / "prilohy"
    downloads.mkdir()
    (downloads / "faktura.pdf").write_bytes(b"%PDF-1.4 test")
    (tmp_path / "tajomstvo.txt").write_bytes(b"toto sa von dostat nesmie")

    monkeypatch.setenv("ZOHO_DOWNLOAD_DIR", str(downloads))
    app = build_app(mcp, token=TOKEN, host=HOST, port=PORT)
    with TestClient(app, base_url=f"http://{HOST}:{PORT}") as client:
        yield client


AUTH = {"Host": f"{HOST}:{PORT}", "Authorization": f"Bearer {TOKEN}"}


def test_attachment_download_needs_a_token(files_client):
    response = files_client.get("/files/faktura.pdf", headers={"Host": f"{HOST}:{PORT}"})
    assert response.status_code == 401


def test_attachment_is_served_with_a_token(files_client):
    response = files_client.get("/files/faktura.pdf", headers=AUTH)
    assert response.status_code == 200
    assert response.content == b"%PDF-1.4 test"


def test_missing_attachment_gives_404(files_client):
    response = files_client.get("/files/neexistuje.pdf", headers=AUTH)
    assert response.status_code == 404


@pytest.mark.parametrize(
    "name",
    ["../tajomstvo.txt", "..%2Ftajomstvo.txt", "subdir/../../tajomstvo.txt"],
)
def test_path_traversal_is_refused(files_client, name):
    response = files_client.get(f"/files/{name}", headers=AUTH)
    assert response.status_code in (400, 404)
    assert b"toto sa von dostat nesmie" not in response.content
