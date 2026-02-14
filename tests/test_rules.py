from datetime import date

from fami_synth.cli import GenerateParams, _seed_for_day, generate
from fami_synth.generator_day import available_menu_items


def test_seed_for_day_is_stable():
    day = date(2026, 2, 10)
    assert _seed_for_day(123, day) == (123 * 1_000_003 + day.toordinal()) & 0xFFFFFFFF


def test_season_and_event_menu_filters():
    spring_day = date(2026, 4, 10)
    items = available_menu_items(spring_day)
    assert any(i.menu_item_id == "M101" for i in items)
    assert all(i.season in (None, "spring") for i in items)

    halloween_day = date(2026, 10, 31)
    items = available_menu_items(halloween_day)
    assert any(i.menu_item_id == "M201" for i in items)


def test_receipt_totals_and_tax_history(tmp_path):
    params = GenerateParams(
        start=date(2026, 2, 10),
        end=date(2026, 2, 11),
        seed=7,
        out_dir=tmp_path,
        force=False,
    )
    generate(params)

    receipt_lines = (tmp_path / "receipt.csv").read_text(encoding="utf-8").splitlines()
    assert len(receipt_lines) > 1
    headers = receipt_lines[0].split(",")
    row = dict(zip(headers, receipt_lines[1].split(",")))

    subtotal = int(row["subtotal_yen"])
    discount = int(row["discount_total_yen"])
    tax = int(row["tax_yen"])
    total = int(row["total_yen"])

    assert 0 <= discount <= subtotal
    assert total == subtotal - discount + tax
    assert row["tax_rate_hist_id"]


def test_change_log_is_off_hours(tmp_path):
    params = GenerateParams(
        start=date(2026, 2, 10),
        end=date(2026, 2, 11),
        seed=9,
        out_dir=tmp_path,
        force=False,
    )
    generate(params)

    lines = (tmp_path / "change_log.csv").read_text(encoding="utf-8").splitlines()
    assert len(lines) > 1
    headers = lines[0].split(",")
    row = dict(zip(headers, lines[1].split(",")))

    changed_at = row["changed_at"]
    effective_from = row["effective_from"]

    assert "T23:" in changed_at or "T00:" in changed_at or "T01:" in changed_at
    assert "T07:00:00+09:00" in effective_from


def test_cli_overrides_affect_counts(tmp_path):
    params = GenerateParams(
        start=date(2026, 2, 10),
        end=date(2026, 2, 11),
        seed=11,
        out_dir=tmp_path,
        force=False,
        visit_range=(1, 1),
        order_range=(1, 1),
        item_range=(1, 1),
    )
    generate(params)

    visit_lines = (tmp_path / "visit.csv").read_text(encoding="utf-8").splitlines()
    order_lines = (tmp_path / "order.csv").read_text(encoding="utf-8").splitlines()
    item_lines = (tmp_path / "order_item.csv").read_text(encoding="utf-8").splitlines()

    visit_count = len(visit_lines) - 1
    order_count = len(order_lines) - 1
    item_count = len(item_lines) - 1

    assert visit_count == 3
    assert order_count == visit_count
    assert item_count == order_count
