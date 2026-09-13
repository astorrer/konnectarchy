from __future__ import annotations

import re

from . import bound

SMS_APP_NAMES = {
    "messages",
    "google messages",
    "messaging",
    "samsung messages",
    "textra",
    "qksms",
    "pulse",
    "pulse sms",
}


def is_sms_notification(item: dict | None) -> bool:
    name = " ".join(str((item or {}).get("appName") or "").split()).strip().lower()
    if not name:
        return False
    if name in SMS_APP_NAMES:
        return True
    return bool(re.search(r"\bsms\b", name))


def parse_notification(nid, props: dict | None) -> dict:
    data = props or {}
    reply_id = bound.label(data.get("replyId"))
    title = bound.label(data.get("title"))
    text = bound.text(data.get("text"))
    ticker = bound.text(data.get("ticker"))
    app_name = bound.label(data.get("appName"))
    parsed = {
        "id": bound.label(nid),
        "appName": app_name,
        "title": title,
        "text": text,
        "ticker": ticker,
        "silent": bound.flag(data.get("silent")),
        "dismissable": bound.flag(data.get("dismissable")),
        "canReply": reply_id != "",
        "replyId": reply_id,
        "isConversation": bound.flag(data.get("isConversation")),
        "hasIcon": bound.flag(data.get("hasIcon")),
    }
    parsed["sms"] = is_sms_notification(parsed)
    return parsed
