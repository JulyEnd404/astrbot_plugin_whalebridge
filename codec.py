"""Normalize UI observations, not native WeChat account IDs."""

import hashlib
import re
import sqlite3
import time
import unicodedata
from pathlib import Path

MEDIA_LABELS = {"图片", "动画表情", "表情", "表情包", "贴图", "视频", "语音", "文件"}


def group_id(name: str) -> str:
    return "wxg_" + hashlib.sha256(name.encode()).hexdigest()[:24]


def text_digest(text: str) -> str:
    normalized = " ".join(unicodedata.normalize("NFKC", text).split())
    return hashlib.sha256(normalized.encode()).hexdigest()


def identity(group: str, raw: dict) -> str | None:
    mid = raw.get("msg_id")
    if not isinstance(mid, str) or not mid or len(mid) > 500:
        return None
    index = raw.get("index")
    suffix = str(index) if not mid.startswith("ui:") and type(index) is int else ""
    return hashlib.sha256((group + "\0" + mid + "\0" + suffix).encode()).hexdigest()


def normalize(
    group: str, raw: dict, self_name: str, names: tuple[str, ...], policy="mention_only"
) -> dict | None:
    if not isinstance(raw, dict):
        return None
    kind = raw.get("msg_type")
    anonymous = kind == "sys" and raw.get("role") == "list item" and raw.get("children") == []
    if kind != "friend" and not anonymous:
        return None
    sender = raw.get("sender", "")
    if not isinstance(sender, str) or sender.strip() == self_name:
        return None
    sender = sender.strip()
    text = raw.get("content")
    if not isinstance(text, str) or not text.strip() or len(text) > 6000:
        return None
    text = text.strip()
    if text.strip("[]") in MEDIA_LABELS:
        return None  # No image originals are available through this transport.
    mid = identity(group, raw)
    if not mid:
        return None
    known = bool(sender and sender != "SYS" and not anonymous)
    pattern = re.compile(
        r"@(" + "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True)) + r")(?=\s|$)"
    )
    mentioned = bool(pattern.search(text))
    if not known and (policy == "drop" or (policy == "mention_only" and not mentioned)):
        return None
    if known:
        uid = "wxu_" + hashlib.sha256((group + "\0" + sender).encode()).hexdigest()[:24]
    elif policy == "group":
        uid = "wxanon_" + group_id(group)[4:]  # One anonymous group identity, never a person.
    else:
        uid = "wxanon_" + mid[:24]  # No cross-message personal identity by default.
    return {
        "group_id": group_id(group),
        "message_id": mid,
        "sender_id": uid,
        "sender_name": sender if known else "未识别群友",
        "sender_known": known,
        "text": pattern.sub("", text).strip() if mentioned else text,
        "mentioned": mentioned,
        "original_text": text,
    }


class Ledger:
    """Best-effort at-most-once claims; no raw chat text is stored here."""

    def __init__(self, path, clock=time.time):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.clock = clock
        self.db = sqlite3.connect(path)
        self.db.execute("CREATE TABLE IF NOT EXISTS incoming(id TEXT PRIMARY KEY, at REAL)")
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS outgoing(chat TEXT, hash TEXT, at REAL, PRIMARY KEY(chat,hash))"
        )
        self.db.commit()

    def claim(self, mid):
        try:
            self.db.execute("INSERT INTO incoming VALUES (?,?)", (mid, self.clock()))
            self.db.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def remember(self, group, text):
        self.db.execute(
            "INSERT OR REPLACE INTO outgoing VALUES (?,?,?)",
            (group_id(group), text_digest(text), self.clock()),
        )
        self.db.commit()

    def is_echo(self, group, text):
        return (
            self.db.execute(
                "SELECT 1 FROM outgoing WHERE chat=? AND hash=? AND at>?",
                (group_id(group), text_digest(text), self.clock() - 300),
            ).fetchone()
            is not None
        )

    def prune(self):
        self.db.execute("DELETE FROM incoming WHERE at<?", (self.clock() - 7 * 86400,))
        self.db.execute("DELETE FROM outgoing WHERE at<?", (self.clock() - 300,))
        self.db.commit()

    def close(self):
        self.db.close()
