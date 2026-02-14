from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from .ids import IdFactory
from .state import Config


@dataclass
class DayRows:
    visits: list[list[str]]
    orders: list[list[str]]
    order_items: list[list[str]]
    receipts: list[list[str]]
    customers: list[list[str]]


@dataclass(frozen=True)
class MenuItem:
    menu_item_id: str
    name: str
    category: str
    price: int
    is_kids: bool
    season: str | None = None
    event: str | None = None


@dataclass(frozen=True)
class Discount:
    discount_id: str
    name: str
    discount_type: str
    discount_value_yen: int
    discount_rate: float


@dataclass(frozen=True)
class TaxRateHistory:
    tax_rate_hist_id: str
    effective_from: date
    effective_to: date
    tax_rate: float
    tax_rule: str


MENU_ITEMS: list[MenuItem] = [
    MenuItem("M001", "Hamburg Steak", "main", 680, False),
    MenuItem("M002", "Chicken Plate", "main", 780, False),
    MenuItem("M003", "Pasta", "main", 520, False),
    MenuItem("M004", "Curry Rice", "main", 980, False),
    MenuItem("M005", "Kids Curry", "kids", 390, True),
    MenuItem("M006", "Kids Pasta", "kids", 450, True),
    MenuItem("M101", "Spring Salad", "seasonal", 620, False, season="spring"),
    MenuItem("M102", "Summer Lemon Pasta", "seasonal", 720, False, season="summer"),
    MenuItem("M103", "Autumn Mushroom Stew", "seasonal", 760, False, season="autumn"),
    MenuItem("M104", "Winter Cream Stew", "seasonal", 800, False, season="winter"),
    MenuItem("M201", "Halloween Pumpkin Pie", "event", 580, False, event="halloween"),
    MenuItem("M202", "Christmas Roast Plate", "event", 980, False, event="christmas"),
    MenuItem("M203", "Setsubun Ehou Roll", "event", 520, False, event="setsubun"),
]

DISCOUNTS: list[Discount] = [
    Discount("D001", "Always 5% Off", "rate", 0, 0.05),
    Discount("D002", "Always 100 Yen Off", "value", 100, 0.0),
]

PAYMENT_METHODS = ["cash", "card", "qr"]


def _slot_from_time(dt: datetime) -> str:
    hour = dt.hour
    if hour < 11:
        return "morning"
    if hour < 15:
        return "lunch"
    if hour < 18:
        return "afternoon"
    return "evening"


def _random_dt(rng, day: date, start_dt: datetime, end_dt: datetime) -> datetime:
    delta_sec = int((end_dt - start_dt).total_seconds())
    offset = rng.randint(0, max(delta_sec, 0))
    return start_dt + timedelta(seconds=offset)


def _round_tax(amount_yen: int, rate: float) -> int:
    dec = (Decimal(amount_yen) * Decimal(str(rate))).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    )
    return int(dec)


def _season_for_date(day: date) -> str:
    if day.month in (3, 4, 5):
        return "spring"
    if day.month in (6, 7, 8):
        return "summer"
    if day.month in (9, 10, 11):
        return "autumn"
    return "winter"


def _is_event_day(day: date, event: str) -> bool:
    if event == "halloween":
        target = date(day.year, 10, 31)
    elif event == "christmas":
        target = date(day.year, 12, 25)
    elif event == "setsubun":
        target = date(day.year, 2, 3)
    else:
        return False
    return abs((day - target).days) <= 7


def available_menu_items(day: date) -> list[MenuItem]:
    season = _season_for_date(day)
    items: list[MenuItem] = []
    for item in MENU_ITEMS:
        if item.season and item.season != season:
            continue
        if item.event and not _is_event_day(day, item.event):
            continue
        items.append(item)
    return items


def select_tax_rate(day: date, history: list[TaxRateHistory]) -> TaxRateHistory | None:
    for entry in history:
        if entry.effective_from <= day <= entry.effective_to:
            return entry
    return None


def compute_discounts(subtotal: int) -> tuple[int, list[str]]:
    discount_total = 0
    applied: list[str] = []
    for d in DISCOUNTS:
        if d.discount_type == "rate":
            amount = _round_tax(subtotal, d.discount_rate)
        else:
            amount = d.discount_value_yen
        amount = min(amount, subtotal)
        if amount > 0:
            applied.append(d.discount_id)
        discount_total += amount
    discount_total = min(discount_total, subtotal)
    return discount_total, applied


def generate_day(
    day: date,
    config: Config,
    rng,
    ids: IdFactory,
    tax_history: list[TaxRateHistory],
) -> DayRows:
    tz = ZoneInfo("Asia/Tokyo")
    open_dt = datetime.combine(day, config.open_time, tz)
    close_dt = datetime.combine(day, config.close_time, tz)
    latest_seat = close_dt - timedelta(minutes=90)

    visits: list[list[str]] = []
    orders: list[list[str]] = []
    order_items: list[list[str]] = []
    receipts: list[list[str]] = []
    customers: list[list[str]] = []

    menu_items = available_menu_items(day)
    tax_entry = select_tax_rate(day, tax_history)
    if tax_entry:
        tax_rate = tax_entry.tax_rate
        tax_rate_hist_id = tax_entry.tax_rate_hist_id
    else:
        tax_rate = config.tax_default.tax_rate
        tax_rate_hist_id = ""

    for store_id in config.stores:
        visit_count = rng.randint(*config.visit_count_range)
        for _ in range(visit_count):
            visit_id = ids.next_visit()
            table_id = f"T{rng.randint(1, config.table_count):02d}"
            seated_at = _random_dt(rng, day, open_dt, latest_seat)
            duration_min = rng.randint(*config.stay_minutes_range)
            left_at = min(seated_at + timedelta(minutes=duration_min), close_dt)

            adult_cnt = rng.randint(1, 4)
            child_cnt = rng.randint(0, 2)

            visits.append(
                [
                    visit_id,
                    store_id,
                    table_id,
                    seated_at.isoformat(),
                    left_at.isoformat(),
                    str(adult_cnt),
                    str(child_cnt),
                    day.isoformat(),
                    str(day.weekday()),
                    _slot_from_time(seated_at),
                ]
            )

            order_count = rng.randint(*config.order_count_range)
            if order_count == 1:
                order_times = [_random_dt(rng, day, seated_at, left_at)]
            else:
                span = max(int((left_at - seated_at).total_seconds()), 1)
                splits = sorted(
                    rng.sample(range(1, span), k=min(order_count - 1, span - 1))
                )
                order_times = [
                    seated_at + timedelta(seconds=offset) for offset in splits
                ]
                order_times = [seated_at] + order_times

            last_served = seated_at
            subtotal = 0
            for seq, ordered_at in enumerate(order_times, start=1):
                order_id = ids.next_order()
                orders.append(
                    [
                        order_id,
                        visit_id,
                        ordered_at.isoformat(),
                        "tablet",
                        str(seq),
                    ]
                )

                item_count = rng.randint(*config.item_count_range)
                for _ in range(item_count):
                    item = rng.choice(menu_items)
                    qty = rng.randint(1, 3)
                    unit_price = item.price
                    line_subtotal = unit_price * qty
                    cook_time = rng.randint(*config.cook_time_seconds_range)
                    served_at = ordered_at + timedelta(seconds=cook_time)
                    if served_at > close_dt:
                        served_at = close_dt - timedelta(minutes=1)
                    last_served = max(last_served, served_at)

                    order_items.append(
                        [
                            ids.next_order_item(),
                            order_id,
                            item.menu_item_id,
                            str(qty),
                            str(unit_price),
                            str(line_subtotal),
                            "served",
                            served_at.isoformat(),
                            str(cook_time),
                            "1" if item.is_kids else "0",
                        ]
                    )
                    subtotal += line_subtotal

            discount_total, applied_discounts = compute_discounts(subtotal)
            discounted_subtotal = max(subtotal - discount_total, 0)

            paid_at = last_served + timedelta(minutes=rng.randint(5, 20))
            if paid_at > close_dt:
                paid_at = close_dt

            tax_yen = _round_tax(discounted_subtotal, tax_rate)
            total_yen = discounted_subtotal + tax_yen

            if rng.random() < config.loyalty_present_rate:
                customer_id = ids.next_customer()
                customers.append([customer_id, paid_at.isoformat()])
            else:
                customer_id = ""

            receipts.append(
                [
                    ids.next_receipt(),
                    visit_id,
                    paid_at.isoformat(),
                    rng.choice(PAYMENT_METHODS),
                    customer_id,
                    str(subtotal),
                    str(discount_total),
                    f"{tax_rate:.2f}",
                    tax_rate_hist_id,
                    str(tax_yen),
                    str(total_yen),
                    "|".join(applied_discounts),
                    "0",
                    "0",
                ]
            )

    return DayRows(
        visits=visits,
        orders=orders,
        order_items=order_items,
        receipts=receipts,
        customers=customers,
    )
