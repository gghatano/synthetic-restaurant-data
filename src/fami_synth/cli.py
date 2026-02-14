from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import random

from . import __version__
from .generator_day import DISCOUNTS, MENU_ITEMS, TaxRateHistory, generate_day
from .ids import IdFactory
from .io_csv import (
    HEADERS,
    append_rows,
    ensure_header,
    file_has_only_header,
    read_existing_state,
)
from .state import default_config


@dataclass(frozen=True)
class GenerateParams:
    start: date
    end: date
    seed: int
    out_dir: Path
    force: bool
    table_count: int | None = None
    visit_range: tuple[int, int] | None = None
    order_range: tuple[int, int] | None = None
    item_range: tuple[int, int] | None = None
    stay_range: tuple[int, int] | None = None
    cook_range: tuple[int, int] | None = None


def _date_range(start: date, end: date) -> list[date]:
    days = []
    cur = start
    while cur < end:
        days.append(cur)
        cur += timedelta(days=1)
    return days


def _seed_for_day(seed: int, day: date) -> int:
    # Stable across Python processes (avoid hash randomization).
    return (seed * 1_000_003 + day.toordinal()) & 0xFFFFFFFF


def _parse_range(value: str) -> tuple[int, int]:
    parts = value.split(",")
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("range must be in MIN,MAX format")
    low = int(parts[0])
    high = int(parts[1])
    if low > high:
        raise argparse.ArgumentTypeError("range MIN must be <= MAX")
    return low, high


def _apply_overrides(config, params: GenerateParams):
    if params.table_count is not None:
        config = replace(config, table_count=params.table_count)
    if params.visit_range is not None:
        config = replace(config, visit_count_range=params.visit_range)
    if params.order_range is not None:
        config = replace(config, order_count_range=params.order_range)
    if params.item_range is not None:
        config = replace(config, item_count_range=params.item_range)
    if params.stay_range is not None:
        config = replace(config, stay_minutes_range=params.stay_range)
    if params.cook_range is not None:
        config = replace(config, cook_time_seconds_range=params.cook_range)
    return config


def _build_tax_history(
    seed: int, start_year: int, end_year: int, config
) -> list[TaxRateHistory]:
    rng = random.Random(seed)
    rate_candidates = config.tax_rate_candidates
    history: list[TaxRateHistory] = []
    current_year = start_year
    while current_year <= end_year:
        rate = rng.choice(rate_candidates)
        start = date(current_year, 1, 1)
        end = date(
            min(current_year + config.tax_change_frequency_years - 1, end_year),
            12,
            31,
        )
        history.append(
            TaxRateHistory(
                tax_rate_hist_id="",
                effective_from=start,
                effective_to=end,
                tax_rate=rate,
                tax_rule=config.tax_default.tax_rule,
            )
        )
        current_year += config.tax_change_frequency_years
    return history


def _ensure_master_data(
    out_dir: Path, ids: IdFactory, seed: int, config
) -> list[TaxRateHistory]:
    menu_item_path = out_dir / "menu_item.csv"
    menu_price_path = out_dir / "menu_price_history.csv"
    discount_path = out_dir / "set_discount.csv"
    tax_path = out_dir / "tax_rate_history.csv"
    change_log_path = out_dir / "change_log.csv"

    change_rows: list[list[str]] = []
    change_dt = datetime(2019, 12, 31, 23, 30, tzinfo=ZoneInfo("Asia/Tokyo"))
    effective_from = "2020-01-01T07:00:00+09:00"
    effective_to = ""

    if file_has_only_header(menu_item_path):
        menu_rows = [
            [
                item.menu_item_id,
                item.name,
                item.category,
                "1" if item.is_kids else "0",
                item.season or "",
                item.event or "",
            ]
            for item in MENU_ITEMS
        ]
        append_rows(menu_item_path, menu_rows)
        for item in MENU_ITEMS:
            change_rows.append(
                [
                    ids.next_change_log(),
                    "menu_item",
                    item.menu_item_id,
                    "create",
                    change_dt.isoformat(),
                    effective_from,
                    effective_to,
                    f"seeded menu item {item.name}",
                ]
            )

    if file_has_only_header(menu_price_path):
        price_rows = []
        for item in MENU_ITEMS:
            price_rows.append(
                [
                    ids.next_menu_price_hist(),
                    item.menu_item_id,
                    str(item.price),
                    "2020-01-01",
                    "2099-12-31",
                ]
            )
            change_rows.append(
                [
                    ids.next_change_log(),
                    "menu_price_history",
                    price_rows[-1][0],
                    "create",
                    change_dt.isoformat(),
                    effective_from,
                    effective_to,
                    f"seeded price {item.price} for {item.menu_item_id}",
                ]
            )
        append_rows(menu_price_path, price_rows)

    if file_has_only_header(discount_path):
        discount_rows = [
            [
                d.discount_id,
                d.name,
                d.discount_type,
                str(d.discount_value_yen),
                f"{d.discount_rate:.2f}",
                "2020-01-01",
                "2099-12-31",
            ]
            for d in DISCOUNTS
        ]
        append_rows(discount_path, discount_rows)
        for d in DISCOUNTS:
            change_rows.append(
                [
                    ids.next_change_log(),
                    "set_discount",
                    d.discount_id,
                    "create",
                    change_dt.isoformat(),
                    effective_from,
                    effective_to,
                    f"seeded discount {d.name}",
                ]
            )

    tax_history: list[TaxRateHistory]
    if file_has_only_header(tax_path):
        raw_history = _build_tax_history(seed, 2018, 2030, config)
        tax_rows = []
        tax_history = []
        for entry in raw_history:
            tax_id = ids.next_tax_rate_hist()
            tax_history.append(
                TaxRateHistory(
                    tax_rate_hist_id=tax_id,
                    effective_from=entry.effective_from,
                    effective_to=entry.effective_to,
                    tax_rate=entry.tax_rate,
                    tax_rule=entry.tax_rule,
                )
            )
            tax_rows.append(
                [
                    tax_id,
                    entry.effective_from.isoformat(),
                    entry.effective_to.isoformat(),
                    f"{entry.tax_rate:.2f}",
                    entry.tax_rule,
                ]
            )
            change_rows.append(
                [
                    ids.next_change_log(),
                    "tax_rate_history",
                    tax_id,
                    "create",
                    change_dt.isoformat(),
                    effective_from,
                    effective_to,
                    f"seeded tax rate {entry.tax_rate:.2f}",
                ]
            )
        append_rows(tax_path, tax_rows)
    else:
        tax_history = []
        with tax_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if not row:
                    continue
                tax_history.append(
                    TaxRateHistory(
                        tax_rate_hist_id=row["tax_rate_hist_id"],
                        effective_from=date.fromisoformat(row["effective_from"]),
                        effective_to=date.fromisoformat(row["effective_to"]),
                        tax_rate=float(row["tax_rate"]),
                        tax_rule=row["tax_rule"],
                    )
                )

    if change_rows:
        append_rows(change_log_path, change_rows)

    return tax_history


def generate(params: GenerateParams) -> None:
    config = _apply_overrides(default_config(), params)
    existing = read_existing_state(params.out_dir)
    ids = IdFactory.from_existing_max(existing.max_ids)

    for filename, header in HEADERS.items():
        ensure_header(params.out_dir / filename, header)

    tax_history = _ensure_master_data(params.out_dir, ids, params.seed, config)

    visits_rows: list[list[str]] = []
    orders_rows: list[list[str]] = []
    order_items_rows: list[list[str]] = []
    receipts_rows: list[list[str]] = []
    customers_rows: list[list[str]] = []

    days_to_generate = [
        day
        for day in _date_range(params.start, params.end)
        if params.force or (day not in existing.generated_dates)
    ]

    if not days_to_generate:
        return

    tz = ZoneInfo("Asia/Tokyo")
    generated_at = datetime.combine(params.start, datetime.min.time(), tz)
    run_row = [
        ids.next_run(),
        generated_at.isoformat(),
        params.start.isoformat(),
        params.end.isoformat(),
        str(params.seed),
        __version__,
    ]
    append_rows(params.out_dir / "generation_run.csv", [run_row])

    for day in days_to_generate:
        rng = random.Random(_seed_for_day(params.seed, day))
        day_rows = generate_day(day, config, rng, ids, tax_history)
        visits_rows.extend(day_rows.visits)
        orders_rows.extend(day_rows.orders)
        order_items_rows.extend(day_rows.order_items)
        receipts_rows.extend(day_rows.receipts)
        customers_rows.extend(day_rows.customers)

    append_rows(params.out_dir / "visit.csv", visits_rows)
    append_rows(params.out_dir / "order.csv", orders_rows)
    append_rows(params.out_dir / "order_item.csv", order_items_rows)
    append_rows(params.out_dir / "receipt.csv", receipts_rows)
    append_rows(params.out_dir / "customer.csv", customers_rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fami-synth")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="Generate daily CSV data")
    gen.add_argument("--start", required=True, type=date.fromisoformat)
    gen.add_argument("--end", required=True, type=date.fromisoformat)
    gen.add_argument("--seed", required=True, type=int)
    gen.add_argument("--out-dir", required=True, type=Path)
    gen.add_argument("--force", action="store_true")
    gen.add_argument("--table-count", type=int)
    gen.add_argument("--visit-range", type=_parse_range, metavar="MIN,MAX")
    gen.add_argument("--order-range", type=_parse_range, metavar="MIN,MAX")
    gen.add_argument("--item-range", type=_parse_range, metavar="MIN,MAX")
    gen.add_argument("--stay-range", type=_parse_range, metavar="MIN,MAX")
    gen.add_argument("--cook-range", type=_parse_range, metavar="MIN,MAX")

    dash = sub.add_parser("dashboard", help="Run dashboard web app")
    dash.add_argument("--data-dir", required=True, type=Path)
    dash.add_argument("--host", default="127.0.0.1")
    dash.add_argument("--port", default=8000, type=int)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "generate":
        params = GenerateParams(
            start=args.start,
            end=args.end,
            seed=args.seed,
            out_dir=args.out_dir,
            force=args.force,
            table_count=args.table_count,
            visit_range=args.visit_range,
            order_range=args.order_range,
            item_range=args.item_range,
            stay_range=args.stay_range,
            cook_range=args.cook_range,
        )
        generate(params)
    elif args.command == "dashboard":
        import uvicorn
        from dashboard.app import create_app

        app = create_app(args.data_dir)
        uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
