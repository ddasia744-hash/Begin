"""지역명(시/도-구/군-동) <-> 법정동코드 검색 유틸리티."""
import json
import os

DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "naver_rls.json")


def _load_regions():
    with open(DATA_PATH, encoding="utf-8") as f:
        raw = json.load(f)

    flat = []
    for sido, gu_dict in raw.items():
        for gu, dong_dict in gu_dict.items():
            for dong, code in dong_dict.items():
                flat.append(
                    {
                        "sido": sido,
                        "gu": gu,
                        "dong": dong,
                        "code": code,
                        "full_name": f"{sido} {gu} {dong}",
                    }
                )
    return flat


REGIONS = _load_regions()


def search(query: str, limit: int = 20):
    """지역명 부분 문자열로 검색. 동 이름이 일치하는 결과를 우선 노출."""
    query = query.strip()
    if not query:
        return []

    tokens = query.split()
    exact_dong, prefix_dong, contains = [], [], []

    for r in REGIONS:
        haystack = r["full_name"]
        if not all(t in haystack for t in tokens):
            continue
        if r["dong"] == query:
            exact_dong.append(r)
        elif r["dong"].startswith(query):
            prefix_dong.append(r)
        else:
            contains.append(r)

    ordered = exact_dong + prefix_dong + contains
    return ordered[:limit]


def find_by_code(code: str):
    for r in REGIONS:
        if r["code"] == code:
            return r
    return None
