"""수익 계산: 포이즌 판매가에서 수수료·배송비·목표 수익을 빼고 '최대 매입가'를 구한다.

수수료율 등 기본값은 예시일 뿐이다. 반드시 POIZON 셀러센터의 수수료 안내를 확인해
fees.json 을 실제 값으로 수정해서 사용한다.
"""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, fields


@dataclass
class FeeConfig:
    commission_rate: float = 0.10       # 판매 수수료율 (예시값)
    commission_min: int = 0             # 수수료 최저액 (없으면 0)
    commission_max: int = 0             # 수수료 상한액 (없으면 0)
    fixed_fee: int = 0                  # 건당 고정 수수료(검수/서비스료 등)
    ship_to_poizon: int = 4000          # 포이즌 검수센터로 보내는 택배비
    ship_from_shop: int = 3000          # 국내 쇼핑몰 구매 시 배송비(가정)
    min_profit: int = 5000              # 건당 최소 순수익(원)
    target_margin_rate: float = 0.05    # 매입가 대비 최소 수익률
    min_price_ratio: float = 0.4        # 포이즌가의 이 비율 미만 국내가는 액세서리/오매칭으로 보고 제외

    @classmethod
    def load(cls, path: str | None) -> "FeeConfig":
        if not path:
            return cls()
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in raw.items() if k in known})

    def to_dict(self) -> dict:
        return asdict(self)


def commission(sale_price: int, cfg: FeeConfig) -> int:
    fee = sale_price * cfg.commission_rate
    if cfg.commission_min:
        fee = max(fee, cfg.commission_min)
    if cfg.commission_max:
        fee = min(fee, cfg.commission_max)
    return int(round(fee))


def payout(sale_price: int, cfg: FeeConfig) -> int:
    """포이즌에서 sale_price 에 팔렸을 때 판매자가 실제로 받는 정산금."""
    return sale_price - commission(sale_price, cfg) - cfg.fixed_fee


def net_profit(sale_price: int, buy_price: int, cfg: FeeConfig) -> int:
    """매입가 buy_price(상품가, 배송비 제외)로 사서 sale_price 에 팔 때의 순수익."""
    return payout(sale_price, cfg) - cfg.ship_to_poizon - cfg.ship_from_shop - buy_price


def max_buy_price(sale_price: int, cfg: FeeConfig) -> int:
    """최소 순수익과 목표 수익률을 모두 만족하는 최대 매입가(상품가 기준). 음수면 0."""
    available = payout(sale_price, cfg) - cfg.ship_to_poizon - cfg.ship_from_shop
    by_amount = available - cfg.min_profit
    by_rate = available / (1 + cfg.target_margin_rate)
    return max(0, math.floor(min(by_amount, by_rate)))
