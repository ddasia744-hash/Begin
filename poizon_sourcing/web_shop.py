"""모델번호 웹 검색(Serper) → 쇼핑몰 상품 페이지에서 가격을 직접 읽는다.

구글 쇼핑에 모델번호로 잡히지 않는 상품(의류 등)용. 상품 페이지의 schema.org
JSON-LD(Product/Offer) 또는 og/product 가격 메타태그만 읽는다.
"""
from __future__ import annotations

import html as html_lib
import json
import re
from urllib.parse import urlparse

import requests

SEARCH_URL = "https://google.serper.dev/search"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
_LD_RE = re.compile(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', re.S | re.I)
_META_RE = re.compile(
    r'<meta[^>]+(?:property|name)=["\'](?:product:price:amount|og:price:amount|product:sale_price:amount)["\']'
    r'[^>]+content=["\']([\d.,]+)', re.I)
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)


def search_links(query: str, api_key: str, num: int = 20,
                 session: requests.Session | None = None) -> list[dict]:
    http = session or requests
    resp = http.post(SEARCH_URL, json={"q": query, "gl": "kr", "hl": "ko", "num": num},
                     headers={"X-API-KEY": api_key, "Content-Type": "application/json"}, timeout=15)
    resp.raise_for_status()
    return [{"title": o.get("title", ""), "url": o.get("link", ""), "snippet": o.get("snippet", "")}
            for o in resp.json().get("organic", []) if o.get("link")]


def _to_int(value) -> int:
    try:
        return int(float(str(value).replace(",", "")))
    except (TypeError, ValueError):
        return 0


def _walk(node):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


def parse_product_page(page: str) -> dict | None:
    """상품 페이지 HTML → {title, price, in_stock}. 가격을 못 찾으면 None."""
    for block in _LD_RE.findall(page):
        try:
            data = json.loads(block.strip())
        except ValueError:
            continue
        for node in _walk(data):
            types = node.get("@type")
            types = types if isinstance(types, list) else [types]
            if "Product" not in types:
                continue
            offers = node.get("offers") or {}
            offers = offers if isinstance(offers, list) else [offers]
            best = None
            for off in offers:
                if not isinstance(off, dict):
                    continue
                if (off.get("priceCurrency") or "KRW").upper() != "KRW":
                    continue
                price = _to_int(off.get("price") or off.get("lowPrice"))
                if price <= 0:
                    continue
                stock = "OutOfStock" not in str(off.get("availability", "")) \
                    and "SoldOut" not in str(off.get("availability", ""))
                if best is None or price < best["price"]:
                    best = {"price": price, "in_stock": stock}
            if best:
                best["title"] = str(node.get("name", "")).strip()
                return best
    m = _META_RE.search(page)
    if m and _to_int(m.group(1)) > 0:
        t = _TITLE_RE.search(page)
        return {"price": _to_int(m.group(1)), "in_stock": True,
                "title": html_lib.unescape(t.group(1)).strip() if t else ""}
    return None


def search(query: str, api_key: str, keep, max_pages: int = 6,
           session: requests.Session | None = None) -> list[dict]:
    """keep(link_dict) 가 True 인 검색 결과만 상품 페이지를 열어 가격을 읽는다."""
    http = session or requests
    offers, seen = [], set()
    for link in search_links(query, api_key, session=session):
        if len(seen) >= max_pages:
            break
        if link["url"] in seen or not keep(link):
            continue
        seen.add(link["url"])
        try:
            r = http.get(link["url"], headers={"User-Agent": UA, "Accept-Language": "ko-KR,ko"}, timeout=15)
            if r.status_code != 200:
                continue
            r.encoding = r.encoding if r.encoding and r.encoding.lower() != "iso-8859-1" else r.apparent_encoding
            info = parse_product_page(r.text)
        except requests.RequestException:
            continue
        if not info:
            continue
        host = urlparse(link["url"]).netloc.replace("www.", "").replace("m.", "", 1)
        offers.append({
            # 검색 결과 제목+페이지 상품명을 합쳐 모델번호 일치 검사에 쓴다(URL 포함)
            "title": f'{info["title"] or link["title"]} [{link["url"].split("?")[0].rsplit("/", 1)[-1]}]',
            "price": info["price"], "mall": host, "url": link["url"].split("?srsltid")[0],
            "in_stock": info["in_stock"],
        })
    return offers
