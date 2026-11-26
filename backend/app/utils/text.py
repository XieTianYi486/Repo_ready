from __future__ import annotations

import bisect
import hashlib
import math
import re
from datetime import datetime, timezone
from pathlib import PurePosixPath


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def short_sha(value: str, length: int = 7) -> str:
    value = (value or "").strip()
    return value[:length] if value else ""


def sha1_short(value: str, length: int = 16) -> str:
    return hashlib.sha1(value.encode("utf-8", "replace")).hexdigest()[:length]


def sha256_short(value: str, length: int = 12) -> str:
    return hashlib.sha256(value.encode("utf-8", "replace")).hexdigest()[:length]


def decode_text(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def looks_binary(data: bytes) -> bool:
    if not data:
        return False
    sample = data[:8192]
    if b"\x00" in sample:
        return True
    # Reject control-heavy content that is almost certainly not source/docs.
    control = sum(1 for b in sample if b < 9 or (13 < b < 32))
    return control / max(1, len(sample)) > 0.05


def shannon_entropy(value: str) -> float:
    if not value:
        return 0.0
    counts: dict[str, int] = {}
    for char in value:
        counts[char] = counts.get(char, 0) + 1
    length = len(value)
    entropy = 0.0
    for count in counts.values():
        p = count / length
        entropy -= p * math.log2(p)
    return entropy


def line_starts(text: str) -> list[int]:
    starts = [0]
    for match in re.finditer(r"\n", text):
        starts.append(match.end())
    return starts


def line_number_at(starts: list[int], index: int) -> int:
    return bisect.bisect_right(starts, max(0, index))


def line_at(text: str, starts: list[int], line_number: int) -> str:
    if line_number < 1 or line_number > len(starts):
        return ""
    start = starts[line_number - 1]
    end = starts[line_number] - 1 if line_number < len(starts) else len(text)
    return text[start:end].strip()


def truncate(value: str, limit: int = 200) -> str:
    value = value or ""
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)] + "…"


def strip_html_comments(text: str) -> str:
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)


def safe_filename(value: str, fallback: str = "report") -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value or "").strip("-._")
    return value[:80] or fallback


def normalize_rel_path(path: str) -> str:
    """Normalize an archive/entry path to a clean POSIX relative path."""
    value = path.replace("\\", "/").strip()
    while value.startswith("./"):
        value = value[2:]
    return value


def depth_of(path: str) -> int:
    return len([part for part in PurePosixPath(path).parts if part not in {"", "."}])


def is_probably_minified(text: str, path: str) -> bool:
    lower = path.lower()
    if lower.endswith((".min.js", ".min.css", ".map")):
        return True
    if len(text) < 4000:
        return False
    longest = max((len(line) for line in text.splitlines()[:20]), default=0)
    return longest > 1200
