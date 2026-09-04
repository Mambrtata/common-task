
import pytest
from conftest import BASE_ENV, FakeTransport, zoho_error, zoho_ok

from zoho_mail_mcp.client import ZohoMailClient, epoch_ms_to_iso
from zoho_mail_mcp.config import Config
from zoho_mail_mcp.errors import ReadOnlyViolation, ZohoApiError, ZohoAuthError
from zoho_mail_mcp.transport import HttpResponse

ACCOUNTS = [
    {
        "accountId": "111",
        "accountName": "Jan",
        "primaryEmailAddress": "jan@onoff.sk",
        "emailAddress": [{"mailId": "jan@onoff.sk", "isPrimary": True}],
    },
    {
        "accountId": "222",
        "accountName": "Info",
        "primaryEmailAddress": "info@onoff.sk",
        "emailAddress": [{"mailId": "info@onoff.sk", "isPrimary": True}],
    },
]


def make_client(routes, config=None, sleep=lambda _: None):
    transport = FakeTransport(routes)
    client = ZohoMailClient(
        config or Config.from_env(BASE_ENV), transport=transport, sleep=sleep
    )
    return client, transport


def test_writes_are_refused_outright(config, transport):
    client = ZohoMailClient(config, transport=transport)
    with pytest.raises(ReadOnlyViolation, match="len na čítanie"):
        client._request("POST", "/api/accounts/111/messages")
    with pytest.raises(ReadOnlyViolation):
        client._request("DELETE", "/api/accounts/111/folders/1/messages/2")


def test_every_api_call_is_a_get():
    routes = {
        "/api/accounts": zoho_ok(ACCOUNTS),
        "/api/accounts/111/folders": zoho_ok([{"folderId": "9", "folderName": "Inbox"}]),
        "/api/accounts/111/messages/view": zoho_ok([]),
    }
    client, transport = make_client(routes)
    client.list_folders("111")
    client.list_messages("111")
    api_calls = [c for c in transport.calls if "/oauth/" not in c["path"]]
    assert api_calls, "žiadne volanie sa neuskutočnilo"
    assert {c["method"] for c in api_calls} == {"GET"}


def test_bearer_header_uses_zoho_prefix():
    client, transport = make_client({"/api/accounts": zoho_ok(ACCOUNTS)})
    client.list_accounts()
    api_call = next(c for c in transport.calls if c["path"] == "/api/accounts")
    assert api_call["headers"]["Authorization"] == "Zoho-oauthtoken at-1"


def test_resolve_account_by_email_and_by_id():
    client, _ = make_client({"/api/accounts": zoho_ok(ACCOUNTS)})
    assert client.resolve_account_id("info@onoff.sk") == "222"
    assert client.resolve_account_id("INFO@ONOFF.SK") == "222"
    assert client.resolve_account_id("111") == "111"


def test_resolve_account_requires_choice_when_several_exist():
    client, _ = make_client({"/api/accounts": zoho_ok(ACCOUNTS)})
    with pytest.raises(ZohoApiError, match="viac účtov"):
        client.resolve_account_id(None)


def test_single_account_needs_no_argument():
    client, _ = make_client({"/api/accounts": zoho_ok(ACCOUNTS[:1])})
    assert client.resolve_account_id(None) == "111"


def test_unknown_account_lists_the_known_ones():
    client, _ = make_client({"/api/accounts": zoho_ok(ACCOUNTS)})
    with pytest.raises(ZohoApiError, match="jan@onoff.sk"):
        client.resolve_account_id("kto@inde.sk")


def test_whitelist_hides_other_mailboxes():
    config = Config.from_env({**BASE_ENV, "ZOHO_ALLOWED_ACCOUNTS": "info@onoff.sk"})
    client, _ = make_client({"/api/accounts": zoho_ok(ACCOUNTS)}, config=config)
    assert [a["accountId"] for a in client.list_accounts()] == ["222"]
    with pytest.raises(ZohoApiError):
        client.resolve_account_id("jan@onoff.sk")


def test_accounts_are_cached():
    client, transport = make_client({"/api/accounts": zoho_ok(ACCOUNTS)})
    client.list_accounts()
    client.list_accounts()
    assert transport.paths().count("/api/accounts") == 1


def test_refresh_bypasses_the_cache():
    client, transport = make_client({"/api/accounts": zoho_ok(ACCOUNTS)})
    client.list_accounts()
    client.list_accounts(refresh=True)
    assert transport.paths().count("/api/accounts") == 2


def test_none_parameters_are_dropped_from_the_query():
    routes = {"/api/accounts/111/messages/view": zoho_ok([])}
    client, transport = make_client(routes)
    client.list_messages("111", folderId=None, status="unread", limit=10, includeto=True)
    query = transport.calls[-1]["query"]
    assert "folderId" not in query
    assert query["status"] == "unread"
    assert query["includeto"] == "true"  # bool sa posiela ako true/false


def test_search_key_is_passed_through():
    routes = {"/api/accounts/111/messages/search": zoho_ok([])}
    client, transport = make_client(routes)
    client.search_messages("111", "subject:faktúra::has:attachment", limit=5)
    assert transport.calls[-1]["query"]["searchKey"] == "subject:faktúra::has:attachment"


def test_expired_token_triggers_one_retry_then_succeeds():
    routes = {
        "/api/accounts": [
            HttpResponse(status=401, body=zoho_error("INVALID_OAUTHTOKEN")),
            zoho_ok(ACCOUNTS),
        ]
    }
    client, transport = make_client(routes)
    assert len(client.list_accounts()) == 2
    # dvakrát API a dvakrát token (druhý po zneplatnení)
    assert transport.paths().count("/api/accounts") == 2
    assert len([c for c in transport.calls if "/oauth/" in c["path"]]) == 2


def test_persistent_token_failure_explains_what_to_check():
    routes = {"/api/accounts": HttpResponse(status=401, body=zoho_error("INVALID_OAUTHTOKEN"))}
    client, _ = make_client(routes)
    with pytest.raises(ZohoAuthError, match="ZohoMail.messages.READ"):
        client.list_accounts()


def test_api_error_is_surfaced_with_its_code():
    routes = {"/api/accounts/111/folders": HttpResponse(status=400, body=zoho_error("INVALID_INPUT"))}
    client, _ = make_client(routes)
    with pytest.raises(ZohoApiError, match="INVALID_INPUT"):
        client.list_folders("111")


def test_non_json_body_is_reported_clearly():
    routes = {"/api/accounts/111/folders": HttpResponse(status=200, body="<html>nope</html>")}
    client, _ = make_client(routes)
    with pytest.raises(ZohoApiError, match="nie je JSON"):
        client.list_folders("111")


def test_throttling_is_retried():
    delays = []
    routes = {
        "/api/accounts": [
            HttpResponse(status=429, headers={"Retry-After": "5"}, body=""),
            zoho_ok(ACCOUNTS),
        ]
    }
    client, _ = make_client(routes, sleep=delays.append)
    assert len(client.list_accounts()) == 2
    assert delays == [5.0]  # Retry-After má prednosť pred vlastným backoffom


def test_json_calls_ask_for_json():
    client, transport = make_client({"/api/accounts": zoho_ok(ACCOUNTS)})
    client.list_accounts()
    api_call = next(c for c in transport.calls if c["path"] == "/api/accounts")
    assert api_call["headers"]["Accept"] == "application/json"


def test_attachment_download_asks_for_binary():
    # So žiadosťou o JSON vracia Zoho na tomto endpointe 406 Not Acceptable.
    path = "/api/accounts/111/folders/9/messages/77/attachments/a1"
    routes = {
        path: HttpResponse(
            status=200,
            headers={"Content-Type": "application/pdf"},
            content=b"%PDF-1.4",
        )
    }
    client, transport = make_client(routes)
    assert client.get_attachment_content("111", "9", "77", "a1") == b"%PDF-1.4"
    assert transport.calls[-1]["headers"]["Accept"] == "application/octet-stream"


def test_message_content_requests_folder_scoped_path():
    path = "/api/accounts/111/folders/9/messages/77/content"
    client, transport = make_client({path: zoho_ok({"content": "<p>ahoj</p>"})})
    result = client.get_message_content("111", "9", "77")
    assert result["content"] == "<p>ahoj</p>"
    assert transport.calls[-1]["path"] == path
    assert transport.calls[-1]["query"]["includeBlockContent"] == "true"


def test_thread_listing_filters_by_thread_id():
    routes = {"/api/accounts/111/messages/view": zoho_ok([])}
    client, transport = make_client(routes)
    client.list_thread_messages("111", "555", limit=10)
    assert transport.calls[-1]["query"]["threadId"] == "555"


def test_attachment_info_unwraps_the_list():
    path = "/api/accounts/111/folders/9/messages/77/attachmentinfo"
    routes = {path: zoho_ok({"attachments": [{"attachmentName": "faktura.pdf"}]})}
    client, _ = make_client(routes)
    assert client.get_attachment_info("111", "9", "77") == [{"attachmentName": "faktura.pdf"}]


@pytest.mark.parametrize(
    "value,expected",
    [
        ("1725379200000", "2024-09-03T16:00:00+00:00"),
        (1725379200000, "2024-09-03T16:00:00+00:00"),
        (None, None),
        ("", None),
        ("0", None),
        ("nezmysel", None),
    ],
)
def test_epoch_conversion(value, expected):
    assert epoch_ms_to_iso(value) == expected
