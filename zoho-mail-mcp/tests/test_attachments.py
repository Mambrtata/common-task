"""Názov prílohy je vstup od cudzieho odosielateľa – musí byť neškodný."""

import pytest

from zoho_mail_mcp.attachments import (
    AttachmentTooLarge,
    resolve_inside,
    safe_filename,
    save_attachment,
    unique_path,
)
from zoho_mail_mcp.errors import ZohoMailMCPError


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("faktura.pdf", "faktura.pdf"),
        # Lomka je v názvoch faktúr bežná, nesmie zožrať začiatok mena.
        ("Faktúra 8/2026.pdf", "Faktura_8_2026.pdf"),
        ("../../etc/passwd", "etc_passwd"),
        ("../../../root/.ssh/authorized_keys", "root_.ssh_authorized_keys"),
        ("C:\\Windows\\system32\\evil.exe", "C_Windows_system32_evil.exe"),
        ("..", "priloha"),
        (".", "priloha"),
        ("", "priloha"),
        (None, "priloha"),
        (".bashrc", "bashrc"),
        ("Faktúra za júl 2026.pdf", "Faktura_za_jul_2026.pdf"),
        ("zlá; rm -rf /.pdf", "zla_rm_-rf_.pdf"),
        ("$(whoami).pdf", "whoami_.pdf"),
    ],
)
def test_dangerous_names_are_defused(raw, expected):
    assert safe_filename(raw) == expected


def test_no_sanitised_name_contains_separators():
    for raw in ("../x", "a/b/c", "a\\b", "..\\..\\x"):
        cleaned = safe_filename(raw)
        assert "/" not in cleaned and "\\" not in cleaned
        assert not cleaned.startswith(".")


def test_long_name_is_shortened_but_keeps_suffix():
    cleaned = safe_filename("a" * 300 + ".pdf")
    assert len(cleaned) <= 100
    assert cleaned.endswith(".pdf")


def test_saved_file_lands_in_the_directory(tmp_path):
    target = save_attachment(tmp_path, "faktura.pdf", b"%PDF-1.4", max_bytes=1000)
    assert target.parent == tmp_path
    assert target.read_bytes() == b"%PDF-1.4"


def test_traversal_name_cannot_escape_the_directory(tmp_path):
    target = save_attachment(tmp_path, "../../uniknute.txt", b"x", max_bytes=1000)
    assert target.parent == tmp_path
    assert not (tmp_path.parent.parent / "uniknute.txt").exists()


def test_name_with_slashes_keeps_its_beginning(tmp_path):
    target = save_attachment(tmp_path, "FA 123/2026.pdf", b"x", max_bytes=1000)
    assert target.name == "FA_123_2026.pdf"
    assert target.parent == tmp_path


def test_second_file_does_not_overwrite_the_first(tmp_path):
    first = save_attachment(tmp_path, "faktura.pdf", b"prva", max_bytes=1000)
    second = save_attachment(tmp_path, "faktura.pdf", b"druha", max_bytes=1000)
    assert first != second
    assert first.read_bytes() == b"prva"
    assert second.read_bytes() == b"druha"


def test_oversized_attachment_is_refused(tmp_path):
    with pytest.raises(AttachmentTooLarge, match="ZOHO_MAX_ATTACHMENT_BYTES"):
        save_attachment(tmp_path, "velka.bin", b"x" * 2000, max_bytes=1000)
    assert list(tmp_path.iterdir()) == []


def test_saved_file_is_not_world_readable(tmp_path):
    target = save_attachment(tmp_path, "faktura.pdf", b"x", max_bytes=1000)
    assert oct(target.stat().st_mode)[-3:] == "640"


def test_directory_is_created_when_missing(tmp_path):
    nested = tmp_path / "a" / "b"
    save_attachment(nested, "x.pdf", b"x", max_bytes=1000)
    assert nested.is_dir()


def test_unique_path_gives_up_gracefully(tmp_path):
    (tmp_path / "x.pdf").write_bytes(b"")
    assert unique_path(tmp_path, "x.pdf").name == "x-1.pdf"


def test_resolve_inside_accepts_plain_names(tmp_path):
    (tmp_path / "faktura.pdf").write_bytes(b"x")
    assert resolve_inside(tmp_path, "faktura.pdf").name == "faktura.pdf"


@pytest.mark.parametrize("name", ["../secret", "../../etc/passwd", "/etc/passwd"])
def test_resolve_inside_blocks_escapes(tmp_path, name):
    with pytest.raises(ZohoMailMCPError, match="mimo priečinka"):
        resolve_inside(tmp_path, name)
