from __future__ import annotations

import select
import subprocess
import time
from pathlib import Path

import gi

gi.require_version("Gio", "2.0")
from gi.repository import GLib

from .bus import (
    BUS_NAME,
    DAEMON_IFACE,
    DAEMON_PATH,
    DEVICE_IFACE,
    call,
    device_path,
    get_prop,
    name_has_owner,
    plugin_path,
    session_bus,
    try_call,
    unpack_string_list,
)
from .media import read_media
from .util import clamp_list, clamp_str, emit, fail

MAX_DEVICES = 32
MAX_PLUGINS = 64
MAX_CLIPBOARD_BYTES = 4 << 20
CLIPBOARD_TIMEOUT = 5


def device_ids(bus) -> list[str]:
    result = try_call(
        bus,
        DAEMON_PATH,
        DAEMON_IFACE,
        [
            ("devices", GLib.Variant("(b)", (False,))),
            ("devices", None),
        ],
    )
    ids = result.unpack()[0] if result.n_children() else []
    return [clamp_str(item) for item in clamp_list(ids, MAX_DEVICES)]


def plugin_names(bus, device_id: str) -> list[str]:
    path = device_path(device_id)
    names = get_prop(bus, path, DEVICE_IFACE, "supportedPlugins", []) or []
    if not names:
        try:
            names = unpack_string_list(call(bus, path, DEVICE_IFACE, "loadedPlugins", None))
        except GLib.Error:
            names = []
    cleaned = []
    for name in clamp_list(names, MAX_PLUGINS):
        text = clamp_str(name)
        if text.startswith("kdeconnect_"):
            text = text.split("_", 1)[-1]
        cleaned.append(text)
    return cleaned


def has_plugin(bus, device_id: str, name: str) -> bool:
    try:
        return bool(
            call(
                bus,
                device_path(device_id),
                DEVICE_IFACE,
                "hasPlugin",
                GLib.Variant("(s)", (name,)),
                "b",
            ).unpack()[0]
        )
    except GLib.Error:
        return False


def read_device(bus, device_id: str) -> dict:
    path = device_path(device_id)
    plugins = plugin_names(bus, device_id)
    battery = -1
    charging = False
    charge = get_prop(bus, plugin_path(device_id, "battery"), "org.kde.kdeconnect.device.battery", "charge", None)
    charging_val = get_prop(
        bus,
        plugin_path(device_id, "battery"),
        "org.kde.kdeconnect.device.battery",
        "isCharging",
        None,
    )
    if isinstance(charge, int):
        battery = charge
    if isinstance(charging_val, bool):
        charging = charging_val
    network_type = get_prop(
        bus,
        plugin_path(device_id, "connectivity_report"),
        "org.kde.kdeconnect.device.connectivity_report",
        "cellularNetworkType",
        "",
    )
    network_strength = get_prop(
        bus,
        plugin_path(device_id, "connectivity_report"),
        "org.kde.kdeconnect.device.connectivity_report",
        "cellularNetworkStrength",
        -1,
    )
    counts = _notification_counts(bus, device_id)
    has_mpris = has_plugin(bus, device_id, "kdeconnect_mprisremote") or "mprisremote" in plugins
    media = None
    if has_mpris:
        try:
            media = read_media(bus, device_id)
        except GLib.Error:
            media = None
    return {
        "id": device_id,
        "name": clamp_str(get_prop(bus, path, DEVICE_IFACE, "name", device_id) or device_id),
        "type": clamp_str(get_prop(bus, path, DEVICE_IFACE, "type", "")),
        "reachable": bool(get_prop(bus, path, DEVICE_IFACE, "isReachable", False)),
        "paired": bool(get_prop(bus, path, DEVICE_IFACE, "isPaired", False)),
        "pairRequested": bool(get_prop(bus, path, DEVICE_IFACE, "isPairRequested", False)),
        "pairRequestedByPeer": bool(get_prop(bus, path, DEVICE_IFACE, "isPairRequestedByPeer", False)),
        "battery": battery,
        "charging": charging,
        "networkType": clamp_str(network_type),
        "networkStrength": int(network_strength) if isinstance(network_strength, int) else -1,
        "plugins": plugins,
        "hasSms": has_plugin(bus, device_id, "kdeconnect_sms") or "sms" in plugins,
        "hasNotifications": has_plugin(bus, device_id, "kdeconnect_notifications") or "notifications" in plugins,
        "hasMpris": has_mpris,
        "media": media,
        "notificationCount": counts[0],
        "smsNotificationCount": counts[1],
    }


def _notification_counts(bus, device_id: str) -> tuple[int, int]:
    try:
        from .notice import is_sms_notification
        from .notifications import list_notifications

        rows = list_notifications(bus, device_id)
    except GLib.Error:
        return 0, 0
    sms = 0
    for row in rows:
        if is_sms_notification(row):
            sms += 1
    return len(rows), sms


def sort_devices(devices: list[dict]) -> list[dict]:
    def key(device: dict):
        return (
            0 if device.get("reachable") and device.get("paired") else 1,
            0 if device.get("pairRequestedByPeer") else 1,
            0 if device.get("reachable") else 1,
            str(device.get("name") or "").lower(),
        )

    return sorted(devices, key=key)


def require_device(device_id: str) -> tuple:
    if not device_id:
        fail("Missing device id")
    bus = session_bus()
    if not name_has_owner(bus, BUS_NAME):
        fail("KDE Connect is not running")
    return bus, device_id


def cmd_ping(args: list[str]) -> None:
    bus, device_id = require_device(args[0] if args else "")
    try_call(
        bus,
        plugin_path(device_id, "ping"),
        "org.kde.kdeconnect.device.ping",
        [("sendPing", None), ("sendPing", GLib.Variant("(s)", ("Ping from Konnectarchy",)))],
    )
    emit({"ok": True})


def cmd_ring(args: list[str]) -> None:
    bus, device_id = require_device(args[0] if args else "")
    try_call(
        bus,
        plugin_path(device_id, "findmyphone"),
        "org.kde.kdeconnect.device.findmyphone",
        [("ring", None)],
    )
    emit({"ok": True})


def cmd_pair(args: list[str]) -> None:
    bus, device_id = require_device(args[0] if args else "")
    try_call(
        bus,
        device_path(device_id),
        DEVICE_IFACE,
        [("requestPairing", None), ("requestPair", None)],
    )
    emit({"ok": True})


def cmd_unpair(args: list[str]) -> None:
    bus, device_id = require_device(args[0] if args else "")
    call(bus, device_path(device_id), DEVICE_IFACE, "unpair", None)
    emit({"ok": True})


def cmd_accept(args: list[str]) -> None:
    bus, device_id = require_device(args[0] if args else "")
    try_call(
        bus,
        device_path(device_id),
        DEVICE_IFACE,
        [("acceptPairing", None), ("acceptPairingRequest", None)],
    )
    emit({"ok": True})


def cmd_reject(args: list[str]) -> None:
    bus, device_id = require_device(args[0] if args else "")
    try_call(
        bus,
        device_path(device_id),
        DEVICE_IFACE,
        [("rejectPairing", None), ("rejectPairingRequest", None)],
    )
    emit({"ok": True})


def cmd_share_file(args: list[str]) -> None:
    if len(args) < 2:
        fail("Usage: share-file <device-id> <path>")
    bus, device_id = require_device(args[0])
    path = Path(args[1]).expanduser().resolve()
    if not path.exists():
        fail(f"File not found: {path}")
    uri = path.as_uri()
    call(
        bus,
        plugin_path(device_id, "share"),
        "org.kde.kdeconnect.device.share",
        "shareUrl",
        GLib.Variant("(s)", (uri,)),
    )
    emit({"ok": True, "uri": uri})


def cmd_share_text(args: list[str]) -> None:
    if len(args) < 2:
        fail("Usage: share-text <device-id> <text>")
    bus, device_id = require_device(args[0])
    text = " ".join(args[1:])
    call(
        bus,
        plugin_path(device_id, "share"),
        "org.kde.kdeconnect.device.share",
        "shareText",
        GLib.Variant("(s)", (text,)),
    )
    emit({"ok": True})


def cmd_send_clipboard(args: list[str]) -> None:
    bus, device_id = require_device(args[0] if args else "")
    try:
        try_call(
            bus,
            plugin_path(device_id, "clipboard"),
            "org.kde.kdeconnect.device.clipboard",
            [("sendClipboard", None)],
        )
    except GLib.Error:
        proc = subprocess.Popen(
            ["wl-paste", "--no-newline"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + CLIPBOARD_TIMEOUT
        chunks: list[bytes] = []
        total = 0
        timed_out = False
        oversized = False
        try:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    timed_out = True
                    break
                ready, _, _ = select.select([proc.stdout], [], [], remaining)
                if not ready:
                    timed_out = True
                    break
                chunk = proc.stdout.read(4096)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_CLIPBOARD_BYTES:
                    oversized = True
                    break
                chunks.append(chunk)
        finally:
            try:
                proc.kill()
            except OSError:
                pass
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=2)
            try:
                proc.stdout.close()
            except OSError:
                pass
        if timed_out:
            fail("Clipboard read timed out")
        if oversized:
            fail("Clipboard read failed")
        text = b"".join(chunks).decode("utf-8", errors="replace").strip()
        if not text:
            fail("Clipboard is empty")
        cmd_share_text([device_id, text])
        return
    emit({"ok": True})
