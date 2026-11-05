"""이벤트 목록을 셀러가 바로 쓸 수 있는 형태로 정리한다."""
from __future__ import annotations

import csv
import io
from collections import Counter
from datetime import date

from .parser import Event

# 이 유형이 마지막이면 '판매 불가'로 본다
UNAVAILABLE = {"품절"}
CSV_FIELDS = ["date", "time", "type", "code", "product", "price", "price_before", "price_after", "note", "raw"]


def filter_events(
    events: list[Event],
    since: date | None = None,
    until: date | None = None,
    keywords: list[str] | None = None,
    types: list[str] | None = None,
) -> list[Event]:
    kws = [k.strip().lower() for k in (keywords or []) if k.strip()]
    out = []
    for ev in events:
        d = ev.when.date()
        if since and d < since:
            continue
        if until and d > until:
            continue
        if types and ev.type not in types:
            continue
        if kws:
            hay = f"{ev.product} {ev.code}".lower()
            if not any(k in hay for k in kws):
                continue
        out.append(ev)
    return out


def _key(ev: Event) -> str:
    return f"{ev.code}|{ev.product}" if ev.code else ev.product


def latest_status(events: list[Event]) -> list[dict]:
    """상품별 마지막 이벤트와 마지막으로 알려진 가격."""
    status: dict[str, dict] = {}
    for ev in sorted(events, key=lambda e: e.when):
        row = status.setdefault(_key(ev), {"product": ev.product, "code": ev.code, "price": None, "events": 0})
        row["events"] += 1
        row["type"] = ev.type
        row["when"] = ev.when
        row["available"] = ev.type not in UNAVAILABLE
        new_price = ev.price_after if ev.price_after is not None else ev.price
        if new_price is not None:
            row["price"] = new_price
    return sorted(status.values(), key=lambda r: r["when"], reverse=True)


def summarize(events: list[Event]) -> dict:
    by_type = Counter(ev.type for ev in events)
    soldout_codes = Counter(ev.code for ev in events if ev.type == "품절" and ev.code)
    soldout_products = Counter(ev.product for ev in events if ev.type == "품절")
    by_month = Counter(ev.when.strftime("%Y-%m") for ev in events)
    return {
        "total": len(events),
        "by_type": by_type.most_common(),
        "by_month": sorted(by_month.items()),
        "soldout_codes": soldout_codes.most_common(10),
        "soldout_products": soldout_products.most_common(10),
        "first": min((e.when for e in events), default=None),
        "last": max((e.when for e in events), default=None),
    }


def to_csv(events: list[Event]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for ev in events:
        writer.writerow(ev.to_row())
    return buf.getvalue()
