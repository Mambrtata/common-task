"""Podpísaný odkaz nesmie pustiť viac, než na čo bol vydaný."""

import pytest

from zoho_mail_mcp.signing import sign, signed_query, verify

SECRET = "tajny-podpisovy-kluc"
NOW = 1_000_000.0


def query_for(name, ttl=3600, secret=SECRET, now=NOW):
    return signed_query(name, secret, ttl=ttl, now=now)


def test_fresh_link_passes():
    assert verify("faktura.pdf", query_for("faktura.pdf"), SECRET, now=NOW)


def test_link_expires():
    query = query_for("faktura.pdf", ttl=60)
    assert verify("faktura.pdf", query, SECRET, now=NOW + 59)
    assert not verify("faktura.pdf", query, SECRET, now=NOW + 61)


def test_link_is_bound_to_one_file():
    query = query_for("faktura.pdf")
    assert not verify("iny-subor.pdf", query, SECRET, now=NOW)


def test_link_is_bound_to_the_secret():
    query = query_for("faktura.pdf")
    assert not verify("faktura.pdf", query, "iny-kluc", now=NOW)


def test_tampered_expiry_is_refused():
    query = query_for("faktura.pdf", ttl=60)
    forged = query.replace("exp=1000060", "exp=9999999999")
    assert not verify("faktura.pdf", forged, SECRET, now=NOW)


@pytest.mark.parametrize(
    "query",
    ["", "sig=abc", "exp=1000060", "exp=nie-cislo&sig=abc", "sig=&exp="],
)
def test_broken_query_is_refused(query):
    assert not verify("faktura.pdf", query, SECRET, now=NOW)


def test_signature_changes_with_every_input():
    assert sign("a.pdf", 1, SECRET) != sign("b.pdf", 1, SECRET)
    assert sign("a.pdf", 1, SECRET) != sign("a.pdf", 2, SECRET)
    assert sign("a.pdf", 1, SECRET) != sign("a.pdf", 1, "iny")


def test_signature_does_not_leak_the_secret():
    assert SECRET not in signed_query("faktura.pdf", SECRET, now=NOW)
