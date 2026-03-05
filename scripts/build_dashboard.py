"""Build a static GitHub Pages dashboard from CSV data files.

Usage:
    python scripts/build_dashboard.py [--data-dir data/output] [--out docs/index.html]
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path


JST = timezone(timedelta(hours=9))


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _int(val: str, default: int = 0) -> int:
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _float(val: str, default: float = 0.0) -> float:
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _date(iso: str) -> str:
    """Extract YYYY-MM-DD from an ISO datetime string."""
    return (iso or "")[:10]


def _minutes_between(iso_start: str, iso_end: str) -> float | None:
    try:
        start = datetime.fromisoformat(iso_start)
        end = datetime.fromisoformat(iso_end)
        diff = (end - start).total_seconds() / 60
        return round(diff, 1) if diff >= 0 else None
    except (ValueError, TypeError):
        return None


def aggregate(data_dir: Path) -> dict:
    visits = read_csv(data_dir / "visit.csv")
    orders = read_csv(data_dir / "order.csv")
    order_items = read_csv(data_dir / "order_item.csv")
    receipts = read_csv(data_dir / "receipt.csv")
    menu_items = read_csv(data_dir / "menu_item.csv")

    # Index helpers
    visit_by_id: dict[str, dict] = {v["visit_id"]: v for v in visits}
    menu_by_id: dict[str, dict] = {m["menu_item_id"]: m for m in menu_items}
    order_to_visit: dict[str, str] = {o["order_id"]: o["visit_id"] for o in orders}

    # Customer first visit date (for new/returning classification)
    customer_first_date: dict[str, str] = {}
    for r in receipts:
        cid = r["customer_id"]
        if not cid:
            continue
        v = visit_by_id.get(r["visit_id"])
        if not v:
            continue
        d = v["visit_date"]
        if not d:
            continue
        if cid not in customer_first_date or d < customer_first_date[cid]:
            customer_first_date[cid] = d

    # All store IDs (sorted)
    store_ids = sorted({v["store_id"] for v in visits})

    # -------------------------------------------------------------------------
    # 1. Daily time series: visits and revenue by date
    # -------------------------------------------------------------------------
    daily_visits: dict[str, int] = defaultdict(int)
    daily_visits_by_store: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for v in visits:
        d = v["visit_date"]
        sid = v["store_id"]
        daily_visits[d] += 1
        daily_visits_by_store[d][sid] += 1

    daily_revenue: dict[str, int] = defaultdict(int)
    for r in receipts:
        d = _date(r["paid_at"])
        daily_revenue[d] += _int(r["total_yen"])

    all_dates = sorted(set(list(daily_visits.keys()) + list(daily_revenue.keys())))

    # -------------------------------------------------------------------------
    # 2. KPI – latest day vs previous day
    # -------------------------------------------------------------------------
    latest_date = all_dates[-1] if all_dates else ""
    prev_date = all_dates[-2] if len(all_dates) >= 2 else ""

    def day_kpi(d: str) -> dict:
        v_cnt = daily_visits.get(d, 0)
        rev = daily_revenue.get(d, 0)
        loyalty_visits = sum(
            1 for r in receipts
            if _date(r["paid_at"]) == d and r["customer_id"]
        )
        total_receipts_day = sum(
            1 for r in receipts
            if _date(r["paid_at"]) == d
        )
        return {
            "visits": v_cnt,
            "revenue": rev,
            "avg_ticket": round(rev / v_cnt) if v_cnt else 0,
            "loyalty_rate": round(loyalty_visits / total_receipts_day * 100) if total_receipts_day else 0,
        }

    latest_kpi = day_kpi(latest_date)
    prev_kpi = day_kpi(prev_date)

    # -------------------------------------------------------------------------
    # 3. Weekday aggregates
    # -------------------------------------------------------------------------
    weekday_order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    weekday_label = {"Mon": "月", "Tue": "火", "Wed": "水", "Thu": "木",
                     "Fri": "金", "Sat": "土", "Sun": "日"}
    weekday_agg: dict[str, dict] = {
        w: {"visits": 0, "revenue": 0} for w in weekday_order
    }
    visit_weekday: dict[str, str] = {}
    for v in visits:
        w = v["day_of_week"]
        # day_of_week column is integer (1=Mon...7=Sun) or string name
        # Let's handle both: if numeric, map; if string, use directly
        if w.isdigit():
            idx = int(w) - 1
            w = weekday_order[idx] if 0 <= idx < 7 else w
        if w not in weekday_agg:
            weekday_agg[w] = {"visits": 0, "revenue": 0}
        weekday_agg[w]["visits"] += 1
        visit_weekday[v["visit_id"]] = w

    for r in receipts:
        w = visit_weekday.get(r["visit_id"], "")
        if w in weekday_agg:
            weekday_agg[w]["revenue"] += _int(r["total_yen"])

    weekday_data = []
    for w in weekday_order:
        agg = weekday_agg[w]
        visits_cnt = agg["visits"]
        rev = agg["revenue"]
        weekday_data.append({
            "label": weekday_label.get(w, w),
            "visits": visits_cnt,
            "revenue": rev,
            "avg_ticket": round(rev / visits_cnt) if visits_cnt else 0,
        })

    # -------------------------------------------------------------------------
    # 4. Time slot aggregates
    # -------------------------------------------------------------------------
    slot_agg: dict[str, dict] = defaultdict(lambda: {"visits": 0, "revenue": 0, "party": 0})
    visit_slot: dict[str, str] = {}
    for v in visits:
        slot = v["time_slot"] or "unknown"
        visit_slot[v["visit_id"]] = slot
        party = _int(v["adult_cnt"]) + _int(v["child_cnt"])
        slot_agg[slot]["visits"] += 1
        slot_agg[slot]["party"] += party

    for r in receipts:
        slot = visit_slot.get(r["visit_id"], "unknown")
        slot_agg[slot]["revenue"] += _int(r["total_yen"])

    slot_order = ["morning", "lunch", "afternoon", "evening", "night"]
    time_slot_data = []
    for slot in slot_order:
        if slot not in slot_agg:
            continue
        agg = slot_agg[slot]
        v_cnt = agg["visits"]
        rev = agg["revenue"]
        party = agg["party"]
        time_slot_data.append({
            "slot": slot,
            "visits": v_cnt,
            "revenue": rev,
            "avg_ticket": round(rev / v_cnt) if v_cnt else 0,
            "avg_party": round(party / v_cnt, 2) if v_cnt else 0,
        })

    # -------------------------------------------------------------------------
    # 5. Store benchmark
    # -------------------------------------------------------------------------
    store_agg: dict[str, dict] = {
        s: {"visits": 0, "revenue": 0, "duration_sum": 0.0, "duration_cnt": 0, "extra_visits": 0}
        for s in store_ids
    }

    # Which visits have extra orders (order_seq >= 2)
    visit_has_extra: dict[str, bool] = {}
    for o in orders:
        vid = o["visit_id"]
        if _int(o["order_seq_in_visit"]) >= 2:
            visit_has_extra[vid] = True

    for v in visits:
        s = v["store_id"]
        if s not in store_agg:
            store_agg[s] = {"visits": 0, "revenue": 0, "duration_sum": 0.0, "duration_cnt": 0, "extra_visits": 0}
        store_agg[s]["visits"] += 1
        dur = _minutes_between(v["seated_at"], v["left_at"])
        if dur is not None:
            store_agg[s]["duration_sum"] += dur
            store_agg[s]["duration_cnt"] += 1
        if visit_has_extra.get(v["visit_id"]):
            store_agg[s]["extra_visits"] += 1

    for r in receipts:
        v = visit_by_id.get(r["visit_id"])
        if not v:
            continue
        s = v["store_id"]
        if s in store_agg:
            store_agg[s]["revenue"] += _int(r["total_yen"])

    store_benchmark = []
    for s in store_ids:
        agg = store_agg[s]
        v_cnt = agg["visits"]
        rev = agg["revenue"]
        dur_cnt = agg["duration_cnt"]
        store_benchmark.append({
            "store_id": s,
            "visits": v_cnt,
            "revenue": rev,
            "avg_ticket": round(rev / v_cnt) if v_cnt else 0,
            "avg_stay": round(agg["duration_sum"] / dur_cnt, 1) if dur_cnt else 0,
            "extra_order_rate": round(agg["extra_visits"] / v_cnt * 100, 1) if v_cnt else 0,
        })

    # -------------------------------------------------------------------------
    # 6. Discount stats
    # -------------------------------------------------------------------------
    discount_usage: dict[str, int] = defaultdict(int)
    discount_stats: dict[str, dict] = defaultdict(lambda: {"cnt": 0, "total_yen": 0, "discount_yen": 0})

    for r in receipts:
        total = _int(r["total_yen"])
        discount_yen = _int(r["discount_total_yen"])
        applied = [d for d in (r.get("applied_discount_ids") or "").split("|") if d]
        labels = applied if applied else ["NONE"]
        for d in labels:
            discount_usage[d] += 1
            discount_stats[d]["cnt"] += 1
            discount_stats[d]["total_yen"] += total
            discount_stats[d]["discount_yen"] += discount_yen

    discount_data = []
    for d_key in sorted(discount_stats.keys(), key=lambda k: -discount_stats[k]["cnt"]):
        stats = discount_stats[d_key]
        cnt = stats["cnt"]
        discount_data.append({
            "discount_id": d_key,
            "count": cnt,
            "avg_total": round(stats["total_yen"] / cnt) if cnt else 0,
            "avg_discount": round(stats["discount_yen"] / cnt) if cnt else 0,
        })

    # -------------------------------------------------------------------------
    # 7. Tax rate distribution
    # -------------------------------------------------------------------------
    tax_rate_dist: dict[str, int] = defaultdict(int)
    for r in receipts:
        tax_rate_dist[r["tax_rate_applied"]] += 1

    # -------------------------------------------------------------------------
    # 8. Loyalty / customer segmentation
    # -------------------------------------------------------------------------
    loyalty_yes = sum(1 for r in receipts if r["customer_id"])
    loyalty_no = len(receipts) - loyalty_yes

    seg: dict[str, dict] = {
        "new_member": {"cnt": 0, "total": 0},
        "returning_member": {"cnt": 0, "total": 0},
        "guest": {"cnt": 0, "total": 0},
    }
    for r in receipts:
        cid = r["customer_id"]
        total = _int(r["total_yen"])
        v = visit_by_id.get(r["visit_id"])
        visit_date = v["visit_date"] if v else ""
        if not cid:
            seg["guest"]["cnt"] += 1
            seg["guest"]["total"] += total
        elif visit_date and customer_first_date.get(cid) == visit_date:
            seg["new_member"]["cnt"] += 1
            seg["new_member"]["total"] += total
        else:
            seg["returning_member"]["cnt"] += 1
            seg["returning_member"]["total"] += total

    customer_seg = [
        {
            "label": "新規会員(初回来店)",
            "cnt": seg["new_member"]["cnt"],
            "avg_ticket": round(seg["new_member"]["total"] / seg["new_member"]["cnt"])
                          if seg["new_member"]["cnt"] else 0,
        },
        {
            "label": "既存会員",
            "cnt": seg["returning_member"]["cnt"],
            "avg_ticket": round(seg["returning_member"]["total"] / seg["returning_member"]["cnt"])
                          if seg["returning_member"]["cnt"] else 0,
        },
        {
            "label": "非会員",
            "cnt": seg["guest"]["cnt"],
            "avg_ticket": round(seg["guest"]["total"] / seg["guest"]["cnt"])
                          if seg["guest"]["cnt"] else 0,
        },
    ]

    # -------------------------------------------------------------------------
    # 9. Season / event sales
    # -------------------------------------------------------------------------
    season_event: dict[str, int] = defaultdict(int)
    sorted_dates = sorted(d for d in daily_visits if d)
    pivot_date = sorted_dates[len(sorted_dates) // 2] if sorted_dates else ""
    season_period = {
        "early": {"seasonal": 0, "total": 0},
        "late": {"seasonal": 0, "total": 0},
    }

    for item in order_items:
        m = menu_by_id.get(item["menu_item_id"])
        if not m:
            continue
        sales = _int(item["line_subtotal_yen"])
        tags = []
        if m["season"]:
            tags.append("季節:" + m["season"])
        if m["event"]:
            tags.append("イベント:" + m["event"])
        if not tags:
            tags.append("通常")
        for tag in tags:
            season_event[tag] += sales

        vid = order_to_visit.get(item["order_id"])
        v = visit_by_id.get(vid or "") if vid else None
        visit_date = v["visit_date"] if v else ""
        period = "early" if (pivot_date and visit_date and visit_date < pivot_date) else "late"
        season_period[period]["total"] += sales
        if m["season"] or m["event"]:
            season_period[period]["seasonal"] += sales

    season_event_ranked = sorted(season_event.items(), key=lambda x: -x[1])[:12]
    season_event_data = [{"tag": k, "revenue": v} for k, v in season_event_ranked]

    season_period_data = [
        {
            "label": "前半",
            "seasonal_revenue": season_period["early"]["seasonal"],
            "ratio": round(
                season_period["early"]["seasonal"] / season_period["early"]["total"] * 100, 1
            ) if season_period["early"]["total"] else 0,
        },
        {
            "label": "後半",
            "seasonal_revenue": season_period["late"]["seasonal"],
            "ratio": round(
                season_period["late"]["seasonal"] / season_period["late"]["total"] * 100, 1
            ) if season_period["late"]["total"] else 0,
        },
    ]

    # -------------------------------------------------------------------------
    # 10. Menu ABC analysis
    # -------------------------------------------------------------------------
    menu_sales: dict[str, int] = defaultdict(int)
    for item in order_items:
        m = menu_by_id.get(item["menu_item_id"])
        name = m["name"] if m else item["menu_item_id"]
        menu_sales[name] += _int(item["line_subtotal_yen"])

    menu_ranked = sorted(menu_sales.items(), key=lambda x: -x[1])
    total_menu_sales = sum(v for _, v in menu_ranked)
    cumulative = 0
    menu_abc_data = []
    for name, sales in menu_ranked:
        cumulative += sales
        menu_abc_data.append({
            "name": name,
            "revenue": sales,
            "cumulative_ratio": round(cumulative / total_menu_sales * 100, 1) if total_menu_sales else 0,
        })

    # -------------------------------------------------------------------------
    # 11. Stay duration × extra order analysis
    # -------------------------------------------------------------------------
    stay_bins = [
        {"label": "<45分", "min": 0, "max": 44},
        {"label": "45-59分", "min": 45, "max": 59},
        {"label": "60-89分", "min": 60, "max": 89},
        {"label": "90分以上", "min": 90, "max": math.inf},
    ]
    stay_agg: dict[str, dict] = {b["label"]: {"cnt": 0, "extra": 0, "total": 0} for b in stay_bins}

    visit_total: dict[str, int] = defaultdict(int)
    for r in receipts:
        visit_total[r["visit_id"]] += _int(r["total_yen"])

    for v in visits:
        dur = _minutes_between(v["seated_at"], v["left_at"])
        if dur is None:
            continue
        for b in stay_bins:
            if b["min"] <= dur <= b["max"]:
                row = stay_agg[b["label"]]
                row["cnt"] += 1
                row["total"] += visit_total.get(v["visit_id"], 0)
                if visit_has_extra.get(v["visit_id"]):
                    row["extra"] += 1
                break

    stay_data = []
    for b in stay_bins:
        row = stay_agg[b["label"]]
        cnt = row["cnt"]
        stay_data.append({
            "label": b["label"],
            "avg_ticket": round(row["total"] / cnt) if cnt else 0,
            "extra_order_rate": round(row["extra"] / cnt * 100, 1) if cnt else 0,
        })

    # -------------------------------------------------------------------------
    # 12. Revenue histogram (bins)
    # -------------------------------------------------------------------------
    receipt_totals = [_int(r["total_yen"]) for r in receipts]
    if receipt_totals:
        bin_count = 20
        min_val = min(receipt_totals)
        max_val = max(receipt_totals)
        bin_size = max(1, (max_val - min_val) // bin_count)
        rev_hist: dict[str, int] = defaultdict(int)
        for val in receipt_totals:
            bucket = (val - min_val) // bin_size
            label = str(min_val + bucket * bin_size)
            rev_hist[label] += 1
        rev_hist_data = [{"range_start": int(k), "count": v}
                         for k, v in sorted(rev_hist.items(), key=lambda x: int(x[0]))]
    else:
        rev_hist_data = []

    # -------------------------------------------------------------------------
    # 13. Orders-per-visit distribution
    # -------------------------------------------------------------------------
    orders_per_visit: dict[str, int] = defaultdict(int)
    for o in orders:
        orders_per_visit[o["visit_id"]] += 1
    opv_counts: dict[int, int] = defaultdict(int)
    for cnt in orders_per_visit.values():
        opv_counts[cnt] += 1
    orders_per_visit_data = [{"orders": k, "visits": v}
                              for k, v in sorted(opv_counts.items())]

    # -------------------------------------------------------------------------
    # 14. Items-per-order distribution
    # -------------------------------------------------------------------------
    items_per_order: dict[str, int] = defaultdict(int)
    for item in order_items:
        items_per_order[item["order_id"]] += 1
    ipo_counts: dict[int, int] = defaultdict(int)
    for cnt in items_per_order.values():
        ipo_counts[cnt] += 1
    items_per_order_data = [{"items": k, "orders": v}
                             for k, v in sorted(ipo_counts.items())]

    # -------------------------------------------------------------------------
    # 15. Store visits by date (for multi-line chart)
    # -------------------------------------------------------------------------
    store_daily_visits = []
    for d in all_dates:
        row: dict = {"date": d}
        for s in store_ids:
            row[s] = daily_visits_by_store[d].get(s, 0)
        store_daily_visits.append(row)

    # -------------------------------------------------------------------------
    # 16. Latest receipts sample
    # -------------------------------------------------------------------------
    receipts_sorted = sorted(
        receipts, key=lambda r: r["paid_at"] or "", reverse=True
    )[:10]
    receipt_sample = [
        {
            "receipt_id": r["receipt_id"],
            "visit_id": r["visit_id"],
            "paid_at": r["paid_at"],
            "subtotal_yen": _int(r["subtotal_yen"]),
            "discount_total_yen": _int(r["discount_total_yen"]),
            "tax_yen": _int(r["tax_yen"]),
            "total_yen": _int(r["total_yen"]),
        }
        for r in receipts_sorted
    ]

    # -------------------------------------------------------------------------
    # 17. Daily time series (combined for decomposition chart)
    # -------------------------------------------------------------------------
    daily_series = []
    for d in all_dates:
        v_cnt = daily_visits.get(d, 0)
        rev = daily_revenue.get(d, 0)
        daily_series.append({
            "date": d,
            "visits": v_cnt,
            "revenue": rev,
            "avg_ticket": round(rev / v_cnt) if v_cnt else 0,
        })

    return {
        "generated_at": datetime.now(JST).strftime("%Y-%m-%d %H:%M JST"),
        "latest_date": latest_date,
        "prev_date": prev_date,
        "latest_kpi": latest_kpi,
        "prev_kpi": prev_kpi,
        "store_ids": store_ids,
        "daily_series": daily_series,
        "store_daily_visits": store_daily_visits,
        "weekday_data": weekday_data,
        "time_slot_data": time_slot_data,
        "store_benchmark": store_benchmark,
        "discount_data": discount_data,
        "tax_rate_dist": dict(tax_rate_dist),
        "loyalty_yes": loyalty_yes,
        "loyalty_no": loyalty_no,
        "customer_seg": customer_seg,
        "season_event_data": season_event_data,
        "season_period_data": season_period_data,
        "menu_abc_data": menu_abc_data,
        "stay_data": stay_data,
        "rev_hist_data": rev_hist_data,
        "orders_per_visit_data": orders_per_visit_data,
        "items_per_order_data": items_per_order_data,
        "receipt_sample": receipt_sample,
    }


def build_html(agg: dict) -> str:
    data_json = json.dumps(agg, ensure_ascii=False, separators=(",", ":"))

    return f"""<!doctype html>
<html lang="ja">
  <head>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1"/>
    <title>ファミシン セールスダッシュボード</title>
    <script src="https://cdn.plot.ly/plotly-2.30.0.min.js"></script>
    <style>
      body {{ font-family: "BIZ UDPGothic", "Noto Sans JP", system-ui, sans-serif; margin: 0; background: #f3f5f6; color: #1c2421; }}
      header {{ padding: 16px 24px; background: #0f1f2e; color: #f4f7f8; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; }}
      header h2 {{ margin: 0 0 4px; font-size: 20px; }}
      .sub {{ opacity: 0.8; font-size: 13px; }}
      .generated {{ font-size: 11px; opacity: 0.6; }}
      .toolbar {{ display: flex; gap: 12px; padding: 12px 24px; background: #e9eef1; align-items: center; }}
      .toolbar label {{ font-size: 13px; }}
      select {{ padding: 6px 10px; border-radius: 8px; border: 1px solid #c7d1d7; }}
      .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; padding: 16px; }}
      .card {{ background: #ffffff; border-radius: 12px; padding: 10px 12px; box-shadow: 0 6px 16px rgba(0,0,0,0.06); }}
      .wide {{ grid-column: span 4; }}
      .half {{ grid-column: span 2; }}
      .kpi {{ display: flex; flex-direction: column; gap: 4px; }}
      .kpi .label {{ font-size: 12px; color: #5b6b74; }}
      .kpi .value {{ font-size: 22px; font-weight: 700; }}
      .kpi .delta {{ font-size: 12px; margin-top: 2px; }}
      .delta-up {{ color: #1a8f5e; }}
      .delta-down {{ color: #c0392b; }}
      .delta-flat {{ color: #5b6b74; }}
      @media (max-width: 1200px) {{ .grid {{ grid-template-columns: 1fr; }} .wide, .half {{ grid-column: span 1; }} }}
    </style>
  </head>
  <body>
    <header>
      <div>
        <h2>ファミシン セールスダッシュボード</h2>
        <div class="sub">店舗責任者 / 全体統括向けの購買・来店ダッシュボード</div>
      </div>
      <div class="generated" id="generated_at"></div>
    </header>
    <div class="toolbar">
      <label>表示対象</label>
      <select id="storeSelect"></select>
      <span class="sub">対象: 全店 / 店舗別の切替</span>
    </div>
    <div class="grid">
      <!-- KPI row -->
      <div class="card kpi" id="kpi_visits"></div>
      <div class="card kpi" id="kpi_revenue"></div>
      <div class="card kpi" id="kpi_avg"></div>
      <div class="card kpi" id="kpi_loyalty"></div>

      <!-- Daily time series -->
      <div class="card half" id="daily_visits"></div>
      <div class="card half" id="daily_revenue"></div>
      <div class="card wide" id="sales_decomposition"></div>
      <div class="card wide" id="weekday_trend"></div>

      <!-- Store comparison -->
      <div class="card half" id="store_benchmark"></div>
      <div class="card half" id="store_efficiency"></div>

      <!-- Time slot -->
      <div class="card half" id="time_slot_kpi"></div>
      <div class="card" id="time_slot"></div>
      <div class="card" id="orders_per_visit"></div>

      <!-- Customer analysis -->
      <div class="card" id="loyalty_pie"></div>
      <div class="card half" id="new_existing"></div>
      <div class="card" id="revenue_hist"></div>
      <div class="card" id="items_per_order"></div>

      <!-- Discount -->
      <div class="card half" id="discount_effect"></div>
      <div class="card half" id="discount_usage"></div>

      <!-- Season / event -->
      <div class="card half" id="season_event"></div>
      <div class="card half" id="season_event_period"></div>

      <!-- Menu ABC -->
      <div class="card half" id="menu_sales_top"></div>
      <div class="card half" id="menu_abc"></div>

      <!-- Stay analysis -->
      <div class="card wide" id="stay_extra_order"></div>

      <!-- Tax rate -->
      <div class="card" id="tax_rate"></div>
      <div class="card" id="visits_store"></div>

      <!-- Sample table -->
      <div class="card wide" id="table"></div>
    </div>

    <script>
    (function() {{
      const DATA = {data_json};

      // -----------------------------------------------------------------------
      // Helpers
      // -----------------------------------------------------------------------
      function fmtYen(n) {{ return "¥" + Number(n).toLocaleString(); }}
      function fmtNum(n) {{ return Number(n).toLocaleString(); }}

      function deltaHtml(current, prev, unit, higherIsBetter) {{
        if (!prev) return "";
        const diff = current - prev;
        const pct = prev !== 0 ? Math.round(diff / prev * 100) : 0;
        const sign = diff >= 0 ? "+" : "";
        const cls = diff === 0 ? "delta-flat" : (diff > 0 === higherIsBetter) ? "delta-up" : "delta-down";
        return `<span class="delta ${{cls}}">${{sign}}${{pct}}% 前日比 (${{sign}}${{unit === "¥" ? fmtYen(diff) : fmtNum(diff)}}${{unit !== "¥" ? unit : ""}})</span>`;
      }}

      function renderKpi(id, label, value, delta) {{
        const el = document.getElementById(id);
        if (!el) return;
        el.innerHTML = `<div class="label">${{label}}</div><div class="value">${{value}}</div>${{delta || ""}}`;
      }}

      // -----------------------------------------------------------------------
      // Populate store selector
      // -----------------------------------------------------------------------
      const storeSelect = document.getElementById("storeSelect");
      const allOpt = document.createElement("option");
      allOpt.value = "ALL"; allOpt.textContent = "全店";
      storeSelect.appendChild(allOpt);
      DATA.store_ids.forEach(s => {{
        const opt = document.createElement("option");
        opt.value = s; opt.textContent = "店舗 " + s;
        storeSelect.appendChild(opt);
      }});

      document.getElementById("generated_at").textContent = "データ更新: " + DATA.generated_at;

      // -----------------------------------------------------------------------
      // Filter helpers (store-aware)
      // -----------------------------------------------------------------------
      function filterDailySeries(store) {{
        if (store === "ALL") return DATA.daily_series;
        // Re-compute from store_daily_visits
        return DATA.store_daily_visits.map(row => {{
          const v = row[store] || 0;
          // Revenue by store is not pre-aggregated separately; show visits only
          return {{ date: row.date, visits: v, revenue: null, avg_ticket: null }};
        }}).filter(r => r.visits > 0 || DATA.daily_series.find(d => d.date === r.date));
      }}

      function filterStoreVisits(store) {{
        if (store === "ALL") {{
          return DATA.store_ids.map(s => ({{
            store: s,
            visits: DATA.store_daily_visits.reduce((acc, r) => acc + (r[s] || 0), 0)
          }}));
        }}
        return [{{
          store,
          visits: DATA.store_daily_visits.reduce((acc, r) => acc + (r[store] || 0), 0)
        }}];
      }}

      function filterBenchmark(store) {{
        if (store === "ALL") return DATA.store_benchmark;
        return DATA.store_benchmark.filter(r => r.store_id === store);
      }}

      // -----------------------------------------------------------------------
      // Render all charts
      // -----------------------------------------------------------------------
      function renderAll(store) {{
        const kpi = DATA.latest_kpi;
        const prev = DATA.prev_kpi;

        renderKpi("kpi_visits", `来店数 (最新日: ${{DATA.latest_date}})`, fmtNum(kpi.visits),
          deltaHtml(kpi.visits, prev.visits, "組", true));
        renderKpi("kpi_revenue", "売上合計 (最新日)", fmtYen(kpi.revenue),
          deltaHtml(kpi.revenue, prev.revenue, "¥", true));
        renderKpi("kpi_avg", "客単価 (最新日)", fmtYen(kpi.avg_ticket),
          deltaHtml(kpi.avg_ticket, prev.avg_ticket, "¥", true));
        renderKpi("kpi_loyalty", "ロイヤルティ提示率 (最新日)", kpi.loyalty_rate + "%",
          deltaHtml(kpi.loyalty_rate, prev.loyalty_rate, "%", true));

        // --- Daily visits (multi-line by store) ---
        const storeTraces = DATA.store_ids.map(s => {{
          if (store !== "ALL" && s !== store) return null;
          return {{
            type: "scatter", mode: "lines", name: "店舗 " + s,
            x: DATA.store_daily_visits.map(r => r.date),
            y: DATA.store_daily_visits.map(r => r[s] || 0),
          }};
        }}).filter(Boolean);
        Plotly.newPlot("daily_visits", storeTraces, {{ title: "日別来店数（店舗別）", legend: {{ orientation: "h" }} }});

        // --- Daily revenue ---
        const revSeries = DATA.daily_series;
        Plotly.newPlot("daily_revenue", [{{
          type: "bar", name: "売上",
          x: revSeries.map(r => r.date),
          y: revSeries.map(r => r.revenue),
        }}], {{ title: "日別売上", yaxis: {{ title: "売上(円)" }} }});

        // --- Sales decomposition ---
        Plotly.newPlot("sales_decomposition", [
          {{ type: "bar", name: "売上", x: revSeries.map(r => r.date), y: revSeries.map(r => r.revenue), yaxis: "y" }},
          {{ type: "scatter", mode: "lines+markers", name: "客数", x: revSeries.map(r => r.date), y: revSeries.map(r => r.visits), yaxis: "y2" }},
          {{ type: "scatter", mode: "lines+markers", name: "客単価", x: revSeries.map(r => r.date), y: revSeries.map(r => r.avg_ticket), yaxis: "y3" }},
        ], {{
          title: "売上分解（日別）: 売上 = 客数 × 客単価",
          legend: {{ orientation: "h" }},
          yaxis: {{ title: "売上(円)" }},
          yaxis2: {{ title: "客数", overlaying: "y", side: "right" }},
          yaxis3: {{ title: "客単価(円)", overlaying: "y", side: "right", position: 0.95 }},
        }});

        // --- Weekday trend ---
        const wd = DATA.weekday_data;
        Plotly.newPlot("weekday_trend", [
          {{ type: "bar", name: "来店数", x: wd.map(r => r.label), y: wd.map(r => r.visits), yaxis: "y" }},
          {{ type: "bar", name: "売上", x: wd.map(r => r.label), y: wd.map(r => r.revenue), yaxis: "y2" }},
          {{ type: "scatter", mode: "lines+markers", name: "客単価", x: wd.map(r => r.label), y: wd.map(r => r.avg_ticket), yaxis: "y3" }},
        ], {{
          title: "曜日別トレンド（来店数/売上/客単価）", barmode: "group",
          legend: {{ orientation: "h" }},
          yaxis: {{ title: "来店数" }},
          yaxis2: {{ title: "売上(円)", overlaying: "y", side: "right" }},
          yaxis3: {{ title: "客単価(円)", overlaying: "y", side: "right", position: 0.95 }},
        }});

        // --- Store benchmark ---
        const bench = filterBenchmark(store);
        const benchColors = bench.map(r => (store !== "ALL" && r.store_id === store) ? "#0f1f2e" : "#6f8592");
        Plotly.newPlot("store_benchmark", [
          {{ type: "bar", name: "売上", x: bench.map(r => r.store_id), y: bench.map(r => r.revenue), marker: {{ color: benchColors }}, yaxis: "y" }},
          {{ type: "scatter", mode: "lines+markers", name: "客単価", x: bench.map(r => r.store_id), y: bench.map(r => r.avg_ticket), yaxis: "y2" }},
        ], {{
          title: "店舗別ベンチマーク（売上/客単価）",
          yaxis: {{ title: "売上(円)" }},
          yaxis2: {{ title: "客単価(円)", overlaying: "y", side: "right" }},
          legend: {{ orientation: "h" }},
        }});

        Plotly.newPlot("store_efficiency", [
          {{ type: "bar", name: "平均滞在時間(分)", x: bench.map(r => r.store_id), y: bench.map(r => r.avg_stay), marker: {{ color: benchColors }}, yaxis: "y" }},
          {{ type: "scatter", mode: "lines+markers", name: "追加注文率(%)", x: bench.map(r => r.store_id), y: bench.map(r => r.extra_order_rate), yaxis: "y2" }},
        ], {{
          title: "店舗別運用効率（滞在時間/追加注文率）",
          yaxis: {{ title: "平均滞在時間(分)" }},
          yaxis2: {{ title: "追加注文率(%)", overlaying: "y", side: "right", range: [0, 100] }},
          legend: {{ orientation: "h" }},
        }});

        // --- Time slot ---
        const ts = DATA.time_slot_data;
        Plotly.newPlot("time_slot", [{{
          type: "bar", x: ts.map(r => r.slot), y: ts.map(r => r.visits),
        }}], {{ title: "時間帯分布（来店数）" }});

        Plotly.newPlot("time_slot_kpi", [
          {{ type: "bar", name: "売上", x: ts.map(r => r.slot), y: ts.map(r => r.revenue), yaxis: "y" }},
          {{ type: "scatter", mode: "lines+markers", name: "客単価", x: ts.map(r => r.slot), y: ts.map(r => r.avg_ticket), yaxis: "y2" }},
          {{ type: "scatter", mode: "lines+markers", name: "平均人数", x: ts.map(r => r.slot), y: ts.map(r => r.avg_party), yaxis: "y3" }},
        ], {{
          title: "時間帯別KPI（売上/客単価/平均人数）",
          yaxis: {{ title: "売上(円)" }},
          yaxis2: {{ title: "客単価(円)", overlaying: "y", side: "right" }},
          yaxis3: {{ title: "平均人数", overlaying: "y", side: "right", position: 0.95 }},
          legend: {{ orientation: "h" }},
        }});

        // --- Orders per visit ---
        const opv = DATA.orders_per_visit_data;
        Plotly.newPlot("orders_per_visit", [{{
          type: "bar", x: opv.map(r => r.orders), y: opv.map(r => r.visits),
        }}], {{ title: "1来店あたり注文数分布", xaxis: {{ title: "注文数" }}, yaxis: {{ title: "来店数" }} }});

        // --- Items per order ---
        const ipo = DATA.items_per_order_data;
        Plotly.newPlot("items_per_order", [{{
          type: "bar", x: ipo.map(r => r.items), y: ipo.map(r => r.orders),
        }}], {{ title: "1注文あたり商品数分布", xaxis: {{ title: "商品数" }}, yaxis: {{ title: "注文数" }} }});

        // --- Loyalty pie ---
        Plotly.newPlot("loyalty_pie", [{{
          type: "pie",
          labels: ["提示あり", "提示なし"],
          values: [DATA.loyalty_yes, DATA.loyalty_no],
          hole: 0.4,
        }}], {{ title: "ロイヤルティ提示率" }});

        // --- Customer segmentation ---
        const seg = DATA.customer_seg;
        Plotly.newPlot("new_existing", [
          {{ type: "bar", name: "会計件数", x: seg.map(r => r.label), y: seg.map(r => r.cnt), yaxis: "y" }},
          {{ type: "scatter", mode: "lines+markers", name: "平均会計額", x: seg.map(r => r.label), y: seg.map(r => r.avg_ticket), yaxis: "y2" }},
        ], {{
          title: "新規/既存/非会員 比較",
          yaxis: {{ title: "会計件数" }},
          yaxis2: {{ title: "平均会計額(円)", overlaying: "y", side: "right" }},
          legend: {{ orientation: "h" }},
        }});

        // --- Revenue histogram ---
        const hist = DATA.rev_hist_data;
        Plotly.newPlot("revenue_hist", [{{
          type: "bar",
          x: hist.map(r => r.range_start),
          y: hist.map(r => r.count),
        }}], {{ title: "客単価分布", xaxis: {{ title: "会計額(円)" }}, yaxis: {{ title: "件数" }} }});

        // --- Discount ---
        const disc = DATA.discount_data;
        Plotly.newPlot("discount_usage", [{{
          type: "bar", x: disc.map(r => r.discount_id), y: disc.map(r => r.count),
        }}], {{ title: "割引利用回数", xaxis: {{ title: "割引ID" }}, yaxis: {{ title: "件数" }} }});

        Plotly.newPlot("discount_effect", [
          {{ type: "bar", name: "平均会計額", x: disc.map(r => r.discount_id), y: disc.map(r => r.avg_total), yaxis: "y" }},
          {{ type: "scatter", mode: "lines+markers", name: "平均値引額", x: disc.map(r => r.discount_id), y: disc.map(r => r.avg_discount), yaxis: "y2" }},
        ], {{
          title: "割引別の効果（平均会計額/平均値引額）",
          yaxis: {{ title: "平均会計額(円)" }},
          yaxis2: {{ title: "平均値引額(円)", overlaying: "y", side: "right" }},
          legend: {{ orientation: "h" }},
        }});

        // --- Season / event ---
        const se = DATA.season_event_data;
        Plotly.newPlot("season_event", [{{
          type: "bar", x: se.map(r => r.tag), y: se.map(r => r.revenue),
        }}], {{ title: "季節/イベント別 売上寄与（上位）", xaxis: {{ title: "タグ" }}, yaxis: {{ title: "売上(円)" }} }});

        const sp = DATA.season_period_data;
        Plotly.newPlot("season_event_period", [
          {{ type: "bar", name: "季節/イベント売上", x: sp.map(r => r.label), y: sp.map(r => r.seasonal_revenue), yaxis: "y" }},
          {{ type: "scatter", mode: "lines+markers", name: "売上構成比", x: sp.map(r => r.label), y: sp.map(r => r.ratio), yaxis: "y2" }},
        ], {{
          title: "季節/イベント売上の期間比較",
          yaxis: {{ title: "売上(円)" }},
          yaxis2: {{ title: "構成比(%)", overlaying: "y", side: "right", range: [0, 100] }},
          legend: {{ orientation: "h" }},
        }});

        // --- Menu ABC ---
        const topMenu = DATA.menu_abc_data.slice(0, 10);
        Plotly.newPlot("menu_sales_top", [{{
          type: "bar", orientation: "h",
          x: topMenu.map(r => r.revenue).reverse(),
          y: topMenu.map(r => r.name).reverse(),
        }}], {{ title: "商品別売上 Top10", xaxis: {{ title: "売上(円)" }} }});

        const allMenu = DATA.menu_abc_data;
        Plotly.newPlot("menu_abc", [
          {{ type: "bar", name: "売上", x: allMenu.map(r => r.name), y: allMenu.map(r => r.revenue), yaxis: "y" }},
          {{ type: "scatter", mode: "lines+markers", name: "累積構成比", x: allMenu.map(r => r.name), y: allMenu.map(r => r.cumulative_ratio), yaxis: "y2" }},
        ], {{
          title: "メニューABC分析（売上順）",
          yaxis: {{ title: "売上(円)" }},
          yaxis2: {{ title: "累積構成比(%)", overlaying: "y", side: "right", range: [0, 100] }},
          legend: {{ orientation: "h" }},
        }});

        // --- Stay × extra order ---
        const stay = DATA.stay_data;
        Plotly.newPlot("stay_extra_order", [
          {{ type: "bar", name: "平均会計額", x: stay.map(r => r.label), y: stay.map(r => r.avg_ticket), yaxis: "y" }},
          {{ type: "scatter", mode: "lines+markers", name: "追加注文率", x: stay.map(r => r.label), y: stay.map(r => r.extra_order_rate), yaxis: "y2" }},
        ], {{
          title: "滞在時間別の追加注文率と客単価",
          yaxis: {{ title: "平均会計額(円)" }},
          yaxis2: {{ title: "追加注文率(%)", overlaying: "y", side: "right", range: [0, 100] }},
          legend: {{ orientation: "h" }},
        }});

        // --- Tax rate ---
        const taxRates = Object.entries(DATA.tax_rate_dist);
        Plotly.newPlot("tax_rate", [{{
          type: "bar",
          x: taxRates.map(([k]) => k),
          y: taxRates.map(([, v]) => v),
        }}], {{ title: "税率適用分布" }});

        // --- Store visits bar ---
        const sv = filterStoreVisits(store);
        Plotly.newPlot("visits_store", [{{
          type: "bar", x: sv.map(r => r.store), y: sv.map(r => r.visits),
        }}], {{ title: "来店数（店舗別・全期間）" }});

        // --- Latest receipts table ---
        const sample = DATA.receipt_sample;
        Plotly.newPlot("table", [{{
          type: "table",
          header: {{ values: ["レシートID", "来店ID", "会計時刻", "小計", "割引額", "税額", "合計"] }},
          cells: {{ values: [
            sample.map(r => r.receipt_id),
            sample.map(r => r.visit_id),
            sample.map(r => r.paid_at),
            sample.map(r => r.subtotal_yen.toLocaleString()),
            sample.map(r => r.discount_total_yen.toLocaleString()),
            sample.map(r => r.tax_yen.toLocaleString()),
            sample.map(r => r.total_yen.toLocaleString()),
          ] }}
        }}], {{ title: "直近レシート（最新10件）" }});
      }}

      storeSelect.onchange = () => renderAll(storeSelect.value);
      renderAll("ALL");
    }})();
    </script>
  </body>
</html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Build static dashboard HTML")
    parser.add_argument("--data-dir", default="data/output", help="CSV directory")
    parser.add_argument("--out", default="docs/index.html", help="Output HTML path")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    out_path = Path(args.out)

    print(f"Reading CSVs from {data_dir} ...")
    agg = aggregate(data_dir)
    print(f"Aggregation complete. Latest date: {agg['latest_date']}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    html = build_html(agg)
    out_path.write_text(html, encoding="utf-8")
    size_kb = len(html.encode()) // 1024
    print(f"Written {out_path} ({size_kb} KB)")


if __name__ == "__main__":
    main()
