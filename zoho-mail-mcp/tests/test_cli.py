"""Testy vstupného bodu: voľba transportu a povinný token."""

import pytest

from zoho_mail_mcp.server import build_parser, main


def test_stdio_is_the_default():
    args = build_parser().parse_args([])
    assert args.transport == "stdio"
    assert args.host == "127.0.0.1"


def test_transport_can_be_set_by_flag():
    args = build_parser().parse_args(["--transport", "http", "--host", "10.147.17.5"])
    assert args.transport == "http"
    assert args.host == "10.147.17.5"


def test_environment_supplies_defaults(monkeypatch):
    monkeypatch.setenv("ZOHO_MCP_TRANSPORT", "http")
    monkeypatch.setenv("ZOHO_MCP_HOST", "10.147.17.5")
    args = build_parser().parse_args([])
    assert args.transport == "http"
    assert args.host == "10.147.17.5"


def test_flag_beats_environment(monkeypatch):
    monkeypatch.setenv("ZOHO_MCP_HOST", "10.147.17.5")
    args = build_parser().parse_args(["--host", "127.0.0.1"])
    assert args.host == "127.0.0.1"


def test_unknown_transport_is_refused():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["--transport", "carrier-pigeon"])


def test_http_without_token_refuses_to_start(monkeypatch, capsys):
    monkeypatch.delenv("ZOHO_MCP_AUTH_TOKEN", raising=False)
    with pytest.raises(SystemExit) as excinfo:
        main(["--transport", "http"])
    assert excinfo.value.code == 2
    assert "ZOHO_MCP_AUTH_TOKEN" in capsys.readouterr().err


def test_http_with_short_token_refuses_to_start(monkeypatch, capsys):
    monkeypatch.setenv("ZOHO_MCP_AUTH_TOKEN", "prikratke")
    with pytest.raises(SystemExit) as excinfo:
        main(["--transport", "http"])
    assert excinfo.value.code == 2
    assert "24 znakov" in capsys.readouterr().err


def test_bad_port_is_reported(monkeypatch, capsys):
    monkeypatch.setenv("ZOHO_MCP_AUTH_TOKEN", "u" * 32)
    monkeypatch.setenv("ZOHO_MCP_PORT", "osemtisic")
    with pytest.raises(SystemExit) as excinfo:
        main(["--transport", "http"])
    assert excinfo.value.code == 2
    assert "ZOHO_MCP_PORT" in capsys.readouterr().err
