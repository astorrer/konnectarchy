#!/usr/bin/python3
import io
import os
import sys
import threading
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import gi

gi.require_version("Gio", "2.0")
from gi.repository import GLib

from connectlib.devices import CLIPBOARD_TIMEOUT, MAX_CLIPBOARD_BYTES


def _proc_with_output(data: bytes) -> MagicMock:
    rd, wr = os.pipe()
    proc = MagicMock()
    proc.stdout = os.fdopen(rd, "rb")
    proc.returncode = 0

    def _write():
        try:
            for start in range(0, len(data), 8192):
                os.write(wr, data[start : start + 8192])
        except OSError:
            pass
        finally:
            try:
                os.close(wr)
            except OSError:
                pass

    threading.Thread(target=_write, daemon=True).start()
    return proc


class ClipboardBoundsTest(unittest.TestCase):
    @patch("connectlib.devices.require_device")
    @patch("connectlib.devices.try_call", side_effect=GLib.Error("no plugin"))
    @patch("connectlib.devices.cmd_share_text")
    @patch("subprocess.Popen")
    def test_normal_clipboard_read(self, MockPopen, mock_share, mock_try, mock_req):
        mock_req.return_value = ("bus", "dev1")
        MockPopen.return_value = _proc_with_output(b"hello world")

        from connectlib.devices import cmd_send_clipboard

        buf = io.StringIO()
        with redirect_stdout(buf):
            cmd_send_clipboard(["dev1"])

        mock_share.assert_called_once_with(["dev1", "hello world"])

    @patch("connectlib.devices.require_device")
    @patch("connectlib.devices.try_call", side_effect=GLib.Error("no plugin"))
    @patch("subprocess.Popen")
    def test_oversized_clipboard_fails(self, MockPopen, mock_try, mock_req):
        mock_req.return_value = ("bus", "dev1")
        MockPopen.return_value = _proc_with_output(b"x" * (MAX_CLIPBOARD_BYTES + 1))

        from connectlib.devices import cmd_send_clipboard

        with self.assertRaises(SystemExit):
            cmd_send_clipboard(["dev1"])
        MockPopen.return_value.kill.assert_called()

    @patch("connectlib.devices.require_device")
    @patch("connectlib.devices.try_call", side_effect=GLib.Error("no plugin"))
    @patch("connectlib.devices.cmd_share_text")
    @patch("subprocess.Popen")
    def test_empty_clipboard_fails(self, MockPopen, mock_share, mock_try, mock_req):
        mock_req.return_value = ("bus", "dev1")
        MockPopen.return_value = _proc_with_output(b"")

        from connectlib.devices import cmd_send_clipboard

        with self.assertRaises(SystemExit):
            cmd_send_clipboard(["dev1"])

    @patch("connectlib.devices.select.select", return_value=([], [], []))
    @patch("connectlib.devices.require_device")
    @patch("connectlib.devices.try_call", side_effect=GLib.Error("no plugin"))
    @patch("subprocess.Popen")
    def test_clipboard_timeout_fails(self, MockPopen, mock_try, mock_req, mock_select):
        mock_req.return_value = ("bus", "dev1")
        MockPopen.return_value = _proc_with_output(b"")

        from connectlib.devices import cmd_send_clipboard

        with self.assertRaises(SystemExit):
            cmd_send_clipboard(["dev1"])
        MockPopen.return_value.kill.assert_called()

    def test_timeout_and_byte_cap_constants(self):
        self.assertGreater(CLIPBOARD_TIMEOUT, 0)
        self.assertLessEqual(CLIPBOARD_TIMEOUT, 10)
        self.assertGreater(MAX_CLIPBOARD_BYTES, 0)
        self.assertLessEqual(MAX_CLIPBOARD_BYTES, 16 << 20)


if __name__ == "__main__":
    unittest.main()