from __future__ import annotations

import quopri
from pathlib import Path

from . import bound

VCARDS_ROOT = Path.home() / ".local" / "share" / "kpeoplevcard"
_CONTACTS_CACHE: dict[str, tuple[tuple[int, int], list[dict]]] = {}


def canonicalize_phone(number: str) -> str:
    text = str(number or "")
    stripped = (
        text.replace(" ", "")
        .replace("-", "")
        .replace("(", "")
        .replace(")", "")
        .replace("+", "")
        .lstrip("0")
    )
    return stripped or text


def phones_match(left: str, right: str) -> bool:
    first = canonicalize_phone(left)
    second = canonicalize_phone(right)
    if not first or not second:
        return False
    longer, shorter = (first, second) if len(first) >= len(second) else (second, first)
    if len(shorter) <= 6 and len(longer) > 6:
        return False
    return longer.endswith(shorter)


def _unescape_vcard(value: str) -> str:
    return (
        value.replace("\\n", "\n")
        .replace("\\N", "\n")
        .replace("\\,", ",")
        .replace("\\;", ";")
        .replace("\\\\", "\\")
    )


def _decode_vcard_value(key: str, value: str) -> str:
    params = [part.strip().upper() for part in key.split(";")[1:]]
    if "QUOTED-PRINTABLE" in params or any(part.startswith("ENCODING=QUOTED-PRINTABLE") for part in params):
        try:
            value = quopri.decodestring(value.encode("utf-8", errors="replace")).decode("utf-8", errors="replace")
        except Exception:
            pass
    return _unescape_vcard(value).strip()


def iter_vcard_fields(text: str):
    buf = None
    for raw in str(text or "").splitlines():
        if raw.startswith((" ", "\t")):
            if buf is not None:
                buf += raw[1:]
            continue
        if buf is not None:
            yield buf
        buf = raw
    if buf is not None:
        yield buf


def parse_vcard(text: str) -> dict | None:
    name = ""
    structured = ""
    phones: list[str] = []
    emails: list[str] = []
    for line in iter_vcard_fields(text):
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        prop = key.split(";", 1)[0].upper()
        if prop == "PHOTO":
            continue
        decoded = bound.label(_decode_vcard_value(key, value))
        if not decoded:
            continue
        if prop == "FN":
            name = decoded
        elif prop == "N" and not structured:
            parts = [_unescape_vcard(part) for part in decoded.split(";")]
            given = parts[1].strip() if len(parts) > 1 else ""
            family = parts[0].strip() if parts else ""
            structured = " ".join(part for part in (given, family) if part)
        elif prop == "TEL":
            if decoded not in phones and len(phones) < MAX_CONTACT_FIELDS:
                phones.append(decoded)
        elif prop == "EMAIL":
            if decoded not in emails and len(emails) < MAX_CONTACT_FIELDS:
                emails.append(decoded)
    display = name or structured
    if not display and not phones and not emails:
        return None
    return {"name": display, "phones": phones, "emails": emails}


def _scan_vcards(directory: Path) -> tuple[list[str], int]:
    entries = bound.scan_dir(directory, ".vcf", bound.MAX_SCAN_ENTRIES)
    paths = [p for (_n, p, _s, _m) in entries]
    newest = max((m for (_n, _p, _s, m) in entries), default=0)
    return paths, newest


def load_contacts(device_id: str, root: Path | None = None) -> list[dict]:
    directory = (root or VCARDS_ROOT) / f"kdeconnect-{bound.ident(device_id)}"
    cache_key = str(directory)
    files, newest = _scan_vcards(directory)
    stamp = (len(files), newest)
    cached = _CONTACTS_CACHE.get(cache_key)
    if cached and cached[0] == stamp:
        return cached[1]
    contacts: list[dict] = []
    budget = bound.Budget(bound.MAX_CONTACT_BYTES)
    for path in files:
        if len(contacts) >= MAX_CONTACTS:
            break
        result = bound.read_file(path, bound.MAX_VCARD_CHARS, budget)
        if result is None:
            continue
        text, over = result
        if over:
            break
        parsed = parse_vcard(text)
        if parsed:
            contacts.append(parsed)
    _CONTACTS_CACHE[cache_key] = (stamp, contacts)
    return contacts


def lookup_contact(address: str, contacts: list[dict] | None) -> dict | None:
    text = str(address or "").strip()
    if not text or not contacts:
        return None
    if "@" in text:
        needle = text.lower()
        for contact in contacts:
            for email in contact.get("emails") or []:
                if str(email).lower() == needle:
                    return contact
    for contact in contacts:
        for phone in contact.get("phones") or []:
            if phones_match(text, phone):
                return contact
    return None


def display_address(address: str, contacts: list[dict] | None = None) -> str:
    contact = lookup_contact(address, contacts)
    name = str((contact or {}).get("name") or "").strip()
    return name or str(address or "")


def conversation_title(message: dict, contacts: list[dict] | None = None) -> str:
    addresses = message.get("addresses") or []
    if not addresses:
        return "Unknown"
    return ", ".join(display_address(address, contacts) for address in addresses)


def serialize_contacts(contacts: list[dict] | None) -> list[dict]:
    rows = []
    for contact in contacts or []:
        phones = [str(phone).strip() for phone in (contact.get("phones") or []) if str(phone).strip()]
        if not phones:
            continue
        rows.append({
            "name": str(contact.get("name") or "").strip(),
            "phones": phones,
            "phone": phones[0],
        })
    rows.sort(key=lambda row: (str(row.get("name") or "").lower(), row["phone"]))
    return rows


def cmd_contacts(args: list[str]) -> None:
    from .util import emit, fail

    if not args:
        fail("Usage: contacts <device-id>")
    emit({"ok": True, "contacts": serialize_contacts(load_contacts(args[0]))})


def annotate_message(message: dict, contacts: list[dict] | None = None) -> dict:
    addresses = message.get("addresses") or []
    names = [display_address(address, contacts) for address in addresses]
    message["names"] = names
    message["title"] = conversation_title(message, contacts)
    return message


MAX_VCARD_CHARS = bound.MAX_VCARD_CHARS
MAX_CONTACTS = bound.MAX_CONTACTS
MAX_CONTACT_BYTES = bound.MAX_CONTACT_BYTES
MAX_CONTACT_FIELDS = bound.MAX_CONTACT_FIELDS
MAX_SCAN_ENTRIES = bound.MAX_SCAN_ENTRIES
