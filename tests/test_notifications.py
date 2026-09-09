#!/usr/bin/python3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from connectlib.notice import is_sms_notification, parse_notification
from connectlib.notifications import notification_path
from connectlib.util import MAX_LABEL_CHARS, MAX_TEXT_CHARS


class NotificationsTest(unittest.TestCase):
    def test_notification_path_sanitizes_ids(self):
        path = notification_path("../dev", "../nid")
        last = path.rsplit("/", 1)[-1]
        self.assertNotIn("/", last)
        self.assertNotIn("..", last)
        self.assertEqual(notification_path("dev1", "1234").rsplit("/", 1)[-1], "1234")

    def test_parse_basic(self):
        item = parse_notification(
            "16",
            {
                "appName": "Wyze",
                "title": "Garage Door Is Closed",
                "text": "Garage Cam at 9:37 PM.",
                "ticker": "Garage Door Is Closed: Garage Cam at 9:37 PM.",
                "silent": True,
                "dismissable": True,
                "replyId": "",
                "isConversation": False,
                "hasIcon": True,
            },
        )
        self.assertEqual(item["id"], "16")
        self.assertEqual(item["appName"], "Wyze")
        self.assertEqual(item["title"], "Garage Door Is Closed")
        self.assertTrue(item["dismissable"])
        self.assertFalse(item["canReply"])

    def test_parse_replyable(self):
        item = parse_notification(
            "8",
            {
                "appName": "Messages",
                "title": "(707) 595-9859",
                "text": "Hello",
                "replyId": "a2555cb3-fbec-4634-a879-d8fb30044eb6",
                "isConversation": True,
                "dismissable": True,
            },
        )
        self.assertTrue(item["canReply"])
        self.assertTrue(item["isConversation"])
        self.assertEqual(item["replyId"], "a2555cb3-fbec-4634-a879-d8fb30044eb6")

    def test_parse_empty(self):
        item = parse_notification("1", {})
        self.assertEqual(item["id"], "1")
        self.assertEqual(item["title"], "")
        self.assertFalse(item["canReply"])

    def test_parse_clamps_remote_fields(self):
        item = parse_notification(
            "n" * 999,
            {
                "appName": "a" * 999,
                "title": "t" * 999,
                "text": "x" * (MAX_TEXT_CHARS + 100),
                "ticker": "k" * (MAX_TEXT_CHARS + 100),
                "replyId": "r" * 999,
            },
        )
        self.assertEqual(len(item["id"]), MAX_LABEL_CHARS)
        self.assertEqual(len(item["appName"]), MAX_LABEL_CHARS)
        self.assertEqual(len(item["title"]), MAX_LABEL_CHARS)
        self.assertEqual(len(item["text"]), MAX_TEXT_CHARS)
        self.assertEqual(len(item["ticker"]), MAX_TEXT_CHARS)
        self.assertEqual(len(item["replyId"]), MAX_LABEL_CHARS)
        self.assertTrue(item["canReply"])

    def test_sms_app_names(self):
        self.assertTrue(is_sms_notification({"appName": "Messages"}))
        self.assertTrue(is_sms_notification({"appName": "Google Messages"}))
        self.assertTrue(parse_notification("1", {"appName": "Messages"})["sms"])
        self.assertFalse(is_sms_notification({"appName": "WhatsApp"}))
        self.assertFalse(is_sms_notification({"appName": "Wyze"}))
        self.assertFalse(parse_notification("2", {"appName": "Wyze"})["sms"])


if __name__ == "__main__":
    unittest.main()
