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
    proc.pid = 999999
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
    @patch("connectlib.devices._wl_paste_path", return_value="/usr/bin/wl-paste")
    @patch("os.killpg")
    @patch("connectlib.devices.require_device")
    @patch("connectlib.devices.try_call", side_effect=GLib.Error("no plugin"))
    @patch("connectlib.devices.cmd_share_text")
    @patch("subprocess.Popen")
    def test_normal_clipboard_read(
        self, MockPopen, mock_share, mock_try, mock_req, mock_killpg, mock_wl_paste
    ):
        mock_req.return_value = ("bus", "dev1")
        MockPopen.return_value = _proc_with_output(b"hello world")

        from connectlib.devices import cmd_send_clipboard

        buf = io.StringIO()
        with redirect_stdout(buf):
            cmd_send_clipboard(["dev1"])

        mock_share.assert_called_once_with(["dev1", "hello world"])
        self.assertTrue(MockPopen.call_args.kwargs.get("start_new_session"))

    @patch("connectlib.devices._wl_paste_path", return_value="/usr/bin/wl-paste")
    @patch("os.killpg")
    @patch("connectlib.devices.require_device")
    @patch("connectlib.devices.try_call", side_effect=GLib.Error("no plugin"))
    @patch("subprocess.Popen")
    def test_oversized_clipboard_fails(
        self, MockPopen, mock_try, mock_req, mock_killpg, mock_wl_paste
    ):
        mock_req.return_value = ("bus", "dev1")
        MockPopen.return_value = _proc_with_output(b"x" * (MAX_CLIPBOARD_BYTES + 1))

        from connectlib.devices import cmd_send_clipboard

        with self.assertRaises(SystemExit):
            cmd_send_clipboard(["dev1"])
        mock_killpg.assert_called()

    @patch("connectlib.devices._wl_paste_path", return_value="/usr/bin/wl-paste")
    @patch("os.killpg")
    @patch("connectlib.devices.require_device")
    @patch("connectlib.devices.try_call", side_effect=GLib.Error("no plugin"))
    @patch("connectlib.devices.cmd_share_text")
    @patch("subprocess.Popen")
    def test_empty_clipboard_fails(
        self, MockPopen, mock_share, mock_try, mock_req, mock_killpg, mock_wl_paste
    ):
        mock_req.return_value = ("bus", "dev1")
        MockPopen.return_value = _proc_with_output(b"")

        from connectlib.devices import cmd_send_clipboard

        with self.assertRaises(SystemExit):
            cmd_send_clipboard(["dev1"])

    @patch("connectlib.devices._wl_paste_path", return_value="/usr/bin/wl-paste")
    @patch("os.killpg")
    @patch("connectlib.devices.select.select", return_value=([], [], []))
    @patch("connectlib.devices.require_device")
    @patch("connectlib.devices.try_call", side_effect=GLib.Error("no plugin"))
    @patch("subprocess.Popen")
    def test_clipboard_timeout_fails(
        self, MockPopen, mock_try, mock_req, mock_select, mock_killpg, mock_wl_paste
    ):
        mock_req.return_value = ("bus", "dev1")
        MockPopen.return_value = _proc_with_output(b"")

        from connectlib.devices import cmd_send_clipboard

        with self.assertRaises(SystemExit):
            cmd_send_clipboard(["dev1"])
        mock_killpg.assert_called()

    @patch("os.killpg")
    @patch("connectlib.devices.cmd_share_text")
    @patch("connectlib.devices.try_call", side_effect=GLib.Error("no plugin"))
    @patch("connectlib.devices.require_device")
    @patch("subprocess.Popen")
    def test_clipboard_without_wl_paste_fails(
        self, MockPopen, mock_req, mock_try, mock_share, mock_killpg
    ):
        mock_req.return_value = ("bus", "dev1")
        MockPopen.return_value = _proc_with_output(b"")

        from connectlib.devices import cmd_send_clipboard

        with patch("connectlib.devices._wl_paste_path", return_value=""):
            with self.assertRaises(SystemExit):
                cmd_send_clipboard(["dev1"])
        self.assertFalse(MockPopen.called)

    @patch("connectlib.devices._wl_paste_path", return_value="/usr/bin/wl-paste")
    @patch("os.killpg")
    @patch("connectlib.devices.require_device")
    @patch("connectlib.devices.try_call", side_effect=GLib.Error("no plugin"))
    @patch("connectlib.devices.cmd_share_text")
    @patch("subprocess.Popen")
    def test_fragment_then_stall_times_out(
        self, MockPopen, mock_share, mock_try, mock_req, mock_killpg, mock_wl_paste
    ):
        mock_req.return_value = ("bus", "dev1")
        rd, wr = os.pipe()
        os.write(wr, b"hi")
        proc = MagicMock()
        proc.stdout = os.fdopen(rd, "rb")
        proc.pid = 999999
        proc.returncode = 0
        MockPopen.return_value = proc
        calls = {"n": 0}

        def fake_select(rlist, _wlist, _xlist, _timeout):
            calls["n"] += 1
            if calls["n"] == 1:
                return (rlist, [], [])
            return ([], [], [])

        from connectlib.devices import cmd_send_clipboard

        buf = io.StringIO()
        with patch("connectlib.devices.select.select", side_effect=fake_select):
            with redirect_stdout(buf):
                with self.assertRaises(SystemExit):
                    cmd_send_clipboard(["dev1"])
        self.assertIn("Clipboard read timed out", buf.getvalue())
        mock_share.assert_not_called()
        mock_killpg.assert_called()
        os.close(wr)

    def test_timeout_and_byte_cap_constants(self):
        self.assertGreater(CLIPBOARD_TIMEOUT, 0)
        self.assertLessEqual(CLIPBOARD_TIMEOUT, 10)
        self.assertGreater(MAX_CLIPBOARD_BYTES, 0)
        self.assertLessEqual(MAX_CLIPBOARD_BYTES, 16 << 20)


if __name__ == "__main__":
    unittest.main()