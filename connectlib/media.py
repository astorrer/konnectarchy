from __future__ import annotations

import gi

gi.require_version("Gio", "2.0")
from gi.repository import GLib

from .bus import call, get_prop, plugin_path, unpack_string_list
from .util import clamp_list, clamp_str, emit, fail

MPRIS_IFACE = "org.kde.kdeconnect.device.mprisremote"

MEDIA_ACTIONS = ("Play", "Pause", "PlayPause", "Next", "Previous", "Stop")
MAX_PLAYERS = 32


def _props(bus, device_id: str) -> dict:
    props = {}
    names = (
        "player",
        "playerList",
        "title",
        "artist",
        "album",
        "isPlaying",
        "position",
        "length",
        "volume",
        "canSeek",
    )
    for name in names:
        props[name] = get_prop(bus, plugin_path(device_id, "mprisremote"), MPRIS_IFACE, name)
    return props


def read_media(bus, device_id: str) -> dict | None:
    props = _props(bus, device_id)
    if not isinstance(props.get("title"), str):
        return None
    players = [clamp_str(item) for item in clamp_list(unpack_string_list(props.get("playerList")), MAX_PLAYERS)]
    title = clamp_str(props.get("title"))
    artist = clamp_str(props.get("artist"))
    album = clamp_str(props.get("album"))
    is_playing = props.get("isPlaying") is True
    return {
        "player": clamp_str(props.get("player")),
        "players": players,
        "title": title,
        "artist": artist,
        "album": album,
        "isPlaying": is_playing,
        "position": props.get("position") if isinstance(props.get("position"), int) else 0,
        "length": props.get("length") if isinstance(props.get("length"), int) else 0,
        "volume": props.get("volume") if isinstance(props.get("volume"), int) else 0,
        "canSeek": props.get("canSeek") is True,
        "hasMedia": bool(title or artist or album or is_playing),
    }


def send_action(bus, device_id: str, action: str) -> None:
    call(
        bus,
        plugin_path(device_id, "mprisremote"),
        MPRIS_IFACE,
        "sendAction",
        GLib.Variant("(s)", (action,)),
    )


def _require(args: list[str]) -> tuple:
    from .devices import require_device

    return require_device(args[0] if args else "")


def cmd_media(args: list[str]) -> None:
    bus, device_id = _require(args)
    emit({"ok": True, "media": read_media(bus, device_id)})


def cmd_media_action(args: list[str]) -> None:
    if len(args) < 2:
        fail("Usage: media-action <device-id> <play|pause|toggle|next|previous|stop>")
    action = {
        "play": "Play",
        "pause": "Pause",
        "toggle": "PlayPause",
        "next": "Next",
        "previous": "Previous",
        "stop": "Stop",
    }.get(args[1].lower())
    if action is None:
        fail(f"Unknown media action: {args[1]}")
    bus, device_id = _require(args)
    send_action(bus, device_id, action)
    emit({"ok": True, "action": action})
