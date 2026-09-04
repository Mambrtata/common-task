"""Orezanie odpovedí Zoho na to podstatné, v jednotnom tvare."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .client import epoch_ms_to_iso


def account_summary(raw: Mapping[str, Any]) -> dict[str, Any]:
    addresses = raw.get("emailAddress")
    aliases = (
        [str(entry.get("mailId")) for entry in addresses if isinstance(entry, dict)]
        if isinstance(addresses, list)
        else []
    )
    return {
        "accountId": str(raw.get("accountId", "")),
        "accountName": raw.get("accountName") or raw.get("accountDisplayName"),
        "primaryEmailAddress": raw.get("primaryEmailAddress"),
        "emailAddresses": aliases,
    }


def folder_summary(raw: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "folderId": str(raw.get("folderId", "")),
        "folderName": raw.get("folderName"),
        "path": raw.get("path"),
        "unreadCount": raw.get("unreadCount"),
        "messageCount": raw.get("messageCount"),
        "parentFolderId": raw.get("parentFolderId"),
    }


def message_summary(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Hlavička správy bez tela – to sa dopĺňa až cez zoho_get_message."""
    return {
        "messageId": str(raw.get("messageId", "")),
        "threadId": str(raw.get("threadId")) if raw.get("threadId") else None,
        "folderId": str(raw.get("folderId")) if raw.get("folderId") else None,
        "subject": raw.get("subject"),
        "fromAddress": raw.get("fromAddress") or raw.get("sender"),
        "toAddress": raw.get("toAddress"),
        "ccAddress": raw.get("ccAddress"),
        "receivedAt": epoch_ms_to_iso(raw.get("receivedTime")),
        "sentAt": epoch_ms_to_iso(raw.get("sentDateInGMT")),
        "hasAttachment": _as_bool(raw.get("hasAttachment")),
        "size": raw.get("size"),
        "summary": raw.get("summary"),
        # `status` necháme tak, ako ho vrátilo Zoho – filtrovať prečítané
        # a neprečítané sa má parametrom `status` pri volaní, nie tu.
        "status": raw.get("status"),
    }


def attachment_summary(raw: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "attachmentId": str(raw.get("attachmentId", "")) or None,
        "attachmentName": raw.get("attachmentName") or raw.get("fileName"),
        "attachmentSize": raw.get("attachmentSize") or raw.get("size"),
        "attachmentType": raw.get("attachmentType") or raw.get("type"),
    }


def _as_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in ("true", "1", "yes"):
        return True
    if text in ("false", "0", "no"):
        return False
    return None
