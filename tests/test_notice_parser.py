import io
from datetime import date, datetime

import pytest

import app as app_module
from notice_parser import classify, filter_events, latest_status, parse_chat, parse_messages, summarize, to_csv

SUPPLIER = "주식회사 테스트유통 농업회사법인"

# 실제 카카오톡 '대화 내보내기' 형식을 흉내 낸 가짜 대화
SAMPLE = f"""테스트 공지방 님과 카카오톡 대화
저장한 날짜 : 2026-11-05 14:31:06

--------------- 2026년 2월 20일 금요일 ---------------
즐거운 라이언님이 들어왔습니다.
[{SUPPLIER}] [오전 7:39] @all ★단가인상★

- [제휴C-01] 제주 콜라비
- 제주 월동무 <재오픈 예정>

<상품리스트 공급가 참고>
오전10시 즉시적용

★품절★

- 고흥유자

2kg 소과,중과,대과
못난이만 공급
슬픈 어피치님이 나갔습니다.
[{SUPPLIER}] [오후 12:54] ★노지감귤 대과 단가인상★

- 대과 5KG 10,500 > 12,000
- 대과 10KG 16,500 > 19,000

잔여 발주건 있으신 대표님들은
오후 4시까지 접수 주시면
[오픈채팅봇] [오후 1:00] [상품리스트 시트]
https://example.com/sheet
[{SUPPLIER}] [오후 8:09] ★노지 감귤 대과 품절★

익일(21일) 오후 6시까지
잔여 발주 주문 접수 부탁드립니다
메시지가 삭제되었습니다.
--------------- 2026년 2월 21일 토요일 ---------------
[{SUPPLIER}] [오전 10:47] [제휴D-01] 설봉감자 품절
[{SUPPLIER}] [오전 11:02] ★특가★

(특가) 노지 신비복숭아 500g 3-9과 4,900
[E05] 참외 10KG ₩13,300
- ★특가★ 함안 단감 가정용 [아이스박스]
[{SUPPLIER}] [오후 1:27] 백도 말랑이 털 복숭아 <즉시품절>
[{SUPPLIER}] [오후 3:00] 무화과 수확 지연으로,
이번 주 일요일부터 주문 접수 부탁드리겠습니다
[{SUPPLIER}] [오후 9:46] ※2월 22일 공지사항※

※신규상품※

- [제휴-LD] (특가) 부사 사과
[1] [제휴CCC] 하코드살구

* 재오픈 *
- 고흥유자
일반 참여자님이 들어왔습니다.
[일반 셀러] [오후 9:50] 감사합니다 ★품절★ 아님
"""


@pytest.fixture
def parsed():
    return parse_chat(SAMPLE)


def find(events, product):
    return [e for e in events if e.product == product]


def test_parse_messages_splits_and_skips_system_lines():
    msgs = parse_messages(SAMPLE)
    assert msgs[0].when == datetime(2026, 2, 20, 7, 39)
    assert msgs[0].sender == SUPPLIER
    # 시스템 줄은 메시지 본문에 섞이지 않는다
    assert all("들어왔습니다" not in m.text and "나갔습니다" not in m.text for m in msgs)
    # 오후 12시는 정오
    assert any(m.when == datetime(2026, 2, 20, 12, 54) for m in msgs)
    assert {m.sender for m in msgs} == {SUPPLIER, "오픈채팅봇", "일반 셀러"}


def test_only_supplier_messages_are_used(parsed):
    _, events = parsed
    assert not find(events, "아님")


def test_section_headers_and_bullets(parsed):
    _, events = parsed
    (kohlrabi,) = find(events, "제주 콜라비")
    assert kohlrabi.type == "단가인상" and kohlrabi.code == "제휴C-01"
    # 꺾쇠 메모에 유형이 있으면 그 유형이 우선
    (radish,) = find(events, "제주 월동무")
    assert radish.type == "재오픈" and radish.note == "재오픈 예정"
    yuzu = find(events, "고흥유자")
    assert [e.type for e in yuzu] == ["품절", "재오픈"]
    # 옵션 설명 줄은 상품이 아님
    assert not find(events, "못난이만 공급")


def test_price_change_uses_header_product(parsed):
    _, events = parsed
    (big5,) = find(events, "노지감귤 대과 5KG")
    assert (big5.type, big5.price_before, big5.price_after) == ("단가인상", 10500, 12000)


def test_header_only_event(parsed):
    _, events = parsed
    (ev,) = find(events, "노지 감귤 대과")
    assert ev.type == "품절"


def test_inline_notices(parsed):
    _, events = parsed
    (potato,) = find(events, "설봉감자")
    assert potato.type == "품절" and potato.code == "제휴D-01"
    (peach,) = find(events, "백도 말랑이 털 복숭아")
    assert peach.type == "품절" and peach.note == "즉시품절"


def test_sentence_is_not_an_event(parsed):
    _, events = parsed
    assert not [e for e in events if "무화과" in e.product]


def test_special_prices(parsed):
    _, events = parsed
    (shinbi,) = find(events, "(특가) 노지 신비복숭아 500g 3-9과")
    assert shinbi.type == "특가" and shinbi.price == 4900
    (melon,) = find(events, "참외 10KG")
    assert melon.price == 13300 and melon.code == "E05"
    (persimmon,) = find(events, "(특가) 함안 단감 가정용")
    assert persimmon.type == "특가"


def test_nested_sections_and_numbering(parsed):
    _, events = parsed
    (apple,) = find(events, "(특가) 부사 사과")
    assert apple.type == "신규상품" and apple.code == "제휴-LD"
    (apricot,) = find(events, "하코드살구")
    assert apricot.code == "제휴CCC"


def test_classify():
    assert classify("즉시 품절") == "품절"
    assert classify("단가 인상 예정") == "인상예정"
    assert classify("가격 인하") == "단가인하"
    assert classify("주말 파격특가") == "특가"
    assert classify("공지사항") is None


def test_latest_status_and_summary(parsed):
    _, events = parsed
    status = {r["product"]: r for r in latest_status(events)}
    assert status["고흥유자"]["available"] is True  # 품절 후 재오픈
    assert status["설봉감자"]["available"] is False
    assert status["노지감귤 대과 5KG"]["price"] == 12000
    s = summarize(events)
    assert s["total"] == len(events)
    assert dict(s["by_type"])["품절"] >= 3


def test_filter_events(parsed):
    _, events = parsed
    assert {e.product for e in filter_events(events, keywords=["감귤"])} == {
        "노지감귤 대과 5KG",
        "노지감귤 대과 10KG",
        "노지 감귤 대과",
    }
    assert all(e.code == "E05" for e in filter_events(events, keywords=["e05"]))
    assert all(e.when.date() == date(2026, 2, 21) for e in filter_events(events, since=date(2026, 2, 21)))
    assert all(e.type == "품절" for e in filter_events(events, types=["품절"]))


def test_to_csv(parsed):
    _, events = parsed
    lines = to_csv(events).splitlines()
    assert lines[0].startswith("date,time,type,code,product")
    assert len(lines) == len(events) + 1


def test_cli(tmp_path, capsys):
    from notice_parser.__main__ import main

    chat = tmp_path / "chat.txt"
    chat.write_text(SAMPLE, encoding="utf-8")
    out_csv = tmp_path / "out.csv"
    assert main([str(chat), "--watch", "감귤", "--status", "--csv", str(out_csv)]) == 0
    out = capsys.readouterr().out
    assert "이벤트 3건" in out and "판매불가" in out
    assert out_csv.read_text(encoding="utf-8-sig").count("\n") == 4


@pytest.fixture
def client():
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


def _post(client, **fields):
    data = {"chat": (io.BytesIO(SAMPLE.encode("utf-8")), "chat.txt"), **fields}
    return client.post("/notices", data=data, content_type="multipart/form-data")


def test_web_form(client):
    resp = client.get("/notices")
    assert resp.status_code == 200
    assert "대화 파일".encode() in resp.data


def test_web_upload_renders_tables(client):
    resp = _post(client, output="html", watch="감귤")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "노지감귤 대과 5KG" in body and "10,500 → 12,000" in body
    assert "설봉감자" not in body  # 관심 품목 필터


def test_web_csv_download(client):
    resp = _post(client, output="csv", types="품절")
    assert resp.status_code == 200
    assert resp.mimetype == "text/csv"
    text = resp.get_data(as_text=True)
    assert "설봉감자" in text and "제주 콜라비" not in text


def test_web_errors(client):
    resp = client.post("/notices", data={}, content_type="multipart/form-data")
    assert resp.status_code == 400
    bad = {"chat": (io.BytesIO("그냥 텍스트".encode()), "x.txt")}
    resp = client.post("/notices", data=bad, content_type="multipart/form-data")
    assert resp.status_code == 400
