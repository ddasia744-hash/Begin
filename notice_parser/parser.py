"""카카오톡 대화 내보내기(.txt)에서 공급사 공지를 읽어 상품 변동 이벤트로 바꾼다.

흐름: 원문 텍스트 → parse_messages() → 메시지 목록 → extract_events() → 이벤트 목록
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time

DATE_LINE = re.compile(r"^-+ (\d{4})년 (\d{1,2})월 (\d{1,2})일 \S+ -+$")
MESSAGE_LINE = re.compile(
    r"^\[(?P<sender>[^\]]+)\] \[(?P<ampm>오전|오후) (?P<h>\d{1,2}):(?P<m>\d{2})\] ?(?P<text>.*)$"
)
SYSTEM_SUFFIXES = (
    "님이 들어왔습니다.",
    "님이 나갔습니다.",
    "메시지가 삭제되었습니다.",
    "부방장이 되었습니다.",
    "님을 내보냈습니다.",
)

# 섹션 제목: ★품절★, *신규상품*, ※단가인상※, * 단가 인상 *, 📣공지드립니다📣 등
HEADER_LINE = re.compile(r"^(?:@all\s*)?(?P<mark>[★*※🛑📣])\s*(?P<body>[^★*※🛑📣]+?)\s*(?P=mark)\s*(?:@all)?$")

# 우선순위 순서. 앞에서 먼저 걸리는 유형을 쓴다.
TYPE_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("재오픈", ("재오픈", "재업로드")),
    ("품절예정", ("품절예정",)),
    ("품절", ("품절",)),
    ("인상예정", ("인상예정",)),
    ("단가인상", ("인상",)),
    ("단가인하", ("인하",)),
    ("출고지연", ("미출고", "미출", "출고지연", "배송지연", "지연")),
    ("전량출고", ("전량출고",)),
    ("특가", ("특가", "행사가")),
    ("신규옵션", ("신규옵션", "옵션추가")),
    ("신규상품", ("신규",)),
]
EVENT_TYPES = [name for name, _ in TYPE_RULES]

# 상품명과 섞인 제목에서 지울 말들
HEADER_NOISE = re.compile(
    r"공지사항|공지드립니다|공지|안내|필독|즉시적용|즉시|긴급|일시|금일|익일|예정|적용|"
    r"재오픈|재업로드|품절|단가|인상|인하|특가|파격|초특가|행사가|신규상품|신규옵션|신규|"
    r"옵션추가|미출고|출고지연|배송지연|지연|전량출고|당일출고|출고일정|출고|일정|업로드|완료|오픈|"
    r"관련|품목|상품|주말|\b건\b|\(\d+\)|<[^>]*>|[!,/]"
)

CODE = re.compile(r"\[([^\]\d][^\]]*|\d+[A-Za-z][^\]]*)\]")  # [1] 같은 순번은 코드가 아님
NUMBERING = re.compile(r"^\[\d+\]\s*")
PRICE_CHANGE = re.compile(r"(\d{1,3}(?:,\d{3})+|\d{4,6})\s*원?\s*(?:>|→|->)\s*(\d{1,3}(?:,\d{3})+|\d{4,6})")
PRICE = re.compile(r"(?:[₩￦]\s*)?(?<![\d.])(\d{1,3}(?:,\d{3})+|\d{4,6})(?![\d.])\s*원?(?!\s*(?:과|건|kg|KG|g|통|개|입|일|시))")
ANGLE_NOTE = re.compile(r"<([^>]*)>?\s*$")
INLINE_STAR = re.compile(r"★\s*([^★]+?)\s*★")
# 첫 줄 제목은 유형 단어로 끝나야 한다 (예: '골드키위 단가인상'). '지연으로,' 같은 문장은 제외
FIRST_LINE_HEADING = re.compile(r"(품절|재오픈|인상|인하|특가|행사가|신규상품|신규옵션|지연|전량출고)\s*(예정|안내)?\s*$")
NOT_PRODUCT = re.compile(r"^(출고|당일출고|건\b|취소|발주|주문)")
META_WORDS = ("발주", "접수", "참고", "마감", "부탁", "확인", "출고됩니다", "가능합니다", "상품리스트", "상품 리스트")


@dataclass
class Message:
    when: datetime
    sender: str
    text: str


@dataclass
class Event:
    when: datetime
    type: str
    product: str
    code: str = ""
    price: int | None = None
    price_before: int | None = None
    price_after: int | None = None
    note: str = ""
    raw: str = field(default="", repr=False)

    def to_row(self) -> dict:
        row = asdict(self)
        row["date"] = self.when.strftime("%Y-%m-%d")
        row["time"] = self.when.strftime("%H:%M")
        del row["when"]
        return row


def _to_time(ampm: str, h: str, m: str) -> time:
    hour = int(h) % 12 + (12 if ampm == "오후" else 0)
    return time(hour, int(m))


def _is_system(line: str) -> bool:
    return line.endswith(SYSTEM_SUFFIXES)


def parse_messages(text: str) -> list[Message]:
    """대화 원문을 메시지 단위로 나눈다. 입·퇴장 같은 시스템 줄은 버린다."""
    messages: list[Message] = []
    current_date: date | None = None
    current: Message | None = None

    def flush():
        nonlocal current
        if current is not None:
            current.text = current.text.rstrip()
            messages.append(current)
            current = None

    for line in text.splitlines():
        line = line.rstrip("\r")
        d = DATE_LINE.match(line)
        if d:
            flush()
            current_date = date(int(d[1]), int(d[2]), int(d[3]))
            continue
        m = MESSAGE_LINE.match(line)
        if m and current_date is not None:
            flush()
            when = datetime.combine(current_date, _to_time(m["ampm"], m["h"], m["m"]))
            current = Message(when, m["sender"].strip(), m["text"])
            continue
        if _is_system(line.strip()):
            flush()
            continue
        if current is not None:
            current.text += "\n" + line
    flush()
    return messages


def classify(text: str) -> str | None:
    """문구에 들어 있는 유형 키워드로 이벤트 유형을 정한다. 없으면 None."""
    compact = re.sub(r"\s+", "", text)
    for name, keywords in TYPE_RULES:
        if any(k in compact for k in keywords):
            return name
    return None


def _to_int(s: str) -> int:
    return int(s.replace(",", ""))


def _header_product(body: str) -> str:
    rest = HEADER_NOISE.sub(" ", body)
    rest = re.sub(r"\s+", " ", rest).strip(" -:")
    return rest


def parse_item(line: str, section_type: str, header_product: str = "") -> Event | None:
    """상품 한 줄을 이벤트로 만든다. 상품 줄이 아니면 None."""
    raw = line.strip()
    s = raw
    is_bullet = s.startswith(("-", "•", "·", "▶")) or s.startswith("[")
    s = s.lstrip("-•·▶ ").strip()
    s = NUMBERING.sub("", s)
    s = s.replace("★VIP코드★", "").replace("@all", "").strip()
    if not s:
        return None

    def find_prices(text):
        ch = PRICE_CHANGE.search(text)
        return ch, (None if ch else PRICE.search(text))

    change, price_m = find_prices(s)
    if not is_bullet:
        # 글머리표가 없는 줄은 가격이 있을 때만 상품 줄로 본다 (안내 문장 제외)
        if not (change or price_m) or any(w in s for w in META_WORDS):
            return None

    item_type = section_type
    note = ""
    angle = ANGLE_NOTE.search(s)
    if angle:
        note = angle.group(1).strip()
        override = classify(note)
        if override:
            item_type = override
        s = s[: angle.start()].strip()

    code = ""
    c = CODE.search(s)
    if c:
        code = c.group(1).strip()
        s = (s[: c.start()] + s[c.end():]).strip()
    # [제휴GSB-05] [G-50] 처럼 코드가 두 개 붙은 경우 두 번째도 떼어 낸다
    s = CODE.sub("", s).strip()
    # 상품명 안의 ★특가★ 표시는 (특가)로 바꿔 읽기 쉽게
    s = INLINE_STAR.sub(lambda m: f"({m.group(1)})" if m.group(1) != "VIP코드" else "", s).strip()

    ev = Event(when=datetime.min, type=item_type, product="", code=code, note=note, raw=raw)
    change, price_m = find_prices(s)  # 코드·메모를 떼어 낸 뒤 위치를 다시 잡는다
    if change:
        ev.price_before, ev.price_after = _to_int(change[1]), _to_int(change[2])
        s = (s[: change.start()] + s[change.end():]).strip()
        if item_type not in ("단가인상", "단가인하"):
            ev.type = "단가인상" if ev.price_after > ev.price_before else "단가인하"
    elif price_m:
        ev.price = _to_int(price_m[1])
        s = (s[: price_m.start()] + s[price_m.end():]).strip()
    s = re.sub(r"\s*/\s*$", "", s).strip(" :/")
    if header_product and not code:
        # '★노지감귤 대과 단가인상★' 아래 '- 대과 5KG ...'처럼 상품명을 생략한 줄은
        # 제목에 있는 상품명 중 줄에 없는 단어를 앞에 붙인다
        words = header_product.split()
        missing = [w for w in words if w not in s]
        if words[0] in missing or s[:1].isdigit():
            s = " ".join(missing + [s]).strip()
    if not s:
        s = header_product
    if not s or NOT_PRODUCT.match(s):
        return None
    ev.product = re.sub(r"\s+", " ", s)
    return ev


def _inline_event(line: str) -> Event | None:
    """제목 없이 한 줄로 쓴 공지. 예: '[제휴D-01] 설봉감자 품절', '사과 <즉시품절>'."""
    t = classify(line)
    if t is None or t == "신규상품" and "[" not in line:
        return None
    s = line.strip()
    angle = ANGLE_NOTE.search(s)
    body = s
    if angle:
        body = s[: angle.start()]
    else:
        # 맨 끝의 유형 단어(품절, 즉시품절, 인상 등)를 떼어 낸다
        body = re.sub(r"\s*(즉시|긴급|일시)?\s*(품절|재오픈|인상|인하)\s*(예정)?\s*$", "", s)
    if body == s and not angle:
        return None  # 상품명 뒤에 유형이 붙은 형태가 아니면 문장으로 보고 건너뜀
    ev = parse_item("- " + body.strip(), t)
    if ev and angle:
        ev.note = angle.group(1).strip()
    return ev


def extract_events(messages: list[Message], sender_filter: str | None = None) -> list[Event]:
    """메시지 목록에서 이벤트를 뽑는다.

    sender_filter를 주면 그 문자열이 보낸 사람 이름에 들어간 메시지만 본다.
    주지 않으면 가장 글을 많이 쓴 사람(봇 제외)을 공급사로 본다.
    """
    if sender_filter is None:
        sender_filter = guess_supplier(messages)
    events: list[Event] = []
    for msg in messages:
        if sender_filter and sender_filter not in msg.sender:
            continue
        events.extend(_events_from_message(msg))
    return events


def guess_supplier(messages: list[Message]) -> str:
    counts: dict[str, int] = {}
    for msg in messages:
        if "봇" in msg.sender:
            continue
        counts[msg.sender] = counts.get(msg.sender, 0) + 1
    return max(counts, key=counts.get) if counts else ""


def _events_from_message(msg: Message) -> list[Event]:
    out: list[Event] = []
    section_type: str | None = None
    header_product = ""
    header_used = True
    lines = msg.text.split("\n")

    def close_section():
        nonlocal header_used
        if section_type and not header_used and header_product and not NOT_PRODUCT.match(header_product):
            out.append(Event(msg.when, section_type, header_product, raw=header_product))
        header_used = True

    for i, line in enumerate(lines):
        s = line.strip()
        if not s or s == "@all":
            continue
        h = HEADER_LINE.match(s)
        if h:
            close_section()
            section_type = classify(h["body"])
            header_product = _header_product(h["body"]) if section_type else ""
            header_used = not header_product
            continue
        if section_type is None:
            # 제목 없는 메시지: 첫 줄이 '... 품절' 같은 한 줄 공지인지 본다
            ev = _inline_event(s)
            if ev:
                ev.when = msg.when
                out.append(ev)
            elif i == 0:
                t = classify(s)
                if t and FIRST_LINE_HEADING.search(s) and not any(w in s for w in META_WORDS):
                    # '★노지감귤 대과 단가인상★' 없이 '골드키위 단가인상' 같은 첫 줄 제목
                    section_type, header_product = t, _header_product(s)
                    header_used = not header_product
            continue
        ev = parse_item(s, section_type, header_product)
        if ev:
            ev.when = msg.when
            out.append(ev)
            header_used = True
    close_section()
    return out


def parse_chat(text: str, sender_filter: str | None = None) -> tuple[list[Message], list[Event]]:
    messages = parse_messages(text)
    return messages, extract_events(messages, sender_filter)
