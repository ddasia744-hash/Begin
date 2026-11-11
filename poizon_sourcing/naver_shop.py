"""네이버 쇼핑 검색 공식 API(https://developers.naver.com/docs/serviceapi/search/shopping/shopping.md).

애플리케이션 등록 후 받은 Client ID/Secret 이 필요하다(일 25,000회 무료).
"""
from __future__ import annotations

import html
import re

import requests

API_URL = "https://openapi.naver.com/v1/search/shop.json"
_TAG_RE = re.compile(r"<[^>]+>")
_NON_ALNUM = re.compile(r"[^0-9a-z]")

# 정품 새상품 리셀에 부적합한 결과를 거르는 키워드
EXCLUDE_KEYWORDS = ("중고", "리퍼", "가품", "레플", "미러", "B급", "전시상품", "렌탈", "대여")


def clean_title(title: str) -> str:
    return html.unescape(_TAG_RE.sub("", title or "")).strip()


def normalize(text: str) -> str:
    return _NON_ALNUM.sub("", (text or "").lower())


def title_matches_model(title: str, model_no: str) -> bool:
    """상품명에 모델번호가 (공백/하이픈 무시하고) 포함되는지. 비슷한 모델 오매칭 방지용."""
    code = normalize(model_no)
    return bool(code) and code in normalize(title)


def search(query: str, client_id: str, client_secret: str, display: int = 100,
           sort: str = "asc", session: requests.Session | None = None) -> list[dict]:
    """가격 낮은 순으로 검색해 정리된 상품 목록을 반환한다."""
    http = session or requests
    resp = http.get(
        API_URL,
        params={"query": query, "display": display, "sort": sort, "exclude": "used:rental"},
        headers={"X-Naver-Client-Id": client_id, "X-Naver-Client-Secret": client_secret},
        timeout=10,
    )
    resp.raise_for_status()
    items = resp.json().get("items", [])
    results = []
    for it in items:
        try:
            price = int(it.get("lprice") or 0)
        except ValueError:
            continue
        if price <= 0:
            continue
        results.append({
            "title": clean_title(it.get("title", "")),
            "price": price,
            "mall": it.get("mallName", ""),
            "url": it.get("link", ""),
            "brand": it.get("brand", ""),
            "product_id": it.get("productId", ""),
        })
    return results


def filter_offers(offers: list[dict], model_no: str) -> list[dict]:
    return [
        o for o in offers
        if title_matches_model(o["title"], model_no)
        and not any(k.lower() in o["title"].lower() for k in EXCLUDE_KEYWORDS)
    ]
