from __future__ import annotations

import binascii
import os
import re
import stat

from .util import clamp_id

MAX_TEXT_CHARS = 4096
MAX_LABEL_CHARS = 256
MAX_ID_CHARS = 64
MAX_EMIT_BYTES = 4 << 20
MAX_DEVICES = 32
MAX_PLUGINS = 64
MAX_NOTIFICATIONS = 128
MAX_PLAYERS = 32
MAX_CONVERSATIONS = 256
MAX_THREAD_MESSAGES = 256
MAX_CONTACTS = 512
MAX_CONTACT_FIELDS = 16
MAX_CONTACT_BYTES = 8 << 20
MAX_SCAN_ENTRIES = 2048
MAX_VCARD_CHARS = 1 << 20
MAX_ATTACHMENTS = 16
MAX_ADDRESSES = 32
MAX_THUMB_CHARS = 1 << 20
MAX_THUMB_BYTES = 1 << 19
MAX_MESSAGE_BYTES = 1 << 21
B64_CHUNK = 4096
MAX_SAFE_INT = 2**53 - 1
_B64_WHITESPACE = re.compile(r"\s+")
_B64_STRICT = re.compile(r"[A-Za-z0-9+/]*={0,2}")


def text(value, limit: int = MAX_TEXT_CHARS) -> str:
    return str(value or "")[:limit]


def label(value) -> str:
    return text(value, MAX_LABEL_CHARS)


def ident(value) -> str:
    return clamp_id(value)


def num(value, default=0) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return default
    if abs(parsed) > MAX_SAFE_INT:
        parsed = MAX_SAFE_INT if parsed > 0 else -MAX_SAFE_INT
    return parsed


def flag(value) -> bool:
    return bool(value)


def strings(raw, count_limit, each_limit: int = MAX_LABEL_CHARS) -> list[str]:
    if not isinstance(raw, (list, tuple)):
        return []
    out = []
    for item in raw:
        if len(out) >= count_limit:
            break
        out.append(str(item)[:each_limit])
    return out


def mapping(raw, entry_limit) -> dict[str, object]:
    if not isinstance(raw, dict):
        return {}
    out = {}
    for key, value in raw.items():
        if len(out) >= entry_limit:
            break
        if isinstance(key, str):
            out[key] = value
    return out


class Budget:
    def __init__(self, capacity: int):
        self._capacity = capacity
        self._used = 0

    @property
    def used(self) -> int:
        return self._used

    def spend(self, n: int) -> bool:
        if n < 0 or self._used + n > self._capacity:
            return False
        self._used += n
        return True


def scan_dir(directory, suffix, entry_budget) -> list[tuple[str, str, int, int, int, int, int, int]]:
    entries = []
    seen = 0
    try:
        with os.scandir(directory) as iterator:
            for entry in iterator:
                if seen >= entry_budget:
                    break
                seen += 1
                if not entry.name.endswith(suffix):
                    continue
                try:
                    if not entry.is_file(follow_symlinks=False):
                        continue
                    info = entry.stat(follow_symlinks=False)
                except OSError:
                    continue
                entries.append(
                    (
                        entry.name,
                        entry.path,
                        info.st_size,
                        info.st_mtime_ns,
                        info.st_dev,
                        info.st_ino,
                        info.st_uid,
                        info.st_mode,
                    )
                )
    except OSError:
        return []
    return entries


def _open_regular(path, dir_fd=None) -> int | None:
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
    try:
        return os.open(path, flags, dir_fd=dir_fd)
    except OSError:
        return None


def _read_bounded(fd, max_chars, budget) -> tuple[str, bool]:
    chunks = []
    remaining = max_chars
    while remaining > 0:
        try:
            chunk = os.read(fd, min(65536, remaining))
        except OSError:
            break
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    text_ = b"".join(chunks).decode("utf-8", errors="replace")
    return text_, not budget.spend(len(text_.encode("utf-8", errors="replace")))


def read_scanned(directory, entry, max_chars: int, budget) -> tuple[str, bool] | None:
    name, _path, size, _mtime, dev, ino, uid, _mode = entry
    try:
        dir_fd = os.open(
            directory,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
        )
    except OSError:
        return None
    try:
        fd = _open_regular(name, dir_fd)
        if fd is None:
            return None
        try:
            try:
                info = os.fstat(fd)
            except OSError:
                return None
            if not stat.S_ISREG(info.st_mode):
                return None
            if info.st_dev != dev or info.st_ino != ino or info.st_uid != uid or info.st_size != size:
                return None
            return _read_bounded(fd, max_chars, budget)
        finally:
            os.close(fd)
    finally:
        os.close(dir_fd)


def read_file(path, max_chars, budget) -> tuple[str, bool] | None:
    fd = _open_regular(path)
    if fd is None:
        return None
    try:
        try:
            info = os.fstat(fd)
        except OSError:
            return None
        if not stat.S_ISREG(info.st_mode):
            return None
        return _read_bounded(fd, max_chars, budget)
    finally:
        os.close(fd)


def b64_decode(compact, max_bytes, budget=None) -> bytes | None:
    compact = _B64_WHITESPACE.sub("", str(compact or ""))
    if not compact or len(compact) % 4 == 1 or not _B64_STRICT.fullmatch(compact):
        return None
    out = bytearray()
    for start in range(0, len(compact), B64_CHUNK):
        piece = compact[start : start + B64_CHUNK]
        if pad := len(piece) % 4:
            piece += "=" * (4 - pad)
        try:
            decoded = binascii.a2b_base64(piece, strict_mode=True)
        except ValueError:
            return None
        out += decoded
        if len(out) > max_bytes:
            return None
        if budget is not None and not budget.spend(len(decoded)):
            return None
    return bytes(out)