#!/usr/bin/python3
import base64
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from connectlib.bound import (
    B64_CHUNK,
    MAX_ADDRESSES,
    MAX_ATTACHMENTS,
    MAX_CONTACT_BYTES,
    MAX_CONTACT_FIELDS,
    MAX_CONTACTS,
    MAX_CONVERSATIONS,
    MAX_DEVICES,
    MAX_EMIT_BYTES,
    MAX_ID_CHARS,
    MAX_LABEL_CHARS,
    MAX_MESSAGE_BYTES,
    MAX_NOTIFICATIONS,
    MAX_PLAYERS,
    MAX_PLUGINS,
    MAX_SAFE_INT,
    MAX_SCAN_ENTRIES,
    MAX_TEXT_CHARS,
    MAX_THREAD_MESSAGES,
    MAX_THUMB_BYTES,
    MAX_THUMB_CHARS,
    MAX_VCARD_CHARS,
    Budget,
    b64_decode,
    flag,
    ident,
    label,
    mapping,
    num,
    read_file,
    read_scanned,
    scan_dir,
    strings,
    text,
)


class BoundConstantsTest(unittest.TestCase):
    def test_values(self):
        self.assertEqual(MAX_TEXT_CHARS, 4096)
        self.assertEqual(MAX_LABEL_CHARS, 256)
        self.assertEqual(MAX_ID_CHARS, 64)
        self.assertEqual(MAX_EMIT_BYTES, 4 << 20)
        self.assertEqual(MAX_DEVICES, 32)
        self.assertEqual(MAX_PLUGINS, 64)
        self.assertEqual(MAX_NOTIFICATIONS, 128)
        self.assertEqual(MAX_PLAYERS, 32)
        self.assertEqual(MAX_CONVERSATIONS, 256)
        self.assertEqual(MAX_THREAD_MESSAGES, 256)
        self.assertEqual(MAX_CONTACTS, 512)
        self.assertEqual(MAX_CONTACT_FIELDS, 16)
        self.assertEqual(MAX_CONTACT_BYTES, 8 << 20)
        self.assertEqual(MAX_SCAN_ENTRIES, 2048)
        self.assertEqual(MAX_VCARD_CHARS, 1 << 20)
        self.assertEqual(MAX_ATTACHMENTS, 16)
        self.assertEqual(MAX_ADDRESSES, 32)
        self.assertEqual(MAX_THUMB_CHARS, 1 << 20)
        self.assertEqual(MAX_THUMB_BYTES, 1 << 19)
        self.assertEqual(MAX_MESSAGE_BYTES, 1 << 21)
        self.assertEqual(B64_CHUNK, 4096)
        self.assertEqual(MAX_SAFE_INT, 2**53 - 1)


class BoundTextTest(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(text("hello"), "hello")
        self.assertEqual(text(None), "")
        self.assertEqual(text(0), "")
        self.assertEqual(text(123), "123")
        self.assertEqual(text(3.14), "3.14")
        self.assertEqual(text("x" * 9999), "x" * 4096)
        self.assertEqual(text("abc", 2), "ab")
        self.assertEqual(text("", 5), "")

    def test_giant_string(self):
        big = "a" * 100_000
        self.assertEqual(len(text(big)), 4096)

    def test_weird_types(self):
        self.assertEqual(text([1, 2]), "[1, 2]")
        self.assertEqual(text({"a": 1}), "{'a': 1}")


class BoundLabelTest(unittest.TestCase):
    def test_limits(self):
        self.assertEqual(label("hello"), "hello")
        self.assertEqual(len(label("x" * 9999)), 256)
        self.assertEqual(label(None), "")


class BoundIdentTest(unittest.TestCase):
    def test_delegates_to_clamp_id(self):
        self.assertEqual(ident("safe-id"), "safe-id")
        self.assertEqual(ident("../escape"), "escape")
        self.assertEqual(len(ident("x" * 200)), 64)


class BoundNumTest(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(num(" 42 "), 42)
        self.assertEqual(num(7), 7)
        self.assertEqual(num(0), 0)
        self.assertEqual(num(None), 0)
        self.assertEqual(num(None, 5), 5)
        self.assertEqual(num("abc", -1), -1)

    def test_clamps_to_max_safe_int(self):
        self.assertEqual(num(2**53), MAX_SAFE_INT)
        self.assertEqual(num(-(2**53)), -MAX_SAFE_INT)
        self.assertEqual(num(2**60), MAX_SAFE_INT)
        self.assertEqual(num(1.9), 1)
        self.assertEqual(num(float("inf")), 0)

    def test_weird_types(self):
        self.assertEqual(num(object(), 42), 42)
        self.assertEqual(num("xyz"), 0)
        self.assertEqual(num("xyz", 10), 10)

    def test_negative_values(self):
        self.assertEqual(num(-5), -5)
        self.assertEqual(num("-100"), -100)
        self.assertEqual(num("-" + "9" * 60), -MAX_SAFE_INT)


class BoundFlagTest(unittest.TestCase):
    def test_coercion(self):
        self.assertTrue(flag(1))
        self.assertTrue(flag("yes"))
        self.assertTrue(flag([1]))
        self.assertFalse(flag(0))
        self.assertFalse(flag(""))
        self.assertFalse(flag(None))


class BoundStringsTest(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(strings(["a", "b", "c"], 2), ["a", "b"])
        self.assertEqual(strings(["x", "y", "z"], 10), ["x", "y", "z"])
        self.assertEqual(strings(None, 5), [])
        self.assertEqual(strings("notalist", 5), [])
        self.assertEqual(strings(42, 5), [])

    def test_non_str_items(self):
        self.assertEqual(strings([1, None, [3]], 5), ["1", "None", "[3]"])

    def test_each_limit(self):
        self.assertEqual(strings(["abcdef"], 5, each_limit=3), ["abc"])

    def test_giant_list(self):
        big = [str(i) for i in range(10_000)]
        self.assertEqual(len(strings(big, 100)), 100)

    def test_tuple_accepted(self):
        self.assertEqual(strings(("a", "b"), 5), ["a", "b"])


class BoundMappingTest(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(mapping({"a": 1, "b": 2}, 1), {"a": 1})
        self.assertEqual(mapping({"a": 1}, 10), {"a": 1})
        self.assertEqual(mapping(None, 5), {})
        self.assertEqual(mapping("bad", 5), {})
        self.assertEqual(mapping(42, 5), {})

    def test_non_str_keys(self):
        d = {1: "a", "ok": "b", 3.0: "c"}
        self.assertEqual(mapping(d, 10), {"ok": "b"})

    def test_entry_limit(self):
        d = {str(i): i for i in range(1000)}
        result = mapping(d, 3)
        self.assertEqual(len(result), 3)

    def test_empty(self):
        self.assertEqual(mapping({}, 5), {})


class BoundBudgetTest(unittest.TestCase):
    def test_spend_within(self):
        b = Budget(10)
        self.assertTrue(b.spend(5))
        self.assertEqual(b.used, 5)
        self.assertTrue(b.spend(5))
        self.assertEqual(b.used, 10)
        self.assertFalse(b.spend(1))
        self.assertEqual(b.used, 10)

    def test_spend_at_exact_capacity(self):
        b = Budget(3)
        self.assertTrue(b.spend(3))
        self.assertTrue(b.spend(0))
        self.assertFalse(b.spend(1))
        self.assertEqual(b.used, 3)

    def test_spend_over(self):
        b = Budget(5)
        self.assertFalse(b.spend(6))
        self.assertEqual(b.used, 0)

    def test_negative_rejected(self):
        b = Budget(10)
        self.assertFalse(b.spend(-1))
        self.assertEqual(b.used, 0)

    def test_zero_capacity(self):
        b = Budget(0)
        self.assertTrue(b.spend(0))
        self.assertFalse(b.spend(1))


class BoundScanDirTest(unittest.TestCase):
    def test_regular_files(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ("a.txt", "b.txt", "c.log"):
                Path(d, name).write_text("x")
            result = scan_dir(d, ".txt", 100)
            names = {e[0] for e in result}
            self.assertEqual(names, {"a.txt", "b.txt"})
            self.assertNotIn("c.log", names)

    def test_budget_enforced(self):
        with tempfile.TemporaryDirectory() as d:
            for i in range(10):
                Path(d, f"f{i}.txt").write_text("x")
            result = scan_dir(d, ".txt", 3)
            self.assertEqual(len(result), 3)

    def test_symlink_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "real.txt").write_text("data")
            os.symlink(Path(d, "real.txt"), Path(d, "link.txt"))
            result = scan_dir(d, ".txt", 100)
            names = {e[0] for e in result}
            self.assertNotIn("link.txt", names)
            self.assertIn("real.txt", names)

    def test_directory_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            os.mkdir(Path(d, "subdir.txt"))
            Path(d, "file.txt").write_text("x")
            result = scan_dir(d, ".txt", 100)
            names = {e[0] for e in result}
            self.assertNotIn("subdir.txt", names)
            self.assertIn("file.txt", names)

    def test_missing_dir(self):
        self.assertEqual(scan_dir("/nonexistent", ".txt", 10), [])

    def test_tuple_contents(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d, "hello.txt")
            p.write_text("abc")
            result = scan_dir(d, ".txt", 10)
            self.assertEqual(len(result), 1)
            name, path, size, mtime, dev, ino, uid, mode = result[0]
            self.assertEqual(name, "hello.txt")
            self.assertEqual(path, str(p))
            self.assertEqual(size, 3)
            self.assertIsInstance(mtime, int)
            self.assertIsInstance(dev, int)
            self.assertIsInstance(ino, int)
            self.assertIsInstance(uid, int)
            self.assertTrue(stat.S_ISREG(mode))

    def test_budget_counts_total_entries_not_matches(self):
        from types import SimpleNamespace
        from unittest.mock import patch

        def entry(name):
            return SimpleNamespace(
                name=name,
                is_file=lambda **kwargs: True,
                stat=lambda **kwargs: SimpleNamespace(
                    st_size=1,
                    st_mtime_ns=2,
                    st_dev=0,
                    st_ino=0,
                    st_uid=0,
                    st_mode=0o100644,
                ),
            )

        class FakeScandir:
            def __init__(self, entries):
                self._entries = entries

            def __iter__(self):
                return iter(self._entries)

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

        order = [entry(f"junk{i}.log") for i in range(5)] + [entry("real.txt")]
        with patch("os.scandir", return_value=FakeScandir(order)):
            result = scan_dir("/x", ".txt", 3)
        self.assertEqual(result, [])

    def test_permission_error(self):
        with tempfile.TemporaryDirectory() as d:
            for i in range(5):
                Path(d, f"f{i}.txt").write_text("x")
            result = scan_dir(d, ".txt", 2)
            self.assertEqual(len(result), 2)


class BoundReadFileTest(unittest.TestCase):
    def test_exists(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d, "t.txt")
            p.write_text("hello")
            b = Budget(1000)
            result = read_file(str(p), 100, b)
            self.assertIsNotNone(result)
            text_, over = result
            self.assertEqual(text_, "hello")
            self.assertFalse(over)

    def test_oversized_chars(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d, "t.txt")
            p.write_text("abcdef")
            b = Budget(1000)
            result = read_file(str(p), 3, b)
            self.assertEqual(result[0], "abc")
            self.assertEqual(len(result[0]), 3)

    def test_budget_exhausted(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d, "t.txt")
            p.write_text("abc")
            b = Budget(2)
            result = read_file(str(p), 100, b)
            self.assertIsNotNone(result)
            self.assertTrue(result[1])

    def test_missing_file(self):
        b = Budget(100)
        self.assertIsNone(read_file("/nonexistent/file.txt", 100, b))

    def test_binary_content(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d, "bin.txt")
            p.write_bytes(b"\xff\x00\xfe\xab")
            b = Budget(1000)
            result = read_file(str(p), 100, b)
            self.assertIsNotNone(result)
            self.assertIn("\ufffd", result[0])

    def test_utf8(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d, "t.txt")
            p.write_text("héllo wörld", encoding="utf-8")
            b = Budget(1000)
            result = read_file(str(p), 100, b)
            self.assertEqual(result[0], "héllo wörld")


class BoundReadScannedTest(unittest.TestCase):
    def _scan_one(self, d, name="card.txt"):
        return scan_dir(d, ".txt", 100)[0]

    def _budget(self):
        return Budget(1 << 20)

    def test_matches_identity(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d, "card.txt")
            p.write_text("hello")
            entry = self._scan_one(d)
            result = read_scanned(d, entry, 100, self._budget())
            self.assertIsNotNone(result)
            self.assertEqual(result[0], "hello")

    def test_rejects_symlink_swap_before_read(self):
        with tempfile.TemporaryDirectory() as d:
            victim = Path(d, "victim.txt")
            victim.write_text("BEGIN:VCARD\nFN:Victim\nEND:VCARD\n")
            p = Path(d, "card.txt")
            p.write_text("BEGIN:VCARD\nFN:Real\nEND:VCARD\n")
            entry = self._scan_one(d)
            p.unlink()
            os.symlink(victim, p)
            result = read_scanned(d, entry, 100, self._budget())
            self.assertIsNone(result)

    def test_rejects_replaced_regular_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d, "card.txt")
            p.write_text("BEGIN:VCARD\nFN:Real\nEND:VCARD\n")
            entry = self._scan_one(d)
            p.unlink()
            p.write_text("BEGIN:VCARD\nFN:Impostor\nEND:VCARD\n")
            result = read_scanned(d, entry, 100, self._budget())
            self.assertIsNone(result)

    def test_rejects_resized_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d, "card.txt")
            p.write_text("abcdef")
            entry = self._scan_one(d)
            p.write_text("ab")
            result = read_scanned(d, entry, 100, self._budget())
            self.assertIsNone(result)

    def test_missing_entry(self):
        with tempfile.TemporaryDirectory() as d:
            entry = ("ghost.txt", "/x/ghost.txt", 3, 0, 0, 0, 0, 0o100644)
            self.assertIsNone(read_scanned(d, entry, 100, self._budget()))

    def test_missing_dir(self):
        entry = ("card.txt", "/nonexistent/card.txt", 3, 0, 0, 0, 0, 0o100644)
        self.assertIsNone(read_scanned("/nonexistent", entry, 100, self._budget()))

    def test_caps_read(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d, "card.txt")
            p.write_text("abcdef")
            entry = self._scan_one(d)
            result = read_scanned(d, entry, 3, self._budget())
            self.assertEqual(result[0], "abc")

    def test_budget_exhausted(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d, "card.txt")
            p.write_text("abc")
            entry = self._scan_one(d)
            result = read_scanned(d, entry, 100, Budget(2))
            self.assertIsNotNone(result)
            self.assertTrue(result[1])


class BoundB64DecodeTest(unittest.TestCase):
    def test_roundtrip(self):
        data = b"hello world"
        enc = base64.b64encode(data).decode()
        self.assertEqual(b64_decode(enc, 100), data)

    def test_whitespace(self):
        enc = base64.b64encode(b"test").decode()
        spaced = enc[0] + " " + enc[1:] + "\n"
        self.assertEqual(b64_decode(spaced, 100), b"test")

    def test_empty(self):
        self.assertIsNone(b64_decode("", 10))
        self.assertIsNone(b64_decode(None, 10))

    def test_len_mod4_eq1_rejected(self):
        self.assertIsNone(b64_decode("Y", 10))
        self.assertIsNone(b64_decode("YQ===", 10))

    def test_bad_chars(self):
        self.assertIsNone(b64_decode("YQ!!", 10))
        self.assertIsNone(b64_decode("abc_def", 10))

    def test_oversized_early_exit(self):
        enc = base64.b64encode(b"abc").decode()
        self.assertIsNone(b64_decode(enc, 1))

    def test_budget_applied(self):
        enc = base64.b64encode(b"hello").decode()
        b = Budget(2)
        self.assertIsNone(b64_decode(enc, 1000, budget=b))
        self.assertEqual(b.used, 0)

    def test_chunking(self):
        data = bytes(range(256)) * 20
        enc = base64.b64encode(data).decode()
        self.assertEqual(len(enc), (len(data) + 2) // 3 * 4)
        self.assertEqual(b64_decode(enc, len(data) + 100), data)

    def test_chunking_budget_across_chunks(self):
        data = b"A" * 6000
        enc = base64.b64encode(data).decode()
        b = Budget(5000)
        result = b64_decode(enc, len(data) + 100, budget=b)
        self.assertIsNone(result)

    def test_valid_no_padding_needed(self):
        enc = base64.b64encode(b"ab").decode()
        self.assertEqual(enc, "YWI=")
        self.assertEqual(b64_decode(enc, 100), b"ab")

    def test_two_pad_chars(self):
        self.assertEqual(b64_decode("YQ==", 10), b"a")


if __name__ == "__main__":
    unittest.main()
