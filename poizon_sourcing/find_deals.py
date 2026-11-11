"""포이즌 최저가 목록(CSV)을 읽어 국내 쇼핑몰에서 '최대 매입가' 이하 상품을 찾는다.

사용법:
    export NAVER_CLIENT_ID=... NAVER_CLIENT_SECRET=...
    python -m poizon_sourcing.find_deals poizon_sourcing/products.example.csv \
        --fees poizon_sourcing/fees.example.json --out deals.csv

입력 CSV 컬럼: model_no, name, poizon_price  (brand 는 선택)
출력 CSV: 조건을 만족한 구입처 목록(순수익 높은 순)
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
import time

import requests

from . import naver_shop
from .margin import FeeConfig, max_buy_price, net_profit

OUT_FIELDS = [
    "model_no", "name", "poizon_price", "max_buy_price", "shop_price",
    "est_profit", "profit_rate", "mall", "title", "url",
]


def parse_price(value: str) -> int:
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return int(digits) if digits else 0


def read_products(path: str) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = []
        for r in csv.DictReader(f):
            model = (r.get("model_no") or "").strip()
            price = parse_price(r.get("poizon_price", ""))
            if model and price:
                rows.append({"model_no": model, "name": (r.get("name") or "").strip(),
                             "brand": (r.get("brand") or "").strip(), "poizon_price": price})
        return rows


def find_deals(products: list[dict], cfg: FeeConfig, searcher, per_model: int = 5) -> list[dict]:
    """searcher(query) -> offers. 모델별로 최대 매입가 이하인 구입처를 per_model 개까지 반환."""
    deals = []
    for p in products:
        limit = max_buy_price(p["poizon_price"], cfg)
        if limit <= 0:
            continue
        query = f'{p["brand"]} {p["model_no"]}'.strip()
        offers = naver_shop.filter_offers(searcher(query), p["model_no"])
        cheap = sorted((o for o in offers if o["price"] <= limit), key=lambda o: o["price"])
        for o in cheap[:per_model]:
            profit = net_profit(p["poizon_price"], o["price"], cfg)
            deals.append({
                "model_no": p["model_no"], "name": p["name"],
                "poizon_price": p["poizon_price"], "max_buy_price": limit,
                "shop_price": o["price"], "est_profit": profit,
                "profit_rate": round(profit / o["price"] * 100, 1),
                "mall": o["mall"], "title": o["title"], "url": o["url"],
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
    args = ap.parse_args(argv)

    cid, secret = os.environ.get("NAVER_CLIENT_ID"), os.environ.get("NAVER_CLIENT_SECRET")
    if not cid or not secret:
        print("NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 환경변수를 설정하세요.", file=sys.stderr)
        return 2

    cfg = FeeConfig.load(args.fees)
    products = read_products(args.products)
    session = requests.Session()

    def searcher(query: str) -> list[dict]:
        time.sleep(args.delay)
        try:
            return naver_shop.search(query, cid, secret, session=session)
        except requests.RequestException as e:
            print(f"[경고] '{query}' 검색 실패: {e}", file=sys.stderr)
            return []

    deals = find_deals(products, cfg, searcher, per_model=args.per_model)
    write_csv(deals, args.out)
    print(f"{len(products)}개 모델 검색 → 조건 충족 구입처 {len(deals)}건, 저장: {args.out}")
    for d in deals[:20]:
        print(f'  {d["model_no"]:<12} 포이즌 {d["poizon_price"]:>8,} / 국내 {d["shop_price"]:>8,} '
              f'({d["mall"]}) 예상수익 {d["est_profit"]:>7,}원  {d["url"]}')
    return 0


if __name__ == "__main__":
    sys.exit(main())
