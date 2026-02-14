from __future__ import annotations

from dataclasses import dataclass
from datetime import time


@dataclass(frozen=True)
class TaxDefault:
    tax_rate: float
    tax_rule: str


@dataclass(frozen=True)
class Config:
    stores: list[str]
    open_time: time
    close_time: time
    loyalty_present_rate: float
    tax_default: TaxDefault
    tax_change_frequency_years: int
    tax_rate_candidates: list[float]
    table_count: int
    visit_count_range: tuple[int, int]
    order_count_range: tuple[int, int]
    item_count_range: tuple[int, int]
    stay_minutes_range: tuple[int, int]
    cook_time_seconds_range: tuple[int, int]


def default_config() -> Config:
    return Config(
        stores=["S001", "S002", "S003"],
        open_time=time.fromisoformat("07:00"),
        close_time=time.fromisoformat("23:00"),
        loyalty_present_rate=0.30,
        tax_default=TaxDefault(tax_rate=0.10, tax_rule="ROUND_HALF_UP"),
        tax_change_frequency_years=3,
        tax_rate_candidates=[0.08, 0.10, 0.12],
        table_count=30,
        visit_count_range=(8, 16),
        order_count_range=(1, 3),
        item_count_range=(1, 4),
        stay_minutes_range=(35, 120),
        cook_time_seconds_range=(240, 1200),
    )
