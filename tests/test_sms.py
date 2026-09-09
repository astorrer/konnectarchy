#!/usr/bin/python3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import connectlib.sms as sms


def tuple_message(mid, thread_id=7, body="hi"):
    return (0, body, [(f"+18015{mid:06d}",)], 1000 + mid, 1, 0, thread_id, mid, 0, [])


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def unpack(self):
        return (self._rows,)


class Params:
    def __init__(self, raw):
        self._raw = raw

    def unpack(self):
        return (self._raw,)


class SignalBus:
    def __init__(self, raws):
        self._raws = raws
        self._handler = None

    def signal_subscribe(self, *args):
        self._handler = args[-1]

    def call(self, *args):
        for raw in self._raws:
            self._handler(None, None, None, None, "conversationUpdated", Params(raw))


class SmsTest(unittest.TestCase):
    def setUp(self):
        self._orig = (sms.call, sms.load_contacts)

    def tearDown(self):
        sms.call, sms.load_contacts = self._orig

    def test_conversations_row_cap(self):
        rows_in = [tuple_message(i, thread_id=i) for i in range(sms.MAX_CONVERSATIONS + 40)]
        sms.call = lambda *a, **k: FakeResult(rows_in)
        sms.load_contacts = lambda device_id: []
        rows = sms.active_conversations(None, "dev")
        self.assertEqual(len(rows), sms.MAX_CONVERSATIONS)

    def test_thread_accumulation_cap(self):
        bus = SignalBus([tuple_message(i) for i in range(sms.MAX_THREAD_MESSAGES + 50)])
        sms.load_contacts = lambda device_id: []
        rows = sms.collect_thread(bus, "dev", 7, wait_ms=50)
        self.assertEqual(len(rows), sms.MAX_THREAD_MESSAGES)

    def test_thread_update_still_lands_at_cap(self):
        raws = [tuple_message(i) for i in range(sms.MAX_THREAD_MESSAGES + 10)]
        raws.append(tuple_message(0, body="edited"))
        bus = SignalBus(raws)
        sms.load_contacts = lambda device_id: []
        rows = sms.collect_thread(bus, "dev", 7, wait_ms=50)
        self.assertEqual(len(rows), sms.MAX_THREAD_MESSAGES)
        by_id = {row["id"]: row for row in rows}
        self.assertEqual(by_id[0]["body"], "edited")


if __name__ == "__main__":
    unittest.main()
