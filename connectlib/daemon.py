from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import gi

gi.require_version("Gio", "2.0")
from gi.repository import GLib

from .bus import (
    BUS_NAME,
    DAEMON_IFACE,
    DAEMON_PATH,
    call,
    get_prop,
    name_has_owner,
    session_bus,
)
from .devices import device_ids, read_device, sort_devices
from .util import clamp_str, emit, fail

DAEMON_CANDIDATES = (
    "/usr/lib/kdeconnectd",
    "/usr/libexec/kdeconnectd",
    "/usr/bin/kdeconnectd",
)

AUTOSTART_PATH = Path.home() / ".config" / "autostart" / "kdeconnectd.desktop"

AUTOSTART_DESKTOP = """[Desktop Entry]
Type=Application
Name=KDE Connect
Comment=Phone connect daemon for Konnectarchy
Exec={daemon}
Terminal=false
X-GNOME-Autostart-enabled=true
"""


def daemon_path() -> str | None:
    for path in DAEMON_CANDIDATES:
        if os.access(path, os.X_OK):
            return path
    found = shutil.which("kdeconnectd")
    return found if found and os.access(found, os.X_OK) else None


def status_payload() -> dict:
    path = daemon_path()
    installed = path is not None
    bus = session_bus()
    running = name_has_owner(bus, BUS_NAME)
    payload = {
        "ok": True,
        "installed": installed,
        "running": running,
        "daemonPath": path or "",
        "announcedName": "",
        "devices": [],
        "error": "",
    }
    if not running:
        return payload
    try:
        payload["announcedName"] = clamp_str(get_prop(bus, DAEMON_PATH, DAEMON_IFACE, "announcedName", ""))
        if not payload["announcedName"]:
            try:
                result = call(bus, DAEMON_PATH, DAEMON_IFACE, "announcedName", None)
                payload["announcedName"] = clamp_str(result.unpack()[0])
            except GLib.Error:
                pass
        payload["devices"] = sort_devices([read_device(bus, device_id) for device_id in device_ids(bus)])
    except GLib.Error as error:
        payload["error"] = clamp_str(error.message)
    return payload


def cmd_status(_args: list[str]) -> None:
    emit(status_payload())


def cmd_start(_args: list[str]) -> None:
    path = daemon_path()
    if not path:
        fail("kdeconnect is not installed")
    bus = session_bus()
    if name_has_owner(bus, BUS_NAME):
        emit({"ok": True, "running": True})
        return
    subprocess.Popen(
        [path],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    emit({"ok": True, "running": True, "started": True})


def cmd_stop(_args: list[str]) -> None:
    bus = session_bus()
    if not name_has_owner(bus, BUS_NAME):
        emit({"ok": True, "running": False})
        return
    try:
        call(bus, "/MainApplication", "org.qtproject.Qt.QCoreApplication", "quit", None)
    except GLib.Error:
        subprocess.run(["pkill", "-u", str(os.getuid()), "-x", "kdeconnectd"], check=False)
    emit({"ok": True, "running": False})


def cmd_autostart(_args: list[str]) -> None:
    path = daemon_path()
    if not path:
        fail("kdeconnect is not installed")
    AUTOSTART_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUTOSTART_PATH.write_text(AUTOSTART_DESKTOP.format(daemon=path), encoding="utf-8")
    emit({"ok": True, "path": str(AUTOSTART_PATH)})
