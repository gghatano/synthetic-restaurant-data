from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path


HEADERS: dict[str, list[str]] = {
    "generation_run.csv": [
        "run_id",
        "generated_at",
        "start_date",
        "end_date",
        "seed",
        "generator_version",
    ],
    "visit.csv": [
        "visit_id",
        "store_id",
        "table_id",
        "seated_at",
        "left_at",
        "adult_cnt",
        "child_cnt",
        "visit_date",
        "day_of_week",
        "time_slot",
    ],
    "order.csv": [
        "order_id",
        "visit_id",
        "ordered_at",
        "channel",
        "order_seq_in_visit",
    ],
    "order_item.csv": [
        "order_item_id",
        "order_id",
        "menu_item_id",
        "qty",
        "unit_price_yen_at_order",
        "line_subtotal_yen",
        "status",
        "served_at",
        "cook_time_sec",
        "is_kids_item",
    ],
    "receipt.csv": [
        "receipt_id",
        "visit_id",
        "paid_at",
        "payment_method",
        "customer_id",
        "subtotal_yen",
        "discount_total_yen",
        "tax_rate_applied",
        "tax_rate_hist_id",
        "tax_yen",
        "total_yen",
        "applied_discount_ids",
        "points_earned",
        "points_used",
    ],
    "menu_item.csv": [
        "menu_item_id",
        "name",
        "category",
        "is_kids_item",
        "season",
        "event",
    ],
    "menu_price_history.csv": [
        "menu_price_hist_id",
        "menu_item_id",
        "price_yen",
        "effective_from",
        "effective_to",
    ],
    "set_discount.csv": [
        "discount_id",
        "name",
        "discount_type",
        "discount_value_yen",
        "discount_rate",
        "effective_from",
        "effective_to",
    ],
    "tax_rate_history.csv": [
        "tax_rate_hist_id",
        "effective_from",
        "effective_to",
        "tax_rate",
        "tax_rule",
    ],
    "customer.csv": [
        "customer_id",
        "created_at",
    ],
    "change_log.csv": [
        "change_id",
        "entity_type",
        "entity_id",
        "change_type",
        "changed_at",
        "effective_from",
        "effective_to",
        "summary",
    ],
}

ID_PATTERNS = {
    "visit.csv": ("V", "visit_id"),
    "order.csv": ("O", "order_id"),
    "order_item.csv": ("OI", "order_item_id"),
    "receipt.csv": ("R", "receipt_id"),
    "generation_run.csv": ("RUN", "run_id"),
    "menu_price_history.csv": ("MPH", "menu_price_hist_id"),
    "tax_rate_history.csv": ("TH", "tax_rate_hist_id"),
    "customer.csv": ("C", "customer_id"),
    "change_log.csv": ("CH", "change_id"),
}


@dataclass
class ExistingState:
    generated_dates: set[date]
    max_ids: dict[str, int]


def ensure_header(path: Path, header: list[str]) -> None:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(header)
        return

    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        existing = next(reader, [])
    if existing != header:
        raise ValueError(f"CSV header mismatch: {path}")


def append_rows(path: Path, rows: list[list[str]]) -> None:
    if not rows:
        return
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(rows)


def file_has_only_header(path: Path) -> bool:
    if not path.exists():
        return True
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)
    return len(rows) <= 1


def read_existing_state(out_dir: Path) -> ExistingState:
    generated_dates: set[date] = set()
    max_ids: dict[str, int] = {}

    visit_path = out_dir / "visit.csv"
    if visit_path.exists():
        with visit_path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if not row:
                    continue
                visit_date = row.get("visit_date")
                if visit_date:
                    generated_dates.add(date.fromisoformat(visit_date))

    for filename, (prefix, id_col) in ID_PATTERNS.items():
        path = out_dir / filename
        if not path.exists():
            continue
        with path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                value = row.get(id_col, "")
                if not value.startswith(prefix):
                    continue
                m = re.search(r"(\d+)$", value)
                if not m:
                    continue
                num = int(m.group(1))
                max_ids[prefix] = max(max_ids.get(prefix, 0), num)

    return ExistingState(generated_dates=generated_dates, max_ids=max_ids)
