#!/usr/bin/python3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import connectlib.devices as devices
import connectlib.media as media


def props(**overrides):
    base = {
        "player": "player1",
        "playerList": ["player1", "player2"],
        "title": "Song",
        "artist": "Artist",
        "album": "Album",
        "isPlaying": True,
        "position": 30,
        "length": 200,
        "volume": 50,
        "canSeek": True,
    }
    base.update(overrides)
    return base


class MediaTest(unittest.TestCase):
    def setUp(self):
        self._orig_media = (media.get_prop, media.unpack_string_list)
        self._orig_require = devices.require_device

    def tearDown(self):
        media.get_prop, media.unpack_string_list = self._orig_media
        devices.require_device = self._orig_require

    def _patch(self, values):
        media.get_prop = lambda bus, path, iface, name, default=None: values.get(name, default)
        media.unpack_string_list = lambda raw: list(raw or [])

    def test_read_media_playing(self):
        self._patch(props())
        row = media.read_media(None, "d")
        self.assertTrue(row["hasMedia"])
        self.assertTrue(row["isPlaying"])
        self.assertEqual(row["players"], ["player1", "player2"])
        self.assertEqual(row["position"], 30)

    def test_read_media_idle(self):
        self._patch(props(title="", artist="", album="", isPlaying=False))
        row = media.read_media(None, "d")
        self.assertFalse(row["hasMedia"])

    def test_read_media_bad_props(self):
        self._patch({})
        self.assertIsNone(media.read_media(None, "d"))

    def test_read_media_clamps_remote_fields(self):
        from connectlib.util import MAX_LABEL_CHARS

        self._patch(
            props(
                title="t" * 999,
                artist="a" * 999,
                album="b" * 999,
                player="p" * 999,
                playerList=[f"p{i}" for i in range(media.MAX_PLAYERS + 10)],
            )
        )
        row = media.read_media(None, "d")
        self.assertEqual(len(row["title"]), MAX_LABEL_CHARS)
        self.assertEqual(len(row["artist"]), MAX_LABEL_CHARS)
        self.assertEqual(len(row["album"]), MAX_LABEL_CHARS)
        self.assertEqual(len(row["player"]), MAX_LABEL_CHARS)
        self.assertEqual(len(row["players"]), media.MAX_PLAYERS)

    def test_read_media_coerces_defaults(self):
        self._patch(props(position="x", length=None, volume=3.5, canSeek=1))
        row = media.read_media(None, "d")
        self.assertEqual(row["position"], 0)
        self.assertEqual(row["length"], 0)
        self.assertEqual(row["volume"], 0)
        self.assertFalse(row["canSeek"])

    def _run_action(self, args):
        devices.require_device = lambda device_id: (None, device_id)
        sent = []
        media.send_action = lambda bus, device_id, action: sent.append(action)
        media.cmd_media_action(args)
        return sent

    def test_action_mapping(self):
        for word, mpris in (
            ("play", "Play"),
            ("pause", "Pause"),
            ("toggle", "PlayPause"),
            ("next", "Next"),
            ("previous", "Previous"),
            ("stop", "Stop"),
        ):
            self.assertEqual(self._run_action(["d", word]), [mpris])

    def test_action_rejects_unknown(self):
        with self.assertRaises(SystemExit):
            devices.require_device = lambda device_id: (None, device_id)
            media.cmd_media_action(["d", "rewind"])


if __name__ == "__main__":
    unittest.main()
