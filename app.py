"""네이버 부동산 매물 조회 웹앱.

지역명을 입력하면 법정동코드(data/naver_rls.json)로 변환한 뒤,
네이버 부동산 비공식 API(new.land.naver.com)에서 매물 목록을 가져온다.
"""
import requests
from flask import Flask, jsonify, render_template, request

import region_lookup

app = Flask(__name__)

NAVER_ARTICLES_URL = "https://new.land.naver.com/api/articles"
NAVER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://new.land.naver.com/complexes",
    "Accept": "application/json",
}

TRADE_TYPES = {"A1": "매매", "B1": "전세", "B2": "월세"}
REAL_ESTATE_TYPES = {"APT": "아파트", "OPST": "오피스텔", "VL": "빌라", "OR": "원룸"}


@app.get("/")
def index():
    return render_template(
        "index.html", trade_types=TRADE_TYPES, real_estate_types=REAL_ESTATE_TYPES
    )


@app.get("/api/regions")
def api_regions():
    query = request.args.get("q", "")
    results = region_lookup.search(query)
    return jsonify(results)


@app.get("/api/listings")
def api_listings():
    cortar_no = request.args.get("cortarNo")
    if not cortar_no:
        return jsonify({"error": "cortarNo 파라미터가 필요합니다."}), 400

    params = {
        "cortarNo": cortar_no,
        "realEstateType": request.args.get("realEstateType", "APT"),
        "tradeType": request.args.get("tradeType", "A1"),
        "page": request.args.get("page", "1"),
        "order": "rank",
    }

    try:
        resp = requests.get(
            NAVER_ARTICLES_URL, params=params, headers=NAVER_HEADERS, timeout=10
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as e:
        return (
            jsonify(
                {
                    "error": "네이버 부동산 API 호출에 실패했습니다.",
                    "detail": str(e),
                }
            ),
            502,
        )
    except ValueError:
        return (
            jsonify({"error": "네이버 부동산 응답을 해석할 수 없습니다 (JSON 아님)."}),
            502,
        )

    articles = data.get("articleList", [])
    simplified = [
        {
            "id": a.get("articleNo"),
            "name": a.get("articleName"),
            "type": a.get("realEstateTypeName"),
            "tradeType": a.get("tradeTypeName"),
            "price": a.get("dealOrWarrantPrc"),
            "rentPrice": a.get("rentPrc"),
            "area": a.get("area2"),
            "floor": a.get("floorInfo"),
            "direction": a.get("direction"),
            "confirmDate": a.get("articleConfirmYmd"),
            "description": a.get("articleFeatureDesc"),
            "realtor": a.get("realtorName"),
        }
        for a in articles
    ]

    return jsonify({"count": len(simplified), "isMoreData": data.get("isMoreData", False), "articles": simplified})


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
