"""구매처(쇼핑몰) 신뢰도 분류: trusted_malls.json 기준."""
from __future__ import annotations

import json
import os
import re
from urllib.parse import urlparse

DEFAULT_PATH = os.path.join(os.path.dirname(__file__), "trusted_malls.json")
_WS = re.compile(r"\s+")


def _norm(s: str) -> str:
    return _WS.sub("", (s or "").lower())


class MallTrust:
    def __init__(self, data: dict):
        self.trusted = [
            (t["tier"], t["name"], [_norm(a) for a in t.get("aliases", [])])
            for t in data.get("trusted", [])
        ]
        self.blocked = [_norm(b) for b in data.get("blocked", [])]

    @classmethod
    def load(cls, path: str | None = None) -> "MallTrust":
        with open(path or DEFAULT_PATH, encoding="utf-8") as f:
            return cls(json.load(f))

    def classify(self, mall: str, url: str = "") -> tuple[str, str]:
        """(등급, 표준 쇼핑몰명). 등급: 공식몰/백화점·대기업몰/정품 유통/차단/미확인."""
        host = urlparse(url).netloc if url else ""
        key = _norm(mall) + "|" + _norm(host)
        if any(b and b in key for b in self.blocked):
            return "차단", mall
        for tier, name, aliases in self.trusted:
            if any(a and a in key for a in aliases):
                return tier, name
        return "미확인", mall
