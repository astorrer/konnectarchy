from __future__ import annotations

import gi

gi.require_version("Gio", "2.0")
from gi.repository import GLib

from .bus import PROPS_IFACE, call, plugin_path
from .devices import require_device
from .notice import parse_notification
from .util import clamp_id, clamp_list, clamp_str, emit, fail

NOTIF_IFACE = "org.kde.kdeconnect.device.notifications"
ITEM_IFACE = "org.kde.kdeconnect.device.notifications.notification"
MAX_NOTIFICATIONS = 128


def notification_path(device_id: str, nid: str) -> str:
    return f"{plugin_path(device_id, 'notifications')}/{clamp_id(nid)}"


def notification_ids(bus, device_id: str) -> list[str]:
    result = call(
        bus,
        plugin_path(device_id, "notifications"),
        NOTIF_IFACE,
        "activeNotifications",
        None,
        "(as)",
    )
    return [clamp_str(item) for item in clamp_list(result.unpack()[0], MAX_NOTIFICATIONS)]


def notification_count(bus, device_id: str) -> int:
    try:
        return len(notification_ids(bus, device_id))
    except GLib.Error:
        return 0


def _props(bus, device_id: str, nid: str) -> dict:
    try:
        result = call(
            bus,
            notification_path(device_id, nid),
            PROPS_IFACE,
            "GetAll",
            GLib.Variant("(s)", (ITEM_IFACE,)),
            "(a{sv})",
        )
        return dict(result.unpack()[0] or {})
    except GLib.Error:
        return {}


def list_notifications(bus, device_id: str) -> list[dict]:
    rows = []
    for nid in notification_ids(bus, device_id):
        rows.append(parse_notification(nid, _props(bus, device_id, nid)))

    def sort_key(row: dict):
        try:
            return -int(row.get("id") or 0)
        except ValueError:
            return 0

    rows.sort(key=sort_key)
    return rows


def cmd_notifications(args: list[str]) -> None:
    bus, device_id = require_device(args[0] if args else "")
    emit({"ok": True, "notifications": list_notifications(bus, device_id)})


def _dismiss_one(bus, device_id: str, nid: str) -> None:
    call(bus, notification_path(device_id, nid), ITEM_IFACE, "dismiss", None)


def cmd_notification_dismiss(args: list[str]) -> None:
    if len(args) < 2:
        fail("Usage: notification-dismiss <device-id> <id|--all>")
    bus, device_id = require_device(args[0])
    target = args[1]
    if target == "--all":
        dismissed = 0
        for item in list_notifications(bus, device_id):
            if not item.get("dismissable"):
                continue
            try:
                _dismiss_one(bus, device_id, item["id"])
                dismissed += 1
            except GLib.Error:
                continue
        emit({"ok": True, "dismissed": dismissed})
        return
    _dismiss_one(bus, device_id, target)
    emit({"ok": True, "id": target})


def cmd_notification_reply(args: list[str]) -> None:
    if len(args) < 3:
        fail("Usage: notification-reply <device-id> <id> <text>")
    bus, device_id = require_device(args[0])
    nid = args[1]
    text = " ".join(args[2:]).strip()
    if not text:
        fail("Message is empty")
    try:
        call(
            bus,
            notification_path(device_id, nid),
            ITEM_IFACE,
            "sendReply",
            GLib.Variant("(s)", (text,)),
        )
    except GLib.Error:
        call(
            bus,
            plugin_path(device_id, "notifications"),
            NOTIF_IFACE,
            "sendReply",
            GLib.Variant("(ss)", (nid, text)),
        )
    emit({"ok": True, "id": nid})
