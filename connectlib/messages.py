from __future__ import annotations

import os
import re
import stat
import tempfile
from pathlib import Path

from . import bound

THUMB_DIR = Path.home() / ".cache" / "konnectarchy" / "thumbs"
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def chip_label(mime: str, name: str) -> str:
    pretty = str(name or "").replace("\\", "/").split("/")[-1]
    if pretty.startswith("PART_") and "_" in pretty:
        pretty = pretty.split("_")[-1]
    mime = str(mime or "").lower()
    if mime.startswith("image/"):
        return pretty or "Photo"
    if mime.startswith("video/"):
        return pretty or "Video"
    if mime.startswith("audio/"):
        return pretty or "Audio"
    if "pdf" in mime:
        return pretty or "PDF"
    if "vcard" in mime or mime.endswith("card"):
        return pretty or "Contact"
    return pretty or (mime.split("/")[-1].upper() if mime else "File")


def _thumb_path(key: str, mime: str, cache_dir: Path) -> Path:
    ext = "jpg"
    lower = str(mime or "").lower()
    if "png" in lower:
        ext = "png"
    elif "gif" in lower:
        ext = "gif"
    elif "webp" in lower:
        ext = "webp"
    safe = _SAFE_NAME.sub("_", key or "att").strip("._")[:80] or "att"
    return cache_dir / f"{safe}.{ext}"


def _publish_thumbnail(path: Path, data: bytes, directory: Path) -> str:
    directory.mkdir(parents=True, exist_ok=True)
    try:
        fd, tmp = tempfile.mkstemp(dir=directory, prefix=path.name + ".", suffix=".part")
    except OSError:
        return ""
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp, path)
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        return ""
    return path.as_uri()


def write_thumbnail(
    key: str, encoded: str, mime: str, cache_dir: Path | None = None, budget: bound.Budget | None = None
) -> str:
    blob = str(encoded or "").strip()
    if not blob or len(blob) > bound.MAX_THUMB_CHARS:
        return ""
    directory = cache_dir or THUMB_DIR
    path = _thumb_path(key, mime, directory)
    try:
        info = path.lstat()
    except OSError:
        info = None
    if info is not None and stat.S_ISREG(info.st_mode) and info.st_size > 0:
        return path.as_uri()
    data = bound.b64_decode(blob, bound.MAX_THUMB_BYTES, budget)
    if not data:
        return ""
    return _publish_thumbnail(path, data, directory)


def parse_attachment(raw, cache_dir: Path | None = None, budget: bound.Budget | None = None) -> dict | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        part_id = bound.num(raw.get("part_id") or raw.get("partId") or raw.get("partID"))
        mime = bound.label(raw.get("mime_type") or raw.get("mime") or raw.get("mimeType"))
        encoded = str(raw.get("encoded_thumbnail") or raw.get("thumb") or raw.get("encodedThumbnail") or "")
        name = bound.label(raw.get("unique_identifier") or raw.get("name") or raw.get("uniqueIdentifier"))
    elif isinstance(raw, (list, tuple)) and len(raw) >= 2:
        try:
            part_id = int(raw[0] or 0)
        except (TypeError, ValueError):
            return None
        mime = bound.label(raw[1])
        encoded = str(raw[2] or "") if len(raw) > 2 else ""
        name = bound.label(raw[3]) if len(raw) > 3 else ""
    else:
        return None
    kind = "image" if mime.lower().startswith("image/") else "file"
    thumb = ""
    if kind == "image" and encoded:
        thumb = write_thumbnail(name or str(part_id), encoded, mime, cache_dir, budget)
    if kind == "image" and not thumb:
        kind = "file"
    return {
        "partId": part_id,
        "mime": mime,
        "name": name,
        "kind": kind,
        "thumb": thumb,
        "label": chip_label(mime, name),
    }


def parse_attachments(raw, cache_dir: Path | None = None) -> list[dict]:
    rows = []
    budget = bound.Budget(bound.MAX_MESSAGE_BYTES)
    items = raw if isinstance(raw, (list, tuple)) else []
    for item in items[:bound.MAX_ATTACHMENTS]:
        parsed = parse_attachment(item, cache_dir, budget)
        if parsed:
            rows.append(parsed)
    return rows


def parse_message(raw, cache_dir: Path | None = None) -> dict | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        body = bound.text(raw.get("body"))
        addresses = bound.strings(raw.get("addresses"), bound.MAX_ADDRESSES)
        attachments = parse_attachments(raw.get("attachments") or [], cache_dir)
        count = bound.num(raw.get("attachmentCount")) or len(attachments)
        return {
            "event": bound.num(raw.get("event")),
            "body": body,
            "addresses": addresses,
            "date": bound.num(raw.get("date")),
            "type": bound.num(raw.get("type")),
            "read": bound.num(raw.get("read")),
            "threadId": bound.num(raw.get("threadId")),
            "id": bound.num(raw.get("id")),
            "fromMe": bound.flag(raw.get("fromMe")),
            "attachmentCount": count,
            "attachments": attachments,
        }
    if not isinstance(raw, (list, tuple)) or len(raw) < 8:
        return None
    raw_addrs = raw[2]
    if not isinstance(raw_addrs, (list, tuple)):
        raw_addrs = []
    addresses = []
    for item in raw_addrs:
        if len(addresses) >= bound.MAX_ADDRESSES:
            break
        if isinstance(item, (list, tuple)) and item:
            addresses.append(bound.label(item[0]))
        else:
            addresses.append(bound.label(item))
    unique = []
    for address in addresses:
        if address and address not in unique:
            unique.append(address)
    msg_type = bound.num(raw[4])
    attachments = parse_attachments(raw[9] if len(raw) > 9 else [], cache_dir)
    return {
        "event": bound.num(raw[0]),
        "body": bound.text(raw[1]),
        "addresses": unique,
        "date": bound.num(raw[3]),
        "type": msg_type,
        "read": bound.num(raw[5]),
        "threadId": bound.num(raw[6]),
        "id": bound.num(raw[7]),
        "fromMe": msg_type == 2,
        "attachmentCount": len(attachments),
        "attachments": attachments,
    }


MAX_THUMB_CHARS = bound.MAX_THUMB_CHARS
MAX_THUMB_BYTES = bound.MAX_THUMB_BYTES
MAX_MESSAGE_BYTES = bound.MAX_MESSAGE_BYTES
MAX_ATTACHMENTS = bound.MAX_ATTACHMENTS
MAX_ADDRESSES = bound.MAX_ADDRESSES
B64_CHUNK = bound.B64_CHUNK
