import csv
from unittest.mock import MagicMock

from poizon_sourcing import naver_shop
from poizon_sourcing.find_deals import find_deals, main, parse_price, read_products
from poizon_sourcing.margin import FeeConfig, max_buy_price, net_profit, payout

CFG = FeeConfig(commission_rate=0.10, fixed_fee=0, ship_to_poizon=4000,
                ship_from_shop=3000, min_profit=5000, target_margin_rate=0.05)


def test_payout_and_profit():
    assert payout(82000, CFG) == 73800
    assert net_profit(82000, 50000, CFG) == 73800 - 7000 - 50000


def test_max_buy_price_satisfies_both_constraints():
    limit = max_buy_price(82000, CFG)
    profit = net_profit(82000, limit, CFG)
    assert profit >= CFG.min_profit
    assert profit >= limit * CFG.target_margin_rate - 1


def test_max_buy_price_zero_for_cheap_items():
    assert max_buy_price(6000, CFG) == 0


def test_commission_min_max():
    cfg = FeeConfig(commission_rate=0.1, commission_min=3000, commission_max=20000)
    assert payout(10000, cfg) == 7000
    assert payout(500000, cfg) == 480000


def test_title_matching_ignores_case_and_separators():
    assert naver_shop.title_matches_model("아디다스 슈퍼스타 <b>JI-0079</b>", "JI0079")
    assert not naver_shop.title_matches_model("아디다스 슈퍼스타 JH9977", "JI0079")


def test_search_parses_items():
    session = MagicMock()
    session.get.return_value.json.return_value = {"items": [
        {"title": "<b>JI0079</b> 슈퍼스타 &amp; 2", "lprice": "55000", "mallName": "A몰",
         "link": "https://a.example/1", "productId": "1"},
        {"title": "bad", "lprice": "", "mallName": "B", "link": "x"},
    ]}
    items = naver_shop.search("JI0079", "id", "secret", session=session)
    assert items == [{"title": "JI0079 슈퍼스타 & 2", "price": 55000, "mall": "A몰",
                      "url": "https://a.example/1", "brand": "", "product_id": "1"}]
    headers = session.get.call_args.kwargs["headers"]
    assert headers["X-Naver-Client-Id"] == "id"


def test_find_deals_filters_by_limit_model_and_keywords():
    products = [{"model_no": "JI0079", "name": "슈퍼스타", "brand": "아디다스", "poizon_price": 82000}]
    offers = [
        {"title": "슈퍼스타 JI0079", "price": 50000, "mall": "싼몰", "url": "u1"},
        {"title": "슈퍼스타 JI0079", "price": 80000, "mall": "비싼몰", "url": "u2"},
        {"title": "중고 슈퍼스타 JI0079", "price": 30000, "mall": "중고몰", "url": "u3"},
        {"title": "슈퍼스타 JH9977", "price": 30000, "mall": "다른모델", "url": "u4"},
    ]
    deals = find_deals(products, CFG, lambda q: offers)
    assert [d["mall"] for d in deals] == ["싼몰"]
    assert deals[0]["est_profit"] == net_profit(82000, 50000, CFG)


def test_parse_price_and_read_products(tmp_path):
    assert parse_price("₩82,000") == 82000
    p = tmp_path / "p.csv"
    p.write_text("model_no,name,poizon_price\nJI0079,슈퍼스타,\"₩82,000\"\n,빈값,1000\n", encoding="utf-8")
    assert read_products(str(p)) == [
        {"model_no": "JI0079", "name": "슈퍼스타", "brand": "", "poizon_price": 82000}]


def test_main_requires_credentials(monkeypatch, tmp_path):
    monkeypatch.delenv("NAVER_CLIENT_ID", raising=False)
    monkeypatch.delenv("NAVER_CLIENT_SECRET", raising=False)
    assert main(["x.csv", "--out", str(tmp_path / "o.csv")]) == 2


def test_main_writes_csv(monkeypatch, tmp_path):
    monkeypatch.setenv("NAVER_CLIENT_ID", "id")
    monkeypatch.setenv("NAVER_CLIENT_SECRET", "secret")
    monkeypatch.setattr(naver_shop, "search", lambda *a, **k: [
        {"title": "JI0079 슈퍼스타", "price": 50000, "mall": "싼몰", "url": "u1"}])
    out = tmp_path / "deals.csv"
    assert main(["poizon_sourcing/products.example.csv", "--out", str(out), "--delay", "0"]) == 0
    rows = list(csv.DictReader(open(out, encoding="utf-8-sig")))
    assert rows and rows[0]["model_no"] == "JI0079"
