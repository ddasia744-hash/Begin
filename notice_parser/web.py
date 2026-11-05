"""대화 파일을 올리면 품절·단가 변동 표를 보여주는 웹 페이지 (Flask Blueprint)."""
from __future__ import annotations

from datetime import date

from flask import Blueprint, Response, render_template, request

from . import EVENT_TYPES, filter_events, latest_status, parse_chat, summarize, to_csv

bp = Blueprint("notices", __name__)

MAX_ROWS = 500


def _parse_date(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


@bp.get("/notices")
def notices_form():
    return render_template("notices.html", event_types=EVENT_TYPES, form={}, result=None, error=None)


@bp.post("/notices")
def notices_result():
    form = request.form
    upload = request.files.get("chat")
    if upload is None or not upload.filename:
        return _render_error("카카오톡 대화 파일(.txt)을 선택하세요.", form), 400
    raw = upload.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return _render_error("UTF-8 텍스트 파일만 읽을 수 있습니다. 카카오톡 '대화 내보내기' 파일을 올려 주세요.", form), 400

    messages, events = parse_chat(text, form.get("sender") or None)
    if not messages:
        return _render_error("대화 내용을 찾지 못했습니다. 카카오톡 '대화 내보내기' 형식이 맞는지 확인하세요.", form), 400

    types = request.form.getlist("types")
    events = filter_events(
        events,
        since=_parse_date(form.get("since")),
        until=_parse_date(form.get("until")),
        keywords=(form.get("watch") or "").split(","),
        types=types or None,
    )

    if form.get("output") == "csv":
        return Response(
            "﻿" + to_csv(events),
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=notice_events.csv"},
        )

    events_sorted = sorted(events, key=lambda e: e.when, reverse=True)
    status = latest_status(events)
    result = {
        "summary": summarize(events),
        "messages": len(messages),
        "events": events_sorted[:MAX_ROWS],
        "status": status[:MAX_ROWS],
        "unavailable": [r for r in status if not r["available"]][:MAX_ROWS],
        "truncated": len(events_sorted) > MAX_ROWS,
    }
    return render_template("notices.html", event_types=EVENT_TYPES, form=form, result=result, error=None, types=types)


def _render_error(message: str, form):
    return render_template("notices.html", event_types=EVENT_TYPES, form=form, result=None, error=message)
