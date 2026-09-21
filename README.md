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
