from __future__ import annotations

import binascii
import os
import re
import stat
import tempfile
from pathlib import Path

THUMB_DIR = Path.home() / ".cache" / "konnectarchy" / "thumbs"
MAX_THUMB_CHARS = 1 << 20
MAX_THUMB_BYTES = 1 << 19
MAX_MESSAGE_BYTES = 1 << 21
MAX_ATTACHMENTS = 16
_B64_CHARS = 4096
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")
_B64_WHITESPACE = re.compile(r"\s+")
_B64_STRICT = re.compile(r"[A-Za-z0-9+/]*={0,2}")


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


def _decode_b64(compact: str, max_bytes: int) -> bytes | None:
    if not compact or len(compact) % 4 == 1 or not _B64_STRICT.fullmatch(compact):
        return None
    out = bytearray()
    for start in range(0, len(compact), _B64_CHARS):
        piece = compact[start : start + _B64_CHARS]
        if pad := len(piece) % 4:
            piece += "=" * (4 - pad)
        try:
            out += binascii.a2b_base64(piece, strict_mode=True)
        except ValueError:
            return None
        if len(out) > max_bytes:
            return None
    return bytes(out)


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
    key: str, encoded: str, mime: str, cache_dir: Path | None = None, budget: list[int] | None = None
) -> str:
    blob = str(encoded or "").strip()
    if not blob or len(blob) > MAX_THUMB_CHARS:
        return ""
    directory = cache_dir or THUMB_DIR
    path = _thumb_path(key, mime, directory)
    try:
        info = path.lstat()
    except OSError:
        info = None
    if info is not None and stat.S_ISREG(info.st_mode) and info.st_size > 0:
        return path.as_uri()
    data = _decode_b64(_B64_WHITESPACE.sub("", blob), MAX_THUMB_BYTES)
    if not data:
        return ""
    if budget is not None:
        if len(data) > budget[0]:
            return ""
        budget[0] -= len(data)
    return _publish_thumbnail(path, data, directory)


def parse_attachment(raw, cache_dir: Path | None = None, budget: list[int] | None = None) -> dict | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        part_id = int(raw.get("part_id") or raw.get("partId") or raw.get("partID") or 0)
        mime = str(raw.get("mime_type") or raw.get("mime") or raw.get("mimeType") or "")
        encoded = str(raw.get("encoded_thumbnail") or raw.get("thumb") or raw.get("encodedThumbnail") or "")
        name = str(raw.get("unique_identifier") or raw.get("name") or raw.get("uniqueIdentifier") or "")
    elif isinstance(raw, (list, tuple)) and len(raw) >= 2:
        try:
            part_id = int(raw[0] or 0)
        except (TypeError, ValueError):
            return None
        mime = str(raw[1] or "")
        encoded = str(raw[2] or "") if len(raw) > 2 else ""
        name = str(raw[3] or "") if len(raw) > 3 else ""
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
    budget = [MAX_MESSAGE_BYTES]
    items = raw if isinstance(raw, (list, tuple)) else []
    for item in items[:MAX_ATTACHMENTS]:
        parsed = parse_attachment(item, cache_dir, budget)
        if parsed:
            rows.append(parsed)
    return rows


def parse_message(raw, cache_dir: Path | None = None) -> dict | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        body = str(raw.get("body") or "")
        addresses = [str(item) for item in (raw.get("addresses") or [])]
        attachments = parse_attachments(raw.get("attachments") or [], cache_dir)
        count = int(raw.get("attachmentCount") or 0) or len(attachments)
        return {
            "event": int(raw.get("event") or 0),
            "body": body,
            "addresses": addresses,
            "date": int(raw.get("date") or 0),
            "type": int(raw.get("type") or 0),
            "read": int(raw.get("read") or 0),
            "threadId": int(raw.get("threadId") or 0),
            "id": int(raw.get("id") or 0),
            "fromMe": bool(raw.get("fromMe")),
            "attachmentCount": count,
            "attachments": attachments,
        }
    if not isinstance(raw, (list, tuple)) or len(raw) < 8:
        return None
    addresses = []
    for item in raw[2] or []:
        if isinstance(item, (list, tuple)) and item:
            addresses.append(str(item[0]))
        else:
            addresses.append(str(item))
    unique = []
    for address in addresses:
        if address and address not in unique:
            unique.append(address)
    msg_type = int(raw[4] or 0)
    attachments = parse_attachments(raw[9] if len(raw) > 9 else [], cache_dir)
    return {
        "event": int(raw[0] or 0),
        "body": str(raw[1] or ""),
        "addresses": unique,
        "date": int(raw[3] or 0),
        "type": msg_type,
        "read": int(raw[5] or 0),
        "threadId": int(raw[6] or 0),
        "id": int(raw[7] or 0),
        "fromMe": msg_type == 2,
        "attachmentCount": len(attachments),
        "attachments": attachments,
    }
