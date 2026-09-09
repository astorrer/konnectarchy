from __future__ import annotations

import shutil
import subprocess

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib

from .bus import (
    BUS_NAME,
    CONV_IFACE,
    SMS_IFACE,
    call,
    device_path,
    plugin_path,
)
from .contacts import annotate_message, load_contacts
from .devices import require_device
from .messages import parse_message
from .util import clamp_id, clamp_list, emit, fail

MAX_CONVERSATIONS = 256
MAX_THREAD_MESSAGES = 256


def active_conversations(bus, device_id: str) -> list[dict]:
    contacts = load_contacts(device_id)
    result = call(bus, device_path(device_id), CONV_IFACE, "activeConversations", None)
    rows = []
    for raw in clamp_list(result.unpack()[0], MAX_CONVERSATIONS):
        message = parse_message(raw)
        if not message:
            continue
        rows.append(annotate_message(message, contacts))
    rows.sort(key=lambda item: item.get("date") or 0, reverse=True)
    return rows


def fire_conversation_request(bus, device_id: str, thread_id: int, start: int, end: int) -> None:
    path = device_path(device_id)
    params = GLib.Variant("(xii)", (thread_id, start, end))

    def _finished(conn, result, *_args):
        try:
            conn.call_finish(result)
        except GLib.Error:
            pass

    bus.call(
        BUS_NAME,
        path,
        CONV_IFACE,
        "requestConversation",
        params,
        None,
        Gio.DBusCallFlags.NONE,
        12000,
        None,
        _finished,
        None,
    )


def collect_thread(bus, device_id: str, thread_id: int, start: int = 0, end: int = 12, wait_ms: int = 1600) -> list[dict]:
    path = device_path(device_id)
    messages: dict[int, dict] = {}
    loop = GLib.MainLoop()
    idle_id = {"id": 0}

    def quit_soon():
        if idle_id["id"]:
            GLib.source_remove(idle_id["id"])
        idle_id["id"] = GLib.timeout_add(250, loop.quit)

    def on_signal(_conn, _sender, _path, _iface, signal, params):
        if signal in ("conversationUpdated", "conversationCreated"):
            raw = params.unpack()[0]
            message = parse_message(raw)
            if message and int(message["threadId"]) == thread_id:
                key = int(message["id"])
                if key in messages or len(messages) < MAX_THREAD_MESSAGES:
                    messages[key] = message
                quit_soon()
        elif signal == "conversationLoaded":
            packed = params.unpack()
            loaded = packed[0] if packed else -1
            if int(loaded) == thread_id:
                quit_soon()

    bus.signal_subscribe(BUS_NAME, CONV_IFACE, None, path, None, Gio.DBusSignalFlags.NONE, on_signal)
    fire_conversation_request(bus, device_id, thread_id, start, end)
    GLib.timeout_add(wait_ms, loop.quit)
    loop.run()
    contacts = load_contacts(device_id)
    rows = [annotate_message(item, contacts) for item in sorted(messages.values(), key=lambda item: item.get("date") or 0)]
    if not rows:
        for item in active_conversations(bus, device_id):
            if int(item.get("threadId") or 0) == thread_id:
                rows = [item]
                break
    return rows


def cmd_conversations(args: list[str]) -> None:
    bus, device_id = require_device(args[0] if args else "")
    try:
        call(bus, device_path(device_id), CONV_IFACE, "requestAllConversationThreads", None, timeout_ms=200)
    except GLib.Error:
        try:
            call(bus, plugin_path(device_id, "sms"), SMS_IFACE, "requestAllConversations", None, timeout_ms=200)
        except GLib.Error:
            pass
    try:
        call(
            bus,
            plugin_path(device_id, "contacts"),
            "org.kde.kdeconnect.device.contacts",
            "synchronizeRemoteWithLocal",
            None,
            timeout_ms=200,
        )
    except GLib.Error:
        pass
    emit({"ok": True, "conversations": active_conversations(bus, device_id)})


def cmd_conversation(args: list[str]) -> None:
    if len(args) < 2:
        fail("Usage: conversation <device-id> <thread-id> [start] [end]")
    bus, device_id = require_device(args[0])
    try:
        thread_id = int(args[1])
        start = int(args[2]) if len(args) > 2 else 0
        end = int(args[3]) if len(args) > 3 else start + 12
    except ValueError:
        fail("Thread id, start, and end must be numbers")
    if end < start:
        end = start + 12
    rows = collect_thread(bus, device_id, thread_id, start, end)
    emit(
        {
            "ok": True,
            "threadId": thread_id,
            "messages": rows,
            "more": len(rows) >= max(1, end - start),
        }
    )


def cmd_sms_reply(args: list[str]) -> None:
    if len(args) < 3:
        fail("Usage: sms-reply <device-id> <thread-id> <text>")
    bus, device_id = require_device(args[0])
    try:
        thread_id = int(args[1])
    except ValueError:
        fail("Thread id must be a number")
    text = " ".join(args[2:]).strip()
    if not text:
        fail("Message is empty")
    try:
        call(
            bus,
            device_path(device_id),
            CONV_IFACE,
            "replyToConversation",
            GLib.Variant("(xsav)", (thread_id, text, [])),
        )
    except GLib.Error:
        call(
            bus,
            device_path(device_id),
            CONV_IFACE,
            "replyToConversation",
            GLib.Variant("(xs)", (thread_id, text)),
        )
    emit({"ok": True})


def cmd_sms_send(args: list[str]) -> None:
    if len(args) < 3:
        fail("Usage: sms-send <device-id> <number> <text>")
    bus, device_id = require_device(args[0])
    number = args[1].strip()
    text = " ".join(args[2:]).strip()
    if not number or not text:
        fail("Number and message are required")
    addresses = [GLib.Variant("(s)", (number,))]
    try:
        call(
            bus,
            device_path(device_id),
            CONV_IFACE,
            "sendWithoutConversation",
            GLib.Variant("(avsav)", (addresses, text, [])),
        )
    except GLib.Error:
        call(
            bus,
            plugin_path(device_id, "sms"),
            SMS_IFACE,
            "sendSms",
            GLib.Variant("(avsav)", (addresses, text, [])),
        )
    emit({"ok": True})


def cmd_sms_app(args: list[str]) -> None:
    bus, device_id = require_device(args[0] if args else "")
    try:
        call(bus, plugin_path(device_id, "sms"), SMS_IFACE, "launchApp", None)
    except GLib.Error:
        app = shutil.which("kdeconnect-sms")
        if not app:
            fail("kdeconnect-sms is not installed")
        subprocess.Popen(
            [app, "--device", clamp_id(device_id)],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    emit({"ok": True})
