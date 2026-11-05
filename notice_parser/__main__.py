"""명령줄 사용법.

    python -m notice_parser 대화.txt
    python -m notice_parser 대화.txt --since 2026-10-01 --watch 감귤,사과 --status
    python -m notice_parser 대화.txt --csv events.csv
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from . import filter_events, latest_status, parse_chat, summarize, to_csv


def _date(s: str) -> date:
    return date.fromisoformat(s)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="notice_parser", description="공급사 카톡 공지에서 품절·단가 변동을 뽑습니다.")
    ap.add_argument("file", type=Path, help="카카오톡 대화 내보내기 .txt")
    ap.add_argument("--sender", help="공급사 이름 일부 (기본: 글을 가장 많이 쓴 사람)")
    ap.add_argument("--since", type=_date, help="이 날짜부터 (YYYY-MM-DD)")
    ap.add_argument("--until", type=_date, help="이 날짜까지 (YYYY-MM-DD)")
    ap.add_argument("--watch", help="관심 품목, 쉼표로 구분 (예: 감귤,사과,E05)")
    ap.add_argument("--type", help="유형 필터, 쉼표로 구분 (예: 품절,단가인상)")
    ap.add_argument("--status", action="store_true", help="상품별 현재 상태 표 출력")
    ap.add_argument("--csv", type=Path, help="이벤트를 CSV로 저장 (엑셀용 UTF-8 BOM)")
    ap.add_argument("--limit", type=int, default=30, help="표에 보여줄 최대 줄 수")
    args = ap.parse_args(argv)

    text = args.file.read_text(encoding="utf-8-sig")
    _, events = parse_chat(text, args.sender)
    events = filter_events(
        events,
        since=args.since,
        until=args.until,
        keywords=args.watch.split(",") if args.watch else None,
        types=args.type.split(",") if args.type else None,
    )

    s = summarize(events)
    print(f"이벤트 {s['total']}건", end="")
    if s["first"]:
        print(f"  ({s['first']:%Y-%m-%d} ~ {s['last']:%Y-%m-%d})")
    else:
        print()
    print("유형별:", ", ".join(f"{t} {n}" for t, n in s["by_type"]))
    if s["soldout_codes"]:
        print("품절이 잦은 공급 코드:", ", ".join(f"{c}({n})" for c, n in s["soldout_codes"]))

    if args.status:
        print("\n[상품별 현재 상태] 최신순")
        for row in latest_status(events)[: args.limit]:
            mark = "판매불가" if not row["available"] else "판매가능"
            price = f"{row['price']:,}원" if row["price"] else "-"
            code = f"[{row['code']}] " if row["code"] else ""
            print(f"{row['when']:%m-%d %H:%M}  {mark}  {row['type']:<5}  {price:>9}  {code}{row['product']}")
    else:
        print("\n[최근 이벤트]")
        for ev in sorted(events, key=lambda e: e.when, reverse=True)[: args.limit]:
            price = ""
            if ev.price_before is not None:
                price = f"  {ev.price_before:,} → {ev.price_after:,}"
            elif ev.price is not None:
                price = f"  {ev.price:,}원"
            code = f"[{ev.code}] " if ev.code else ""
            print(f"{ev.when:%m-%d %H:%M}  {ev.type:<5}  {code}{ev.product}{price}")

    if args.csv:
        args.csv.write_text(to_csv(events), encoding="utf-8-sig")
        print(f"\nCSV 저장: {args.csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
