"""포이즌 최저가 목록(CSV)을 읽어 국내 쇼핑몰에서 '최대 매입가' 이하 상품을 찾는다.

사용법 (기본: Serper 구글 쇼핑 + 신뢰 쇼핑몰만):
    export SERPER_API_KEY=...
    python -m poizon_sourcing.find_deals poizon_sourcing/products.example.csv \
        --fees poizon_sourcing/fees.example.json --out deals.csv

    --source naver 로 네이버 쇼핑 API(기존 개발자센터 키 보유자)도 사용 가능.
    --include-unverified 를 주면 신뢰 목록에 없는 쇼핑몰도 '미확인' 등급으로 포함.

입력 CSV 컬럼: model_no, name, 그리고 가격(아래 중 하나 이상)
    poizon_price : 판매 기준가를 직접 지정
    avg_30d      : 셀러센터 '최근 30일 평균 거래가'
    cn_exposed   : 셀러센터 '중국 구매자 페이지 노출'가
  poizon_price 가 비어 있으면 avg_30d·cn_exposed 중 낮은 값(보수적)을 기준가로 쓴다.
선택 컬럼:
    brand : 검색어 앞에 붙일 브랜드
    query : 검색어 직접 지정 (기본: brand + model_no)
    match : 상품명 일치 조건. 공백=모두 포함, '|'=또는  (기본: model_no)
            예) "러브누드 글로우|lovenude glow"
출력 CSV: 조건을 만족한 구입처 목록(순수익 높은 순)
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
import time

import requests

from . import naver_shop, serper_shop
from .margin import FeeConfig, max_buy_price, net_profit
from .trust import MallTrust

OUT_FIELDS = [
    "model_no", "name", "poizon_price", "max_buy_price", "shop_price",
    "est_profit", "profit_rate", "trust", "mall", "shop_mall_raw", "title", "url",
]


def parse_price(value: str) -> int:
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return int(digits) if digits else 0


def base_price(row: dict) -> int:
    direct = parse_price(row.get("poizon_price", ""))
    if direct:
        return direct
    candidates = [parse_price(row.get(k, "")) for k in ("avg_30d", "cn_exposed")]
    candidates = [c for c in candidates if c > 0]
    return min(candidates) if candidates else 0


def read_products(path: str) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = []
        for r in csv.DictReader(f):
            model = (r.get("model_no") or "").strip()
            price = base_price(r)
            if model and price:
                brand = (r.get("brand") or "").strip()
                rows.append({
                    "model_no": model, "name": (r.get("name") or "").strip(),
                    "brand": brand, "poizon_price": price,
                    "query": (r.get("query") or "").strip() or f"{brand} {model}".strip(),
                    "match": (r.get("match") or "").strip() or model,
                })
        return rows


def find_deals(products: list[dict], cfg: FeeConfig, searcher, per_model: int = 5,
               trust: MallTrust | None = None, include_unverified: bool = False) -> list[dict]:
    """searcher(query) -> offers. 모델별로 최대 매입가 이하인 구입처를 per_model 개까지 반환.

    trust 가 주어지면 '차단' 쇼핑몰은 항상 제외, '미확인'은 include_unverified 일 때만 포함.
    """
    deals = []
    for p in products:
        limit = max_buy_price(p["poizon_price"], cfg)
        if limit <= 0:
            continue
        query = p.get("query") or f'{p["brand"]} {p["model_no"]}'.strip()
        offers = naver_shop.filter_offers(searcher(query), p.get("match") or p["model_no"])
        floor = p["poizon_price"] * cfg.min_price_ratio
        picked = []
        for o in sorted(offers, key=lambda o: o["price"]):
            if o["price"] < floor:
                continue
            if o["price"] > limit:
                break
            tier, mall = ("-", o["mall"])
            if trust:
                tier, mall = trust.classify(o["mall"], o.get("url", ""))
                if tier == "차단" or (tier == "미확인" and not include_unverified):
                    continue
            picked.append((o, tier, mall))
            if len(picked) >= per_model:
                break
        for o, tier, mall in picked:
            profit = net_profit(p["poizon_price"], o["price"], cfg)
            deals.append({
                "model_no": p["model_no"], "name": p["name"],
                "poizon_price": p["poizon_price"], "max_buy_price": limit,
                "shop_price": o["price"], "est_profit": profit,
                "profit_rate": round(profit / o["price"] * 100, 1),
                "trust": tier, "mall": mall, "shop_mall_raw": o["mall"],
                "title": o["title"], "url": o["url"],
            })
    deals.sort(key=lambda d: d["est_profit"], reverse=True)
    return deals


def write_csv(deals: list[dict], path: str) -> None:
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=OUT_FIELDS)
        w.writeheader()
        w.writerows(deals)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("products", help="포이즌 최저가 CSV (model_no,name,poizon_price[,brand])")
    ap.add_argument("--fees", help="수수료/배송비/목표수익 설정 JSON")
    ap.add_argument("--out", default="deals.csv", help="결과 CSV 경로 (기본: deals.csv)")
    ap.add_argument("--per-model", type=int, default=5, help="모델당 최대 결과 수")
    ap.add_argument("--delay", type=float, default=0.15, help="API 호출 간격(초)")
    ap.add_argument("--source", choices=["serper", "naver"], default="serper", help="가격 검색 소스")
    ap.add_argument("--trusted", help="신뢰 쇼핑몰 목록 JSON (기본: trusted_malls.json)")
    ap.add_argument("--include-unverified", action="store_true", help="신뢰 목록에 없는 쇼핑몰도 포함")
    args = ap.parse_args(argv)

    if args.source == "serper":
        key = os.environ.get("SERPER_API_KEY")
        if not key:
            print("SERPER_API_KEY 환경변수를 설정하세요.", file=sys.stderr)
            return 2

        def raw_search(query, session):
            return serper_shop.search(query, key, session=session)
    else:
        cid, secret = os.environ.get("NAVER_CLIENT_ID"), os.environ.get("NAVER_CLIENT_SECRET")
        if not cid or not secret:
            print("NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 환경변수를 설정하세요.", file=sys.stderr)
            return 2

        def raw_search(query, session):
            return naver_shop.search(query, cid, secret, session=session)

    cfg = FeeConfig.load(args.fees)
    trust = MallTrust.load(args.trusted)
    products = read_products(args.products)
    session = requests.Session()

    def searcher(query: str) -> list[dict]:
        time.sleep(args.delay)
        try:
            return raw_search(query, session)
        except requests.RequestException as e:
            print(f"[경고] '{query}' 검색 실패: {e}", file=sys.stderr)
            return []

    deals = find_deals(products, cfg, searcher, per_model=args.per_model,
                       trust=trust, include_unverified=args.include_unverified)
    write_csv(deals, args.out)
    print(f"{len(products)}개 모델 검색 → 조건 충족 구입처 {len(deals)}건, 저장: {args.out}")
    for d in deals[:20]:
        print(f'  {d["model_no"]:<12} 포이즌 {d["poizon_price"]:>8,} / 국내 {d["shop_price"]:>8,} '
              f'[{d["trust"]}] {d["mall"]} 예상수익 {d["est_profit"]:>7,}원  {d["url"]}')
    return 0


if __name__ == "__main__":
    sys.exit(main())
