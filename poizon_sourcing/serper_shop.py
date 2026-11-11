"""Serper.dev 구글 쇼핑 검색(한국). https://serper.dev

키는 X-API-KEY 헤더로 보낸다. 무료 크레딧 소진 후 유료.
"""
from __future__ import annotations

import re
from urllib.parse import quote_plus

import requests

API_URL = "https://google.serper.dev/shopping"
_PRICE_RE = re.compile(r"[\d,]+")


def parse_krw(text) -> int:
    """'₩55,000', '55,000원', 55000 → 55000. 외화(US$ 등)나 해석 불가는 0."""
    if isinstance(text, (int, float)):
        return int(text)
    s = str(text or "")
    if any(c in s for c in ("$", "€", "¥", "£")) and "₩" not in s:
        return 0
    m = _PRICE_RE.search(s)
    if not m:
        return 0
    digits = m.group().replace(",", "")
    return int(digits) if digits else 0


def product_url(item: dict) -> str:
    """Serper 결과에 link 가 비어 있을 때 구글 쇼핑 상품/검색 페이지 주소를 만든다."""
    pid = item.get("productId")
    if pid:
        return f"https://www.google.com/shopping/product/{pid}?gl=kr&hl=ko"
    q = f'{item.get("title", "")} {item.get("source", "")}'.strip()
    return f"https://www.google.com/search?tbm=shop&gl=kr&hl=ko&q={quote_plus(q)}"


def search(query: str, api_key: str, num: int = 40,
           session: requests.Session | None = None) -> list[dict]:
    http = session or requests
    resp = http.post(
        API_URL,
        json={"q": query, "gl": "kr", "hl": "ko", "num": num},
        headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
        timeout=15,
    )
    resp.raise_for_status()
    results = []
    for it in resp.json().get("shopping", []):
        price = parse_krw(it.get("price"))
        if price <= 0:
            continue
        results.append({
            "title": (it.get("title") or "").strip(),
            "price": price,
            "mall": (it.get("source") or "").strip(),
            "url": it.get("link") or product_url(it),
            "delivery": it.get("delivery", ""),
        })
    return results
