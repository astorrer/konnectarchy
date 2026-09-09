from __future__ import annotations

import sys

import gi

gi.require_version("Gio", "2.0")
from gi.repository import GLib

from .contacts import cmd_contacts
from .daemon import cmd_autostart, cmd_start, cmd_status, cmd_stop
from .devices import (
    cmd_accept,
    cmd_pair,
    cmd_ping,
    cmd_reject,
    cmd_ring,
    cmd_send_clipboard,
    cmd_share_file,
    cmd_share_text,
    cmd_unpair,
)
from .media import cmd_media, cmd_media_action
from .notifications import (
    cmd_notification_dismiss,
    cmd_notification_reply,
    cmd_notifications,
)
from .sms import (
    cmd_conversation,
    cmd_conversations,
    cmd_sms_app,
    cmd_sms_reply,
    cmd_sms_send,
)
from .util import clamp_str, fail

COMMANDS = {
    "status": cmd_status,
    "start": cmd_start,
    "stop": cmd_stop,
    "ping": cmd_ping,
    "ring": cmd_ring,
    "pair": cmd_pair,
    "unpair": cmd_unpair,
    "accept": cmd_accept,
    "reject": cmd_reject,
    "share-file": cmd_share_file,
    "share-text": cmd_share_text,
    "send-clipboard": cmd_send_clipboard,
    "conversations": cmd_conversations,
    "conversation": cmd_conversation,
    "sms-reply": cmd_sms_reply,
    "sms-send": cmd_sms_send,
    "sms-app": cmd_sms_app,
    "contacts": cmd_contacts,
    "notifications": cmd_notifications,
    "notification-dismiss": cmd_notification_dismiss,
    "notification-reply": cmd_notification_reply,
    "media": cmd_media,
    "media-action": cmd_media_action,
    "autostart": cmd_autostart,
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        sys.stderr.write("Usage: connect.py <command> [args...]\n")
        sys.stderr.write("Commands: " + ", ".join(COMMANDS) + "\n")
        raise SystemExit(2)
    command = sys.argv[1]
    handler = COMMANDS.get(command)
    if handler is None:
        fail(f"Unknown command: {command}")
    try:
        handler(sys.argv[2:])
    except GLib.Error as error:
        fail(clamp_str(error.message))
