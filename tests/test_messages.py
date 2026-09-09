#!/usr/bin/python3
import base64
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from connectlib.messages import (
    MAX_ATTACHMENTS,
    MAX_MESSAGE_BYTES,
    MAX_THUMB_BYTES,
    MAX_THUMB_CHARS,
    chip_label,
    parse_attachment,
    parse_attachments,
    parse_message,
    write_thumbnail,
)

TINY_PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="


class MessagesTest(unittest.TestCase):
    def test_parse_dict(self):
        message = parse_message(
            {
                "event": 1,
                "body": "hello",
                "addresses": ["+18015550100"],
                "date": 10,
                "type": 2,
                "read": 1,
                "threadId": 7,
                "id": 9,
                "fromMe": True,
                "attachmentCount": 0,
            }
        )
        self.assertEqual(message["body"], "hello")
        self.assertEqual(message["addresses"], ["+18015550100"])
        self.assertTrue(message["fromMe"])
        self.assertEqual(message["threadId"], 7)

    def test_parse_tuple_and_attachments(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = (
                0,
                "hi",
                [("+1",), ("+1",), "+2"],
                123,
                1,
                0,
                44,
                12,
                0,
                [
                    (190, "image/png", TINY_PNG, "PART_1_pic.png"),
                    (191, "application/pdf", "", "scan.pdf"),
                ],
            )
            message = parse_message(raw, Path(tmp))
            self.assertEqual(message["addresses"], ["+1", "+2"])
            self.assertFalse(message["fromMe"])
            self.assertEqual(message["attachmentCount"], 2)
            self.assertEqual(message["id"], 12)
            self.assertEqual(message["attachments"][0]["kind"], "image")
            self.assertTrue(message["attachments"][0]["thumb"].startswith("file:"))
            self.assertEqual(message["attachments"][1]["kind"], "file")
            self.assertEqual(message["attachments"][1]["label"], "scan.pdf")

    def test_chip_label(self):
        self.assertEqual(chip_label("image/jpeg", "PART_123_cat.jpg"), "cat.jpg")
        self.assertEqual(chip_label("application/pdf", ""), "PDF")
        self.assertEqual(chip_label("audio/mpeg", "voicenote.m4a"), "voicenote.m4a")

    def test_parse_attachment_dict(self):
        parsed = parse_attachment(
            {"part_id": 3, "mime_type": "video/mp4", "unique_identifier": "clip.mp4"},
            Path("/tmp"),
        )
        self.assertEqual(parsed["kind"], "file")
        self.assertEqual(parsed["label"], "clip.mp4")

    def test_parse_rejects_junk(self):
        self.assertIsNone(parse_message(None))
        self.assertIsNone(parse_message([1, 2, 3]))

    def test_thumbnail_rejects_invalid_base64(self):
        with tempfile.TemporaryDirectory() as tmp:
            for blob in ("not base64!!", "A", "AB=C", "===="):
                self.assertEqual(write_thumbnail("bad", blob, "image/png", Path(tmp)), "")
            self.assertFalse(list(Path(tmp).iterdir()))

    def test_thumbnail_accepts_whitespace(self):
        with tempfile.TemporaryDirectory() as tmp:
            wrapped = "\n".join(TINY_PNG[i : i + 4] for i in range(0, len(TINY_PNG), 4))
            self.assertTrue(write_thumbnail("ws", wrapped, "image/png", Path(tmp)).startswith("file:"))

    def test_thumbnail_rejects_oversized_encoded(self):
        with tempfile.TemporaryDirectory() as tmp:
            blob = "A" * (MAX_THUMB_CHARS + 1)
            self.assertEqual(write_thumbnail("huge", blob, "image/png", Path(tmp)), "")
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_thumbnail_rejects_oversized_decoded(self):
        with tempfile.TemporaryDirectory() as tmp:
            blob = base64.b64encode(os.urandom(700_000)).decode()
            self.assertLessEqual(len(blob), MAX_THUMB_CHARS)
            self.assertGreater(700_000, MAX_THUMB_BYTES)
            self.assertEqual(write_thumbnail("big", blob, "image/png", Path(tmp)), "")
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_thumbnail_replaces_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "thumbs"
            cache.mkdir()
            sentinel = Path(tmp) / "sentinel"
            sentinel.write_bytes(b"keep")
            target = cache / "pic.png"
            target.symlink_to(sentinel)
            self.assertTrue(write_thumbnail("pic", TINY_PNG, "image/png", cache).startswith("file:"))
            self.assertFalse(target.is_symlink())
            self.assertTrue(target.is_file())
            self.assertEqual(sentinel.read_bytes(), b"keep")

    def test_attachments_cap_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = [(i, "image/png", TINY_PNG, f"PART_{i}.png") for i in range(MAX_ATTACHMENTS + 4)]
            self.assertEqual(len(parse_attachments(raw, Path(tmp))), MAX_ATTACHMENTS)

    def test_attachments_aggregate_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            blob = base64.b64encode(b"a" * 450_000).decode()
            self.assertLess(450_000, MAX_THUMB_BYTES)
            self.assertGreater(5 * 450_000, MAX_MESSAGE_BYTES)
            raw = [(i, "image/png", blob, f"PART_{i}.png") for i in range(5)]
            rows = parse_attachments(raw, Path(tmp))
            self.assertEqual(len(rows), 5)
            self.assertEqual(sum(row["kind"] == "image" for row in rows), 4)


if __name__ == "__main__":
    unittest.main()
