#!/usr/bin/python3
import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from connectlib.util import MAX_EMIT_BYTES, MAX_LABEL_CHARS, clamp_list, clamp_str, emit


class UtilTest(unittest.TestCase):
    def test_clamp_str(self):
        self.assertEqual(clamp_str(None), "")
        self.assertEqual(clamp_str(0), "")
        self.assertEqual(clamp_str("abc"), "abc")
        self.assertEqual(clamp_str("abcdef", 3), "abc")
        self.assertEqual(len(clamp_str("x" * 999)), MAX_LABEL_CHARS)

    def test_clamp_list(self):
        self.assertEqual(clamp_list(None, 3), [])
        self.assertEqual(clamp_list("abc", 3), [])
        self.assertEqual(clamp_list({"a": 1}, 3), [])
        self.assertEqual(clamp_list([1, 2, 3, 4], 3), [1, 2, 3])
        self.assertEqual(clamp_list((1, 2), 3), [1, 2])

    def test_emit_round_trip(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            emit({"ok": True, "value": "héllo"})
        parsed = json.loads(buf.getvalue())
        self.assertTrue(parsed["ok"])
        self.assertEqual(parsed["value"], "héllo")

    def test_emit_rejects_oversized_payload(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            emit({"ok": True, "blob": "a" * (MAX_EMIT_BYTES + 1)})
        out = buf.getvalue()
        self.assertLess(len(out), 200)
        parsed = json.loads(out)
        self.assertFalse(parsed["ok"])
        self.assertIn("budget", parsed["error"])


if __name__ == "__main__":
    unittest.main()
