#!/usr/bin/python3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from connectlib import contacts
from connectlib.util import MAX_LABEL_CHARS


class ContactsTest(unittest.TestCase):
    def test_canonicalize_and_match(self):
        self.assertEqual(contacts.canonicalize_phone("+1-801-865-8491"), "18018658491")
        self.assertEqual(contacts.canonicalize_phone("+18018658491"), "18018658491")
        self.assertTrue(contacts.phones_match("+18018658491", "801-865-8491"))
        self.assertTrue(contacts.phones_match("2708505320", "+1-270-850-5320"))
        self.assertFalse(contacts.phones_match("64241", "+18018658491"))
        self.assertFalse(contacts.phones_match("", "8018658491"))

    def test_parse_vcard(self):
        card = """BEGIN:VCARD
VERSION:2.1
N:Storrer;Gabby;;;
FN:Gabby Storrer
TEL;CELL:+1-801-865-8491
EMAIL;HOME:gabby@example.com
END:VCARD
"""
        parsed = contacts.parse_vcard(card)
        self.assertEqual(parsed["name"], "Gabby Storrer")
        self.assertEqual(parsed["phones"], ["+1-801-865-8491"])
        self.assertEqual(parsed["emails"], ["gabby@example.com"])

    def test_parse_vcard_skips_photo_and_uses_n(self):
        card = """BEGIN:VCARD
VERSION:2.1
N:Fisher;Daryl;;;
TEL;CELL:+1-253-985-7807
PHOTO;ENCODING=BASE64;JPEG:/9j/4AAQ
 SkZJRgABAQAAAQABAAD
END:VCARD
"""
        parsed = contacts.parse_vcard(card)
        self.assertEqual(parsed["name"], "Daryl Fisher")
        self.assertEqual(parsed["phones"], ["+1-253-985-7807"])

    def test_quoted_printable_name(self):
        card = "BEGIN:VCARD\nFN;ENCODING=QUOTED-PRINTABLE:Caf=C3=A9\nTEL:+1-801-555-0100\nEND:VCARD\n"
        parsed = contacts.parse_vcard(card)
        self.assertEqual(parsed["name"], "Café")

    def test_parse_vcard_caps_fields(self):
        lines = ["BEGIN:VCARD", "FN:" + "N" * 999]
        lines += [f"TEL:+1801555{i:04d}" for i in range(contacts.MAX_CONTACT_FIELDS + 10)]
        lines += [f"EMAIL:user{i}@example.com" for i in range(contacts.MAX_CONTACT_FIELDS + 10)]
        lines.append("END:VCARD")
        parsed = contacts.parse_vcard("\n".join(lines))
        self.assertEqual(len(parsed["name"]), MAX_LABEL_CHARS)
        self.assertEqual(len(parsed["phones"]), contacts.MAX_CONTACT_FIELDS)
        self.assertEqual(len(parsed["emails"]), contacts.MAX_CONTACT_FIELDS)

    def test_load_caps_file_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "kdeconnect-cap"
            folder.mkdir()
            filler = "NOTE:" + "x" * contacts.MAX_VCARD_CHARS + "\n"
            (folder / "big.vcf").write_text(
                "BEGIN:VCARD\nFN:Early Name\n" + filler + "TEL:+18015550100\nEND:VCARD\n",
                encoding="utf-8",
            )
            loaded = contacts.load_contacts("cap", root)
            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0]["name"], "Early Name")
            self.assertEqual(loaded[0]["phones"], [])

    def test_load_and_title(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "kdeconnect-dev"
            folder.mkdir()
            (folder / "one.vcf").write_text(
                "BEGIN:VCARD\nFN:Gabby Storrer\nTEL;CELL:+1-801-865-8491\nEND:VCARD\n",
                encoding="utf-8",
            )
            (folder / "two.vcf").write_text(
                "BEGIN:VCARD\nFN:Caroline Storrer\nTEL;CELL:+1-252-619-8608\nEND:VCARD\n",
                encoding="utf-8",
            )
            loaded = contacts.load_contacts("dev", root)
            self.assertEqual(len(loaded), 2)
            message = {
                "addresses": ["+18018658491", "+12526198608", "64241"],
            }
            titled = contacts.annotate_message(dict(message), loaded)
            self.assertEqual(titled["title"], "Gabby Storrer, Caroline Storrer, 64241")
            self.assertEqual(titled["names"], ["Gabby Storrer", "Caroline Storrer", "64241"])
            unknown = contacts.conversation_title({"addresses": ["+15555550100"]}, loaded)
            self.assertEqual(unknown, "+15555550100")
            self.assertEqual(contacts.conversation_title({"addresses": []}), "Unknown")
            packed = contacts.serialize_contacts(loaded)
            self.assertEqual(packed[0]["name"], "Caroline Storrer")
            self.assertEqual(packed[0]["phone"], "+1-252-619-8608")
            self.assertEqual(contacts.serialize_contacts([{"name": "No phone", "phones": []}]), [])


if __name__ == "__main__":
    unittest.main()
