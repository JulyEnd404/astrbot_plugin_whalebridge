"""Validate administrator-supplied platform settings without logging secrets."""

import os
import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Settings:
    platform_id: str
    api_url: str
    api_token: str = field(repr=False)
    groups: tuple[str, ...]
    self_name: str
    mention_names: tuple[str, ...]
    unknown_sender_policy: str
    poll_interval: float
    discard_startup_backlog: bool


def settings_from(config: dict) -> Settings:
    if config.get("risk_acknowledged") is not True:
        raise ValueError("Read README and DISCLAIMER.md, then explicitly acknowledge the risks")
    platform_id = config.get("id", "mimicwx-wechat")
    if not isinstance(platform_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", platform_id):
        raise ValueError("Platform id must use 1-80 ASCII letters, numbers, hyphens or underscores")
    url = config.get("api_url", "http://127.0.0.1:8899")
    if not isinstance(url, str) or any(ord(c) < 32 for c in url):
        raise ValueError("api_url must be an HTTP(S) origin")
    try:
        parsed = urlsplit(url)
        valid_port = parsed.port is None or 1 <= parsed.port <= 65535
    except ValueError:
        raise ValueError("Invalid api_url") from None
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or not valid_port
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise ValueError(
            "api_url must be an HTTP(S) origin without credentials, path, query or fragment"
        )
    env = config.get("api_token_env", "")
    if not isinstance(env, str) or (env and not re.fullmatch(r"[A-Z_][A-Z0-9_]{0,127}", env)):
        raise ValueError("api_token_env must be an environment variable name")
    token = os.environ.get(env, "") if env else config.get("api_token", "")
    if not isinstance(token, str) or not token.strip() or "\r" in token or "\n" in token:
        raise ValueError(
            "Configure a nonempty API token in the AstrBot process environment or platform settings"
        )
    groups = config.get("groups", [])
    if (
        not isinstance(groups, list)
        or not 1 <= len(groups) <= 30
        or any(
            not isinstance(g, str) or not g.strip() or len(g) > 200 or any(ord(c) < 32 for c in g)
            for g in groups
        )
        or len(set(groups)) != len(groups)
    ):
        raise ValueError(
            "groups must contain 1-30 unique, exact, nonempty chat names without control characters"
        )
    self_name = config.get("self_name", "")
    names = config.get("mention_names", [])
    if (
        not isinstance(self_name, str)
        or not self_name.strip()
        or len(self_name) > 100
        or any(ord(c) < 32 for c in self_name)
    ):
        raise ValueError("Set the exact WeChat display name in self_name")
    if (
        not isinstance(names, list)
        or not names
        or any(
            not isinstance(n, str) or not n.strip() or len(n) > 100 or any(ord(c) < 32 for c in n)
            for n in names
        )
    ):
        raise ValueError(
            "mention_names must contain nonempty display names without control characters"
        )
    policy = config.get("unknown_sender_policy", "mention_only")
    if policy not in {"drop", "mention_only", "group"}:
        raise ValueError("unknown_sender_policy must be drop, mention_only or group")
    interval = config.get("poll_interval", 2.0)
    if (
        isinstance(interval, bool)
        or not isinstance(interval, (int, float))
        or not 1 <= interval <= 30
    ):
        raise ValueError("poll_interval must be between 1 and 30 seconds")
    discard = config.get("discard_startup_backlog", True)
    if not isinstance(discard, bool):
        raise ValueError("discard_startup_backlog must be a boolean")
    return Settings(
        platform_id,
        url.rstrip("/"),
        token.strip(),
        tuple(groups),
        self_name,
        tuple(dict.fromkeys(names)),
        policy,
        float(interval),
        discard,
    )
