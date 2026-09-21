from unittest.mock import MagicMock, patch

import pytest
import requests

import app as app_module


@pytest.fixture
def client():
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


def test_index_page(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "지역명을 입력하세요".encode() in resp.data


def test_api_regions_returns_matches(client):
    resp = client.get("/api/regions?q=역삼")
    assert resp.status_code == 200
    data = resp.get_json()
    assert any(r["dong"] == "역삼동" for r in data)


def test_api_listings_missing_cortarno(client):
    resp = client.get("/api/listings")
    assert resp.status_code == 400


def test_api_listings_success(client):
    fake_response = MagicMock()
    fake_response.raise_for_status.return_value = None
    fake_response.json.return_value = {
        "isMoreData": True,
        "articleList": [
            {
                "articleNo": "123456",
                "articleName": "래미안대치팰리스",
                "realEstateTypeName": "아파트",
                "tradeTypeName": "매매",
                "dealOrWarrantPrc": "250,000",
                "rentPrc": "",
                "area2": "84.99",
                "floorInfo": "10/20",
                "direction": "남향",
                "articleConfirmYmd": "20250101",
                "articleFeatureDesc": "역세권 급매",
                "realtorName": "OO공인중개사",
            }
        ],
    }

    with patch("app.requests.get", return_value=fake_response) as mock_get:
        resp = client.get("/api/listings?cortarNo=1168010100&page=2")

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["count"] == 1
    assert data["isMoreData"] is True
    assert data["articles"][0]["name"] == "래미안대치팰리스"
    assert data["articles"][0]["price"] == "250,000"

    called_params = mock_get.call_args.kwargs["params"]
    assert called_params["cortarNo"] == "1168010100"
    assert called_params["page"] == "2"


def test_api_listings_network_failure_returns_502(client):
    with patch("app.requests.get", side_effect=requests.exceptions.ConnectionError("boom")):
        resp = client.get("/api/listings?cortarNo=1168010100")

    assert resp.status_code == 502
    data = resp.get_json()
    assert "실패" in data["error"]


def test_api_listings_bad_json_returns_502(client):
    fake_response = MagicMock()
    fake_response.raise_for_status.return_value = None
    fake_response.json.side_effect = ValueError("not json")

    with patch("app.requests.get", return_value=fake_response):
        resp = client.get("/api/listings?cortarNo=1168010100")

    assert resp.status_code == 502
