from __future__ import annotations

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib

BUS_NAME = "org.kde.kdeconnect"
DAEMON_PATH = "/modules/kdeconnect"
DAEMON_IFACE = "org.kde.kdeconnect.daemon"
DEVICE_IFACE = "org.kde.kdeconnect.device"
CONV_IFACE = "org.kde.kdeconnect.device.conversations"
SMS_IFACE = "org.kde.kdeconnect.device.sms"
PROPS_IFACE = "org.freedesktop.DBus.Properties"
TIMEOUT_MS = 2500


def session_bus():
    return Gio.bus_get_sync(Gio.BusType.SESSION, None)


def name_has_owner(bus, name: str) -> bool:
    try:
        result = bus.call_sync(
            "org.freedesktop.DBus",
            "/org/freedesktop/DBus",
            "org.freedesktop.DBus",
            "NameHasOwner",
            GLib.Variant("(s)", (name,)),
            GLib.VariantType("(b)"),
            Gio.DBusCallFlags.NONE,
            TIMEOUT_MS,
            None,
        )
        return bool(result.unpack()[0])
    except GLib.Error:
        return False


def call(
    bus,
    path: str,
    iface: str,
    method: str,
    params: GLib.Variant | None = None,
    reply_type: str | None = None,
    timeout_ms: int = TIMEOUT_MS,
):
    return bus.call_sync(
        BUS_NAME,
        path,
        iface,
        method,
        params,
        GLib.VariantType(reply_type) if reply_type else None,
        Gio.DBusCallFlags.NONE,
        timeout_ms,
        None,
    )


def get_prop(bus, path: str, iface: str, name: str, default=None):
    try:
        result = bus.call_sync(
            BUS_NAME,
            path,
            PROPS_IFACE,
            "Get",
            GLib.Variant("(ss)", (iface, name)),
            GLib.VariantType("(v)"),
            Gio.DBusCallFlags.NONE,
            TIMEOUT_MS,
            None,
        )
        return result.unpack()[0]
    except GLib.Error:
        return default


def try_call(bus, path: str, iface: str, methods: list[tuple[str, GLib.Variant | None]]):
    last_error = None
    for method, params in methods:
        try:
            return call(bus, path, iface, method, params)
        except GLib.Error as error:
            last_error = error
            continue
    if last_error:
        raise last_error
    raise RuntimeError("no methods to call")


from .util import clamp_id


def device_path(device_id: str) -> str:
    return f"{DAEMON_PATH}/devices/{clamp_id(device_id)}"


def plugin_path(device_id: str, plugin: str) -> str:
    return f"{device_path(device_id)}/{plugin}"


def unpack_string_list(result) -> list[str]:
    raw = result.unpack() if hasattr(result, "unpack") else result
    if isinstance(raw, (list, tuple)) and len(raw) == 1 and isinstance(raw[0], (list, tuple)):
        raw = raw[0]
    return [str(item) for item in (raw or [])]
