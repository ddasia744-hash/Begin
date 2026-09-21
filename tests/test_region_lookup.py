import region_lookup


def test_load_regions_count():
    assert len(region_lookup.REGIONS) == 5044


def test_search_exact_dong_ranks_first():
    results = region_lookup.search("역삼동")
    assert results[0]["dong"] == "역삼동"
    assert results[0]["code"] == "1168010100"


def test_search_prefix_match():
    results = region_lookup.search("역삼")
    assert any(r["dong"] == "역삼동" for r in results)


def test_search_multi_token():
    results = region_lookup.search("강남구 역삼")
    assert results[0]["full_name"] == "서울시 강남구 역삼동"


def test_search_empty_query_returns_empty():
    assert region_lookup.search("") == []
    assert region_lookup.search("   ") == []


def test_search_no_match_returns_empty():
    assert region_lookup.search("존재하지않는동이름xyz") == []


def test_search_respects_limit():
    results = region_lookup.search("동", limit=5)
    assert len(results) <= 5


def test_find_by_code():
    region = region_lookup.find_by_code("1168010100")
    assert region["dong"] == "역삼동"
    assert region["gu"] == "강남구"


def test_find_by_code_missing():
    assert region_lookup.find_by_code("0000000000") is None
