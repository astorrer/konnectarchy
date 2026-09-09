from __future__ import annotations

import re

from .util import MAX_TEXT_CHARS, clamp_str

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
    reply_id = clamp_str(data.get("replyId"))
    title = clamp_str(data.get("title"))
    text = clamp_str(data.get("text"), MAX_TEXT_CHARS)
    ticker = clamp_str(data.get("ticker"), MAX_TEXT_CHARS)
    app_name = clamp_str(data.get("appName"))
    parsed = {
        "id": clamp_str(nid),
        "appName": app_name,
        "title": title,
        "text": text,
        "ticker": ticker,
        "silent": bool(data.get("silent")),
        "dismissable": bool(data.get("dismissable")),
        "canReply": reply_id != "",
        "replyId": reply_id,
        "isConversation": bool(data.get("isConversation")),
        "hasIcon": bool(data.get("hasIcon")),
    }
    parsed["sms"] = is_sms_notification(parsed)
    return parsed
