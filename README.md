# 네이버 부동산 매물 조회 웹앱

지역명(예: "강남구 역삼동")을 검색하면 `data/naver_rls.json`(법정동코드 매핑 데이터)을 통해
법정동코드로 변환하고, 네이버 부동산 비공식 API에서 해당 지역의 매물 목록을 조회합니다.

## 구조

- `app.py` — Flask 백엔드. 지역 검색 API와 네이버 부동산 매물 조회 프록시 API 제공
- `region_lookup.py` — `data/naver_rls.json`을 읽어 지역명 검색/코드 변환 로직 담당
- `data/naver_rls.json` — 시/도 → 구/군 → 동 → 법정동코드 매핑 데이터
- `templates/index.html`, `static/` — 검색창 + 결과 화면 프론트엔드

## 실행 방법

```bash
pip install -r requirements.txt
python3 app.py
```

브라우저에서 `http://localhost:5000` 접속 후, 검색창에 지역명을 입력하고
자동완성 목록에서 지역을 선택한 뒤 "매물 조회" 버튼을 누르면 매물 목록이 표시됩니다.

## API

- `GET /api/regions?q=<검색어>` — 지역명 부분 일치 검색, 법정동코드 반환
- `GET /api/listings?cortarNo=<코드>&realEstateType=APT&tradeType=A1&page=1` — 매물 목록 조회
  - `realEstateType`: `APT`(아파트), `OPST`(오피스텔), `VL`(빌라), `OR`(원룸)
  - `tradeType`: `A1`(매매), `B1`(전세), `B2`(월세)

## 참고 사항

- 네이버 부동산 API(`new.land.naver.com`)는 비공식(비공개) 엔드포인트이므로, 요청 헤더나
  인증 방식이 사전 예고 없이 변경될 수 있습니다. 응답이 실패하면 `/api/listings`가
  502와 함께 오류 메시지를 반환하니 이를 참고해 헤더/파라미터를 조정하세요.
- 이 저장소 개발 환경(샌드박스)은 아웃바운드 네트워크 정책상 `new.land.naver.com`으로의
  직접 접속이 차단되어 있어, 매물 조회 API는 이 환경에서 end-to-end로 테스트하지
  못했습니다. 인터넷 접속이 열린 환경에서 실행해 동작을 확인하세요. 지역 검색
  (`/api/regions`)은 외부 네트워크 없이 완전히 동작을 확인했습니다.

---

# 공급사 공지 → 품절·단가 변동 표 (`notice_parser`)

농수산물 위탁판매 공급사가 카카오톡 공지방에 올리는 공지(품절, 단가 인상·인하, 특가, 신규 상품,
재오픈, 출고지연 등)를 읽어 상품별 이벤트 표로 정리합니다. 배경과 사업 전략은
`docs/농산물_위탁판매_사업화_전략.md`를 참고하세요.

## 사용법

카카오톡 공지방에서 **대화 내보내기**로 받은 `.txt` 파일을 준비합니다.

웹 페이지: `python3 app.py` 실행 후 `http://localhost:5000/notices`에서 파일을 올립니다.
관심 품목, 기간, 유형으로 거를 수 있고 CSV(엑셀용)로 내려받을 수 있습니다.
업로드한 파일은 서버에 저장하지 않습니다.

명령줄:

```bash
python3 -m notice_parser 대화.txt
python3 -m notice_parser 대화.txt --watch 감귤,사과 --since 2026-10-01 --status
python3 -m notice_parser 대화.txt --type 품절,단가인상 --csv events.csv
```

## 구조

- `notice_parser/parser.py` — 대화를 메시지로 나누고(입·퇴장 등 시스템 줄 제외), 공급사 메시지에서
  `★품절★`, `*신규상품*`, `※단가인상※` 같은 제목과 그 아래 상품 줄을 이벤트로 바꿉니다.
  상품코드(`[제휴C-01]`), 가격(`12,000`), 가격 변동(`10,500 > 12,000`), 꺾쇠 메모(`<즉시품절>`)를 뽑습니다.
  공급사는 글을 가장 많이 쓴 사람(봇 제외)으로 자동 판단하며 `--sender`로 지정할 수 있습니다.
- `notice_parser/report.py` — 필터, 상품별 현재 상태(마지막 공지가 품절이면 판매불가), 요약, CSV
- `notice_parser/web.py`, `templates/notices.html`, `static/notices.css` — 업로드 페이지

## 한계

공지 문구는 사람이 자유롭게 쓰므로 규칙 기반 파싱에는 빈틈이 있습니다. 예를 들어 제목 없이 문장으로만
쓴 공지나 같은 상품의 다른 표기(띄어쓰기, 옵션명)는 별개 상품으로 잡힐 수 있습니다.
실제 공지방 10개월치(약 1,060개 공지)로 확인했을 때 약 3,500건의 이벤트가 추출되었습니다.
