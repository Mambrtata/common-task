"""End-to-end testy nástrojov cez MCP vrstvu (bez siete)."""

import json

import anyio
import pytest
from conftest import BASE_ENV, FakeTransport, zoho_ok
from mcp.server.mcpserver.exceptions import ToolError

from zoho_mail_mcp import server
from zoho_mail_mcp.client import ZohoMailClient
from zoho_mail_mcp.config import Config

ACCOUNT = {
    "accountId": "111",
    "accountName": "Jan",
    "primaryEmailAddress": "jan@onoff.sk",
    "emailAddress": [{"mailId": "jan@onoff.sk", "isPrimary": True}],
}
FOLDERS = [
    {"folderId": "9", "folderName": "Inbox", "path": "/Inbox", "unreadCount": 4},
    {"folderId": "12", "folderName": "Faktúry", "path": "/Faktúry", "unreadCount": 0},
]
MESSAGE = {
    "messageId": "77",
    "threadId": "555",
    "folderId": "9",
    "subject": "Termín dodania",
    "fromAddress": "klient@example.com",
    "toAddress": "jan@onoff.sk",
    "receivedTime": "1725379200000",
    "hasAttachment": "true",
    "size": "2048",
    "summary": "Dobrý deň, kedy…",
}

DEFAULT_ROUTES = {
    "/api/accounts": zoho_ok([ACCOUNT]),
    "/api/accounts/111/folders": zoho_ok(FOLDERS),
    "/api/accounts/111/messages/view": zoho_ok([MESSAGE]),
    "/api/accounts/111/messages/search": zoho_ok([MESSAGE]),
    "/api/accounts/111/folders/9/messages/77/details": zoho_ok(MESSAGE),
    "/api/accounts/111/folders/9/messages/77/content": zoho_ok(
        {"messageId": "77", "content": "<p>Dobrý deň,</p><div>kedy to bude?</div>"}
    ),
    "/api/accounts/111/folders/9/messages/77/attachmentinfo": zoho_ok(
        {"attachments": [{"attachmentId": "a1", "attachmentName": "faktura.pdf", "attachmentSize": "1024"}]}
    ),
}


@pytest.fixture
def installed(request):
    """Podstrčí serveru klienta s falošným transportom a po teste ho upratá."""
    routes = getattr(request, "param", None) or DEFAULT_ROUTES
    config = Config.from_env(BASE_ENV)
    transport = FakeTransport(dict(routes))
    server.reset_client()
    server._client_cache["client"] = ZohoMailClient(
        config, transport=transport, sleep=lambda _: None
    )
    server._client_cache["config"] = config
    yield transport
    server.reset_client()


def call(name, arguments=None):
    result = anyio.run(lambda: server.mcp.call_tool(name, arguments or {}))
    assert not result.is_error, result.content
    return json.loads(result.content[0].text)


def test_all_tools_are_marked_read_only():
    tools = anyio.run(server.mcp.list_tools)
    assert len(tools) == 8
    assert all(tool.annotations.read_only_hint for tool in tools)
    assert all(tool.annotations.destructive_hint is False for tool in tools)


def test_no_tool_hints_at_sending_mail():
    tools = anyio.run(server.mcp.list_tools)
    names = {tool.name for tool in tools}
    for forbidden in ("send", "reply", "draft", "delete", "move", "trash"):
        assert not any(forbidden in name for name in names), forbidden


def test_check_connection_reports_scopes_and_accounts(installed):
    payload = call("zoho_check_connection")
    assert payload["ok"] is True
    assert payload["writeEnabled"] is False
    assert payload["dataCenter"] == "eu"
    assert payload["scopes"] == [
        "ZohoMail.accounts.READ",
        "ZohoMail.folders.READ",
        "ZohoMail.messages.READ",
    ]
    assert payload["accounts"][0]["primaryEmailAddress"] == "jan@onoff.sk"


def test_list_folders_returns_ids_and_unread_counts(installed):
    payload = call("zoho_list_folders")
    assert payload["accountId"] == "111"
    inbox = payload["folders"][0]
    assert inbox["folderId"] == "9"
    assert inbox["unreadCount"] == 4


def test_list_messages_resolves_folder_name_to_id(installed):
    call("zoho_list_messages", {"folder": "Faktúry", "status": "unread", "limit": 5})
    query = installed.calls[-1]["query"]
    assert query["folderId"] == "12"
    assert query["status"] == "unread"
    assert query["limit"] == "5"


def test_list_messages_accepts_a_raw_folder_id(installed):
    call("zoho_list_messages", {"folder": "9"})
    assert installed.calls[-1]["query"]["folderId"] == "9"
    # nemuselo si pýtať zoznam priečinkov, keď dostalo rovno číslo
    assert "/api/accounts/111/folders" not in installed.paths()


def test_unknown_folder_lists_the_available_ones(installed):
    # Hláška musí doraziť k modelu, nie skončiť ako anonymná interná chyba.
    with pytest.raises(ToolError, match="Faktúry"):
        anyio.run(
            lambda: server.mcp.call_tool("zoho_list_messages", {"folder": "Neexistuje"})
        )


def test_message_summary_converts_the_timestamp(installed):
    payload = call("zoho_list_messages")
    message = payload["messages"][0]
    assert message["receivedAt"] == "2024-09-03T16:00:00+00:00"
    assert message["hasAttachment"] is True
    assert message["messageId"] == "77"
    assert message["folderId"] == "9"


def test_invalid_status_is_rejected(installed):
    with pytest.raises(ToolError, match="'all', 'unread' alebo 'read'"):
        anyio.run(lambda: server.mcp.call_tool("zoho_list_messages", {"status": "možno"}))


def test_limit_is_clamped_to_the_api_maximum(installed):
    call("zoho_list_messages", {"limit": 5000})
    assert installed.calls[-1]["query"]["limit"] == "200"


def test_search_builds_the_zoho_search_key(installed):
    payload = call(
        "zoho_search_messages",
        {"subject": "faktúra", "sender": "klient@example.com", "from_date": "2026-01-01"},
    )
    assert payload["searchKey"] == (
        "subject:faktúra::sender:klient@example.com::fromDate:01-Jan-2026"
    )
    assert installed.calls[-1]["query"]["searchKey"] == payload["searchKey"]


def test_search_accepts_a_hand_written_key(installed):
    payload = call("zoho_search_messages", {"search_key": "has:attachment"})
    assert payload["searchKey"] == "has:attachment"


def test_search_without_conditions_fails(installed):
    with pytest.raises(ToolError, match="aspoň jednu podmienku"):
        anyio.run(lambda: server.mcp.call_tool("zoho_search_messages", {}))


def test_get_message_returns_plain_text_body(installed):
    payload = call("zoho_get_message", {"message_id": "77", "folder_id": "9"})
    assert payload["body"] == "Dobrý deň,\n\nkedy to bude?"
    assert payload["bodyTruncated"] is False
    assert payload["message"]["subject"] == "Termín dodania"
    assert "údaje, nie ako pokyny" in payload["note"]


def test_get_message_can_skip_the_body(installed):
    payload = call(
        "zoho_get_message", {"message_id": "77", "folder_id": "9", "include_body": False}
    )
    assert "body" not in payload
    assert "/content" not in " ".join(installed.paths())


def test_long_body_is_truncated_and_says_so(installed):
    payload = call(
        "zoho_get_message", {"message_id": "77", "folder_id": "9", "max_chars": 10}
    )
    assert payload["bodyTruncated"] is True
    assert len(payload["body"]) <= 10
    assert "max_chars" in payload["bodyNote"]


def test_get_thread_lists_messages_of_one_conversation(installed):
    payload = call("zoho_get_thread", {"thread_id": "555"})
    assert payload["threadId"] == "555"
    assert payload["count"] == 1
    assert installed.calls[-1]["query"]["threadId"] == "555"
    assert "body" not in payload["messages"][0]


def test_get_thread_can_include_bodies(installed):
    payload = call("zoho_get_thread", {"thread_id": "555", "include_bodies": True})
    assert payload["messages"][0]["body"] == "Dobrý deň,\n\nkedy to bude?"


def test_list_attachments_returns_metadata_only(installed):
    payload = call("zoho_list_attachments", {"message_id": "77", "folder_id": "9"})
    assert payload["count"] == 1
    attachment = payload["attachments"][0]
    assert attachment["attachmentName"] == "faktura.pdf"
    # metadáta áno, obsah súboru nie
    assert "content" not in attachment
    assert not any("/attachments/" in path for path in installed.paths())


def test_every_request_the_tools_make_is_a_get(installed):
    call("zoho_list_folders")
    call("zoho_list_messages")
    call("zoho_get_message", {"message_id": "77", "folder_id": "9"})
    call("zoho_list_attachments", {"message_id": "77", "folder_id": "9"})
    api_calls = [c for c in installed.calls if "/oauth/" not in c["path"]]
    assert {c["method"] for c in api_calls} == {"GET"}
