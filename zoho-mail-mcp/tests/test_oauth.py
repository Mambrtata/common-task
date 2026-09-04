import json

import pytest

from zoho_mail_mcp.errors import ZohoAuthError
from zoho_mail_mcp.oauth import TokenProvider
from zoho_mail_mcp.transport import HttpResponse


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_token_is_fetched_once_and_reused(config, transport):
    provider = TokenProvider(config, transport=transport, clock=Clock())
    assert provider.get_access_token() == "at-1"
    assert provider.get_access_token() == "at-1"
    assert len(transport.calls) == 1


def test_token_is_refreshed_after_expiry(config, transport):
    clock = Clock()
    provider = TokenProvider(config, transport=transport, clock=clock)
    provider.get_access_token()

    transport.token_response = json.dumps({"access_token": "at-2", "expires_in": 3600})
    clock.now = 3600  # token medzitým vypršal
    assert provider.get_access_token() == "at-2"
    assert len(transport.calls) == 2


def test_invalidate_forces_new_token(config, transport):
    provider = TokenProvider(config, transport=transport, clock=Clock())
    provider.get_access_token()
    provider.invalidate()
    transport.token_response = json.dumps({"access_token": "at-3", "expires_in": 3600})
    assert provider.get_access_token() == "at-3"


def test_refresh_sends_exactly_what_zoho_documents(config, transport):
    TokenProvider(config, transport=transport).get_access_token()
    body = transport.calls[0]["body"]
    assert "grant_type=refresh_token" in body
    assert "refresh_token=rt" in body
    assert "client_id=cid" in body
    assert "client_secret=secret" in body
    # Scope pri obnove Zoho nedokumentuje a jeho posielanie vracia general_error.
    assert "scope" not in body


def test_refresh_goes_to_the_configured_data_center(config, transport):
    TokenProvider(config, transport=transport).get_access_token()
    assert transport.calls[0]["url"].startswith("https://accounts.zoho.eu/oauth/v2/token")


def test_invalid_grant_mentions_data_center(config, transport):
    transport.token_response = json.dumps({"error": "invalid_grant"})
    provider = TokenProvider(config, transport=transport)
    with pytest.raises(ZohoAuthError, match="dátovom centre"):
        provider.get_access_token()


def test_general_error_hints_at_placeholder_values(config, transport):
    transport.token_response = json.dumps({"error": "general_error"})
    with pytest.raises(ZohoAuthError, match="zástupného textu"):
        TokenProvider(config, transport=transport).get_access_token()


def test_invalid_client_is_explained(config, transport):
    transport.token_response = json.dumps({"error": "invalid_client"})
    with pytest.raises(ZohoAuthError, match="ZOHO_CLIENT_ID"):
        TokenProvider(config, transport=transport).get_access_token()


def test_non_json_token_response_is_reported(config, transport, no_sleep):
    sleep, delays = no_sleep
    transport.token_response = HttpResponse(status=502, body="<html>bad gateway</html>")
    with pytest.raises(ZohoAuthError, match="nie je JSON"):
        TokenProvider(config, transport=transport, sleep=sleep).get_access_token()
    # 502 je dočasná chyba, takže sa to malo skúsiť znova (3 pokusy navyše).
    assert delays == [1.0, 2.0, 4.0]


def test_missing_access_token_is_reported(config, transport):
    transport.token_response = json.dumps({"expires_in": 3600})
    with pytest.raises(ZohoAuthError, match="access_token"):
        TokenProvider(config, transport=transport).get_access_token()
