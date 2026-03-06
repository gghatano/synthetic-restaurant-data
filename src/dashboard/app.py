from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response


def _load_csv(path: Path) -> str:
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Missing: {path.name}")
    return path.read_text(encoding="utf-8")


def _index_html() -> str:
    return """<!doctype html>
<html lang="ja">
  <head>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1"/>
    <title>ファミシン セールスダッシュボード</title>
    <script src="https://cdn.plot.ly/plotly-2.30.0.min.js"></script>
    <style>
      :root {
        --primary: #2563eb;
        --secondary: #059669;
        --accent: #d97706;
        --alert: #ef4444;
        --neutral: #6b7280;
        --success: #22c55e;
        --bg: #f3f5f6;
        --card-bg: #ffffff;
        --header-bg: #0f1f2e;
        --text: #1c2421;
        --text-sub: #5b6b74;
        --border: #e2e8f0;
      }
      * { box-sizing: border-box; }
      body { font-family: "BIZ UDPGothic", "Noto Sans JP", system-ui, sans-serif; margin: 0; background: var(--bg); color: var(--text); }
      header { padding: 20px 32px; background: var(--header-bg); color: #f4f7f8; }
      header h1 { margin: 0; font-size: 22px; font-weight: 700; letter-spacing: 0.5px; }
      .sub { opacity: 0.7; font-size: 13px; }
      .toolbar { display: flex; gap: 16px; padding: 14px 32px; background: #e9eef1; align-items: center; flex-wrap: wrap; }
      .toolbar label { font-size: 13px; font-weight: 600; color: var(--text-sub); }
      select { padding: 7px 12px; border-radius: 8px; border: 1px solid #c7d1d7; font-size: 13px; background: #fff; }

      /* Tabs */
      .tabs { display: flex; gap: 0; padding: 0 32px; background: #e9eef1; border-bottom: 2px solid var(--border); }
      .tab-btn { padding: 12px 24px; font-size: 14px; font-weight: 600; color: var(--text-sub); background: none; border: none; border-bottom: 3px solid transparent; cursor: pointer; transition: all 0.2s; margin-bottom: -2px; }
      .tab-btn:hover { color: var(--primary); }
      .tab-btn.active { color: var(--primary); border-bottom-color: var(--primary); background: rgba(37, 99, 235, 0.05); }
      .tab-content { display: none; padding: 20px 24px; }
      .tab-content.active { display: block; }

      /* Grid */
      .grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; }
      .grid-4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
      .card { background: var(--card-bg); border-radius: 12px; padding: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); transition: box-shadow 0.2s; }
      .card:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.10); }
      .wide { grid-column: span 2; }

      /* KPI Cards */
      .kpi { display: flex; flex-direction: column; gap: 6px; padding: 24px 20px; min-height: 120px; }
      .kpi .label { font-size: 13px; color: var(--text-sub); font-weight: 500; }
      .kpi .value { font-size: 28px; font-weight: 800; line-height: 1.2; }
      .kpi .change { font-size: 13px; font-weight: 600; }
      .kpi .change.up { color: var(--success); }
      .kpi .change.down { color: var(--alert); }

      /* Section headings */
      .section-heading { font-size: 16px; font-weight: 700; color: var(--text); margin: 8px 0 12px; padding-bottom: 8px; border-bottom: 2px solid var(--border); grid-column: span 2; }

      #status { padding: 8px 32px; font-size: 12px; color: var(--text-sub); background: #e9eef1; }

      @media (max-width: 1200px) {
        .grid { grid-template-columns: 1fr; }
        .grid-4 { grid-template-columns: repeat(2, 1fr); }
        .wide, .section-heading { grid-column: span 1; }
      }
      @media (max-width: 640px) {
        .grid-4 { grid-template-columns: 1fr; }
        .tabs { overflow-x: auto; }
      }
    </style>
  </head>
  <body>
    <header>
      <h1>ファミシン セールスダッシュボード</h1>
      <div class="sub" style="margin-top:4px;">店舗責任者 / 全体統括向けの購買・来店分析</div>
    </header>
    <div class="toolbar">
      <label>店舗</label>
      <select id="storeSelect"></select>
      <label style="margin-left:12px;">期間</label>
      <select id="periodSelect">
        <option value="ALL">全期間</option>
        <option value="EARLY">前半</option>
        <option value="LATE">後半</option>
      </select>
    </div>
    <div class="tabs">
      <button class="tab-btn active" data-tab="overview">概要</button>
      <button class="tab-btn" data-tab="sales">売上分析</button>
      <button class="tab-btn" data-tab="customer">顧客分析</button>
      <button class="tab-btn" data-tab="store">店舗比較</button>
      <button class="tab-btn" data-tab="menu">メニュー分析</button>
    </div>
    <div id="status">読み込み中...</div>
    <noscript>JavaScriptが無効です。ブラウザ設定をご確認ください。</noscript>

    <!-- Overview Tab -->
    <div class="tab-content active" id="tab-overview">
      <div class="grid-4" style="margin-bottom:16px;">
        <div class="card kpi" id="kpi_visits"></div>
        <div class="card kpi" id="kpi_revenue"></div>
        <div class="card kpi" id="kpi_avg"></div>
        <div class="card kpi" id="kpi_loyalty"></div>
      </div>
      <div class="grid">
        <div class="card wide" id="daily_revenue_overview"></div>
        <div class="card wide" id="store_ranking_table"></div>
      </div>
    </div>

    <!-- Sales Tab -->
    <div class="tab-content" id="tab-sales">
      <div class="grid">
        <div class="section-heading">日次トレンド</div>
        <div class="card" id="daily_visits"></div>
        <div class="card" id="daily_revenue"></div>
        <div class="section-heading">曜日・時間帯</div>
        <div class="card" id="weekday_visits"></div>
        <div class="card" id="weekday_revenue"></div>
        <div class="section-heading">売上分解</div>
        <div class="card" id="sales_decomp_revenue"></div>
        <div class="card" id="sales_decomp_count"></div>
        <div class="section-heading">時間帯分析</div>
        <div class="card" id="time_slot_revenue"></div>
        <div class="card" id="time_slot_avg"></div>
      </div>
    </div>

    <!-- Customer Tab -->
    <div class="tab-content" id="tab-customer">
      <div class="grid">
        <div class="section-heading">顧客セグメント</div>
        <div class="card" id="loyalty"></div>
        <div class="card" id="new_existing"></div>
        <div class="card" id="revenue_hist"></div>
        <div class="card" id="discount_usage"></div>
        <div class="card" id="discount_effect"></div>
      </div>
    </div>

    <!-- Store Tab -->
    <div class="tab-content" id="tab-store">
      <div class="grid">
        <div class="section-heading">店舗パフォーマンス</div>
        <div class="card" id="store_benchmark"></div>
        <div class="card" id="store_efficiency"></div>
        <div class="card wide" id="visits_store"></div>
      </div>
    </div>

    <!-- Menu Tab -->
    <div class="tab-content" id="tab-menu">
      <div class="grid">
        <div class="section-heading">商品分析</div>
        <div class="card" id="menu_sales_top"></div>
        <div class="card" id="menu_abc"></div>
        <div class="section-heading">季節・滞在</div>
        <div class="card" id="season_event"></div>
        <div class="card" id="stay_extra_order"></div>
      </div>
    </div>

    <script>
      /* ---- Tab switching ---- */
      document.querySelectorAll(".tab-btn").forEach(btn => {
        btn.addEventListener("click", () => {
          document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
          document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
          btn.classList.add("active");
          document.getElementById("tab-" + btn.dataset.tab).classList.add("active");
          window.dispatchEvent(new Event("resize"));
        });
      });

      /* ---- Utility ---- */
      function setStatus(message) {
        const el = document.getElementById("status");
        if (el) el.textContent = message;
      }

      window.onerror = function(message, source, lineno) {
        setStatus("エラー発生: " + message + " (" + lineno + ")");
      };

      async function fetchCsv(name) {
        const res = await fetch("/data/" + name);
        if (!res.ok) throw new Error("Failed to load " + name);
        const text = await res.text();
        return parseCsv(text);
      }

      function parseCsv(text) {
        const lines = text.trim().split(/\\r?\\n/);
        if (lines.length === 0) return [];
        const headers = lines[0].split(",");
        return lines.slice(1).map(line => {
          const cols = line.split(",");
          const row = {};
          headers.forEach((h, i) => row[h] = cols[i] ?? "");
          return row;
        });
      }

      function counter(rows, key) {
        const out = {};
        rows.forEach(r => { out[r[key]] = (out[r[key]] || 0) + 1; });
        return out;
      }

      function minutesBetween(isoStart, isoEnd) {
        const start = Date.parse(isoStart || "");
        const end = Date.parse(isoEnd || "");
        if (!Number.isFinite(start) || !Number.isFinite(end) || end < start) return null;
        return Math.round((end - start) / 60000);
      }

      /* ---- Color palette ---- */
      const COLORS = ["#2563eb", "#059669", "#d97706", "#ef4444", "#6b7280", "#8b5cf6", "#ec4899", "#14b8a6"];
      const defaultLayout = {
        colorway: COLORS,
        font: { family: '"BIZ UDPGothic", "Noto Sans JP", system-ui, sans-serif', size: 12 },
        margin: { t: 48, b: 40, l: 56, r: 48 },
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
        legend: { orientation: "h", y: -0.15 },
      };
      function L(overrides) {
        return Object.assign({}, defaultLayout, overrides);
      }

      /* ---- KPI rendering ---- */
      function renderKpi(id, label, value, changePercent) {
        const el = document.getElementById(id);
        if (!el) return;
        el.replaceChildren();
        const labelEl = document.createElement("div");
        labelEl.className = "label";
        labelEl.textContent = label;
        const valueEl = document.createElement("div");
        valueEl.className = "value";
        valueEl.textContent = value;
        el.append(labelEl, valueEl);
        if (changePercent !== undefined && changePercent !== null && isFinite(changePercent)) {
          const changeEl = document.createElement("div");
          const isUp = changePercent >= 0;
          changeEl.className = "change " + (isUp ? "up" : "down");
          const arrow = isUp ? "▲" : "▼";
          changeEl.textContent = arrow + " " + Math.abs(changePercent).toFixed(1) + "% (後半 vs 前半)";
          el.appendChild(changeEl);
        }
      }

      /* ---- Main render ---- */
      function render() {
        setStatus("スクリプト起動: データ読み込み開始");
        if (typeof Plotly === "undefined") {
          setStatus("Plotlyの読み込みに失敗しました。ネットワークをご確認ください。");
          return;
        }
        Promise.all([
          fetchCsv("visit.csv"),
          fetchCsv("order.csv"),
          fetchCsv("order_item.csv"),
          fetchCsv("receipt.csv"),
          fetchCsv("menu_item.csv"),
        ]).then(([visits, orders, items, receipts, menu]) => {
          setStatus("読み込み完了");
          const visitById = {};
          visits.forEach(v => { visitById[v["visit_id"]] = v; });
          const customerFirstDate = {};
          receipts.forEach(r => {
            const cid = r["customer_id"];
            const v = visitById[r["visit_id"]];
            if (!cid || !v) return;
            const d = v["visit_date"] || "";
            if (!d) return;
            if (!customerFirstDate[cid] || d < customerFirstDate[cid]) {
              customerFirstDate[cid] = d;
            }
          });

          /* Store selector */
          const storeSelect = document.getElementById("storeSelect");
          const storeIds = [...new Set(visits.map(v => v["store_id"]))].sort();
          storeSelect.innerHTML = "";
          const optAll = document.createElement("option");
          optAll.value = "ALL";
          optAll.textContent = "全店";
          storeSelect.appendChild(optAll);
          storeIds.forEach(s => {
            const opt = document.createElement("option");
            opt.value = s;
            opt.textContent = "店舗 " + s;
            storeSelect.appendChild(opt);
          });

          /* Pivot date for period filter */
          const allDates = [...new Set(visits.map(v => v["visit_date"]).filter(Boolean))].sort();
          const pivotDate = allDates.length ? allDates[Math.floor(allDates.length / 2)] : "";

          function filterByStore(rows, storeIdKey, selected) {
            if (selected === "ALL") return rows;
            return rows.filter(r => r[storeIdKey] === selected);
          }

          function filterByPeriod(visitRows, period) {
            if (period === "ALL" || !pivotDate) return visitRows;
            if (period === "EARLY") return visitRows.filter(v => (v["visit_date"] || "") < pivotDate);
            return visitRows.filter(v => (v["visit_date"] || "") >= pivotDate);
          }

          function renderAll(selectedStore, selectedPeriod) {
            let fVisits = filterByStore(visits, "store_id", selectedStore);
            fVisits = filterByPeriod(fVisits, selectedPeriod);
            const visitIds = new Set(fVisits.map(v => v["visit_id"]));
            const fOrders = orders.filter(o => visitIds.has(o["visit_id"]));
            const orderIds = new Set(fOrders.map(o => o["order_id"]));
            const fItems = items.filter(i => orderIds.has(i["order_id"]));
            const fReceipts = receipts.filter(r => visitIds.has(r["visit_id"]));

            /* ============================================
               KPI with half-period comparison
               ============================================ */
            const totalVisits = fVisits.length;
            const totalRevenue = fReceipts.reduce((acc, r) => acc + parseInt(r["total_yen"] || "0", 10), 0);
            const avgRevenue = totalVisits ? Math.round(totalRevenue / totalVisits) : 0;
            const loyaltyYes = fReceipts.filter(r => r["customer_id"]).length;
            const loyaltyRate = fReceipts.length ? Math.round((loyaltyYes / fReceipts.length) * 100) : 0;

            /* Split current filtered data into first-half and second-half for comparison */
            const filteredDates = [...new Set(fVisits.map(v => v["visit_date"]).filter(Boolean))].sort();
            const halfPivot = filteredDates.length ? filteredDates[Math.floor(filteredDates.length / 2)] : "";
            function splitHalf(visitRows, receiptRows) {
              const earlyV = visitRows.filter(v => (v["visit_date"] || "") < halfPivot);
              const lateV = visitRows.filter(v => (v["visit_date"] || "") >= halfPivot);
              const earlyVids = new Set(earlyV.map(v => v["visit_id"]));
              const lateVids = new Set(lateV.map(v => v["visit_id"]));
              const earlyR = receiptRows.filter(r => earlyVids.has(r["visit_id"]));
              const lateR = receiptRows.filter(r => lateVids.has(r["visit_id"]));
              return { earlyV, lateV, earlyR, lateR };
            }
            let kpiVisitsChange = null, kpiRevenueChange = null, kpiAvgChange = null, kpiLoyaltyChange = null;
            if (halfPivot) {
              const h = splitHalf(fVisits, fReceipts);
              const eVisits = h.earlyV.length, lVisits = h.lateV.length;
              const eRev = h.earlyR.reduce((a, r) => a + parseInt(r["total_yen"] || "0", 10), 0);
              const lRev = h.lateR.reduce((a, r) => a + parseInt(r["total_yen"] || "0", 10), 0);
              const eAvg = eVisits ? eRev / eVisits : 0;
              const lAvg = lVisits ? lRev / lVisits : 0;
              const eLoyalty = h.earlyR.length ? h.earlyR.filter(r => r["customer_id"]).length / h.earlyR.length * 100 : 0;
              const lLoyalty = h.lateR.length ? h.lateR.filter(r => r["customer_id"]).length / h.lateR.length * 100 : 0;
              if (eVisits) kpiVisitsChange = ((lVisits - eVisits) / eVisits) * 100;
              if (eRev) kpiRevenueChange = ((lRev - eRev) / eRev) * 100;
              if (eAvg) kpiAvgChange = ((lAvg - eAvg) / eAvg) * 100;
              if (eLoyalty) kpiLoyaltyChange = lLoyalty - eLoyalty;
            }
            renderKpi("kpi_visits", "来店数", totalVisits.toLocaleString(), kpiVisitsChange);
            renderKpi("kpi_revenue", "売上合計", "¥" + totalRevenue.toLocaleString(), kpiRevenueChange);
            renderKpi("kpi_avg", "客単価", "¥" + avgRevenue.toLocaleString(), kpiAvgChange);
            renderKpi("kpi_loyalty", "ロイヤルティ提示率", loyaltyRate + "%", kpiLoyaltyChange);

            /* ============================================
               OVERVIEW TAB
               ============================================ */
            /* Daily revenue trend (overview) */
            const revenueByDate = {};
            fReceipts.forEach(r => {
              const d = (r["paid_at"] || "").slice(0,10);
              revenueByDate[d] = (revenueByDate[d] || 0) + parseInt(r["total_yen"] || "0", 10);
            });
            const revDates = Object.keys(revenueByDate).sort();
            Plotly.newPlot("daily_revenue_overview", [{
              type: "scatter",
              mode: "lines",
              x: revDates,
              y: revDates.map(d => revenueByDate[d] || 0),
              line: { color: "#2563eb", width: 2 },
              fill: "tozeroy",
              fillcolor: "rgba(37, 99, 235, 0.08)",
            }], L({ title: "日別売上トレンド", xaxis: { title: "日付" }, yaxis: { title: "売上(円)" } }), { responsive: true });

            /* Store ranking table */
            const storeAgg = {};
            storeIds.forEach(s => {
              storeAgg[s] = { visits: 0, revenue: 0, durationSum: 0, durationCnt: 0, extraVisits: 0 };
            });
            const allVisitExtra = {};
            orders.forEach(o => {
              const vid = o["visit_id"];
              const seq = parseInt(o["order_seq_in_visit"] || "0", 10);
              if (!allVisitExtra[vid]) allVisitExtra[vid] = false;
              if (seq >= 2) allVisitExtra[vid] = true;
            });
            visits.forEach(v => {
              const s = v["store_id"];
              if (!storeAgg[s]) storeAgg[s] = { visits: 0, revenue: 0, durationSum: 0, durationCnt: 0, extraVisits: 0 };
              storeAgg[s].visits += 1;
              const duration = minutesBetween(v["seated_at"], v["left_at"]);
              if (duration !== null) {
                storeAgg[s].durationSum += duration;
                storeAgg[s].durationCnt += 1;
              }
              if (allVisitExtra[v["visit_id"]]) storeAgg[s].extraVisits += 1;
            });
            receipts.forEach(r => {
              const v = visitById[r["visit_id"]];
              if (!v) return;
              const s = v["store_id"];
              if (!storeAgg[s]) return;
              storeAgg[s].revenue += parseInt(r["total_yen"] || "0", 10);
            });

            const rankedStores = [...storeIds].sort((a, b) => (storeAgg[b] ? storeAgg[b].revenue : 0) - (storeAgg[a] ? storeAgg[a].revenue : 0));
            const rankStoreIds = rankedStores;
            const rankVisits = rankStoreIds.map(s => storeAgg[s] ? storeAgg[s].visits : 0);
            const rankRevenue = rankStoreIds.map(s => storeAgg[s] ? storeAgg[s].revenue : 0);
            const rankAvgTicket = rankStoreIds.map((s, i) => rankVisits[i] ? Math.round(rankRevenue[i] / rankVisits[i]) : 0);
            Plotly.newPlot("store_ranking_table", [{
              type: "table",
              header: {
                values: ["店舗ID", "来店数", "売上(円)", "客単価(円)"],
                align: "center",
                fill: { color: "#2563eb" },
                font: { color: "white", size: 13 },
                height: 32,
              },
              cells: {
                values: [
                  rankStoreIds,
                  rankVisits.map(v => v.toLocaleString()),
                  rankRevenue.map(v => "¥" + v.toLocaleString()),
                  rankAvgTicket.map(v => "¥" + v.toLocaleString()),
                ],
                align: "center",
                height: 28,
                font: { size: 12 },
                fill: { color: [rankStoreIds.map((_, i) => i % 2 === 0 ? "#f8fafc" : "#ffffff")] },
              },
            }], L({ title: "店舗ランキング（売上順）" }), { responsive: true });

            /* ============================================
               SALES TAB
               ============================================ */
            /* Daily visits */
            const visitsByDate = {};
            fVisits.forEach(v => {
              if (!visitsByDate[v["visit_date"]]) visitsByDate[v["visit_date"]] = {};
              visitsByDate[v["visit_date"]][v["store_id"]] = (visitsByDate[v["visit_date"]][v["store_id"]] || 0) + 1;
            });
            const dates = Object.keys(visitsByDate).sort();
            const stores = selectedStore === "ALL" ? storeIds : [selectedStore];
            const visitTraces = stores.map((s, idx) => ({
              type: "scatter",
              mode: "lines",
              name: "店舗 " + s,
              x: dates,
              y: dates.map(d => (visitsByDate[d] && visitsByDate[d][s]) || 0),
              line: { color: COLORS[idx % COLORS.length] },
            }));
            Plotly.newPlot("daily_visits", visitTraces, L({ title: "日別来店数（店舗別）", xaxis: { title: "日付" }, yaxis: { title: "来店数" } }), { responsive: true });

            /* Daily revenue */
            Plotly.newPlot("daily_revenue", [{
              type: "scatter",
              mode: "lines",
              x: revDates,
              y: revDates.map(d => revenueByDate[d] || 0),
              line: { color: "#2563eb", width: 2 },
            }], L({ title: "日別売上", xaxis: { title: "日付" }, yaxis: { title: "売上(円)" } }), { responsive: true });

            /* Weekday trend - split into 2 charts */
            const weekdayOrder = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
            const weekdayLabel = { Mon: "月", Tue: "火", Wed: "水", Thu: "木", Fri: "金", Sat: "土", Sun: "日" };
            const weekdayAgg = {};
            weekdayOrder.forEach(w => { weekdayAgg[w] = { visits: 0, revenue: 0 }; });
            const visitWeekdayById = {};
            fVisits.forEach(v => {
              const w = v["day_of_week"];
              if (!weekdayAgg[w]) weekdayAgg[w] = { visits: 0, revenue: 0 };
              weekdayAgg[w].visits += 1;
              visitWeekdayById[v["visit_id"]] = w;
            });
            fReceipts.forEach(r => {
              const w = visitWeekdayById[r["visit_id"]];
              if (!w) return;
              weekdayAgg[w].revenue += parseInt(r["total_yen"] || "0", 10);
            });
            const presentWeekdays = weekdayOrder.filter(w => weekdayAgg[w] && weekdayAgg[w].visits > 0);
            const weekdayX = presentWeekdays.map(w => weekdayLabel[w] || w);
            const weekdayVisits = presentWeekdays.map(w => weekdayAgg[w].visits);
            const weekdayRevenue = presentWeekdays.map(w => weekdayAgg[w].revenue);

            Plotly.newPlot("weekday_visits", [{
              type: "bar",
              x: weekdayX,
              y: weekdayVisits,
              marker: { color: "#059669" },
            }], L({ title: "曜日別 来店数", xaxis: { title: "曜日" }, yaxis: { title: "来店数" } }), { responsive: true });

            Plotly.newPlot("weekday_revenue", [{
              type: "bar",
              x: weekdayX,
              y: weekdayRevenue,
              marker: { color: "#2563eb" },
            }], L({ title: "曜日別 売上", xaxis: { title: "曜日" }, yaxis: { title: "売上(円)" } }), { responsive: true });

            /* Sales decomposition - split into 2 charts */
            const decompDateSet = new Set([
              ...fVisits.map(v => v["visit_date"]),
              ...Object.keys(revenueByDate),
            ]);
            const decompDates = Array.from(decompDateSet).sort();
            const visitsDaily = {};
            fVisits.forEach(v => {
              const d = v["visit_date"];
              visitsDaily[d] = (visitsDaily[d] || 0) + 1;
            });
            const decompVisits = decompDates.map(d => visitsDaily[d] || 0);
            const decompRevenue = decompDates.map(d => revenueByDate[d] || 0);
            const decompAvg = decompDates.map((d, i) => {
              const vc = decompVisits[i] || 0;
              return vc ? Math.round((decompRevenue[i] || 0) / vc) : 0;
            });

            Plotly.newPlot("sales_decomp_revenue", [
              { type: "bar", name: "売上", x: decompDates, y: decompRevenue, marker: { color: "#2563eb" } },
              { type: "scatter", mode: "lines+markers", name: "客数", x: decompDates, y: decompVisits, yaxis: "y2", line: { color: "#059669" } },
            ], L({
              title: "売上分解: 売上 & 客数",
              yaxis: { title: "売上(円)" },
              yaxis2: { title: "客数", overlaying: "y", side: "right" },
            }), { responsive: true });

            Plotly.newPlot("sales_decomp_count", [{
              type: "scatter",
              mode: "lines+markers",
              x: decompDates,
              y: decompAvg,
              line: { color: "#d97706", width: 2 },
              marker: { color: "#d97706" },
            }], L({ title: "売上分解: 客単価推移", xaxis: { title: "日付" }, yaxis: { title: "客単価(円)" } }), { responsive: true });

            /* Time slot analysis - split into 2 charts */
            const revenueByTimeSlot = {};
            const partyByTimeSlot = {};
            const visitCountByTimeSlot = {};
            const visitSlotById = {};
            fVisits.forEach(v => {
              const slot = v["time_slot"] || "unknown";
              const party = parseInt(v["adult_cnt"] || "0", 10) + parseInt(v["child_cnt"] || "0", 10);
              visitSlotById[v["visit_id"]] = slot;
              visitCountByTimeSlot[slot] = (visitCountByTimeSlot[slot] || 0) + 1;
              partyByTimeSlot[slot] = (partyByTimeSlot[slot] || 0) + party;
              if (!revenueByTimeSlot[slot]) revenueByTimeSlot[slot] = 0;
            });
            fReceipts.forEach(r => {
              const slot = visitSlotById[r["visit_id"]] || "unknown";
              revenueByTimeSlot[slot] = (revenueByTimeSlot[slot] || 0) + parseInt(r["total_yen"] || "0", 10);
            });
            const slotKeys = Object.keys(visitCountByTimeSlot).sort();
            const slotRevenue = slotKeys.map(k => revenueByTimeSlot[k] || 0);
            const slotAvgRevenue = slotKeys.map((k, i) => {
              const cnt = visitCountByTimeSlot[k] || 0;
              return cnt ? Math.round(slotRevenue[i] / cnt) : 0;
            });

            Plotly.newPlot("time_slot_revenue", [{
              type: "bar",
              x: slotKeys,
              y: slotRevenue,
              marker: { color: "#2563eb" },
            }], L({ title: "時間帯別 売上", xaxis: { title: "時間帯" }, yaxis: { title: "売上(円)" } }), { responsive: true });

            Plotly.newPlot("time_slot_avg", [{
              type: "bar",
              x: slotKeys,
              y: slotAvgRevenue,
              marker: { color: "#d97706" },
            }], L({ title: "時間帯別 客単価", xaxis: { title: "時間帯" }, yaxis: { title: "客単価(円)" } }), { responsive: true });

            /* ============================================
               CUSTOMER TAB
               ============================================ */
            /* Loyalty */
            const loyaltyNo = fReceipts.length - loyaltyYes;
            Plotly.newPlot("loyalty", [{
              type: "pie",
              labels: ["提示あり", "提示なし"],
              values: [loyaltyYes, loyaltyNo],
              marker: { colors: ["#059669", "#6b7280"] },
              hole: 0.4,
            }], L({ title: "ロイヤルティ提示率" }), { responsive: true });

            /* New / Existing / Guest */
            const seg = {
              new_member: { cnt: 0, total: 0 },
              returning_member: { cnt: 0, total: 0 },
              guest: { cnt: 0, total: 0 },
            };
            fReceipts.forEach(r => {
              const v = visitById[r["visit_id"]];
              const cid = r["customer_id"];
              const total = parseInt(r["total_yen"] || "0", 10);
              if (!cid) { seg.guest.cnt += 1; seg.guest.total += total; return; }
              const visitDate = v ? (v["visit_date"] || "") : "";
              if (visitDate && customerFirstDate[cid] && visitDate === customerFirstDate[cid]) {
                seg.new_member.cnt += 1; seg.new_member.total += total;
              } else {
                seg.returning_member.cnt += 1; seg.returning_member.total += total;
              }
            });
            const segKeys = ["new_member", "returning_member", "guest"];
            const segLabels = ["新規会員", "既存会員", "非会員"];
            const segCounts = segKeys.map(k => seg[k].cnt);
            const segAvg = segKeys.map(k => seg[k].cnt ? Math.round(seg[k].total / seg[k].cnt) : 0);
            Plotly.newPlot("new_existing", [
              { type: "bar", name: "会計件数", x: segLabels, y: segCounts, marker: { color: "#2563eb" } },
              { type: "scatter", mode: "lines+markers", name: "平均会計額", x: segLabels, y: segAvg, yaxis: "y2", line: { color: "#d97706" } },
            ], L({
              title: "新規/既存/非会員 比較",
              yaxis: { title: "会計件数" },
              yaxis2: { title: "平均会計額(円)", overlaying: "y", side: "right" },
            }), { responsive: true });

            /* Revenue histogram */
            const revenue = fReceipts.map(r => parseInt(r["total_yen"] || "0", 10));
            Plotly.newPlot("revenue_hist", [{
              type: "histogram",
              x: revenue,
              nbinsx: 20,
              marker: { color: "#d97706" },
            }], L({ title: "客単価分布", xaxis: { title: "会計額(円)" }, yaxis: { title: "件数" } }), { responsive: true });

            /* Discount usage */
            const discountUsage = {};
            const discountStats = {};
            fReceipts.forEach(r => {
              const total = parseInt(r["total_yen"] || "0", 10);
              const discountYen = parseInt(r["discount_total_yen"] || "0", 10);
              const applied = (r["applied_discount_ids"] || "").split("|").filter(Boolean);
              const labels = applied.length ? applied : ["NONE"];
              labels.forEach(d => {
                discountUsage[d] = (discountUsage[d] || 0) + 1;
                if (!discountStats[d]) discountStats[d] = { cnt: 0, totalYen: 0, discountYen: 0 };
                discountStats[d].cnt += 1;
                discountStats[d].totalYen += total;
                discountStats[d].discountYen += discountYen;
              });
            });
            Plotly.newPlot("discount_usage", [{
              type: "bar",
              x: Object.keys(discountUsage),
              y: Object.values(discountUsage),
              marker: { color: "#6b7280" },
            }], L({ title: "割引利用回数", xaxis: { title: "割引ID" }, yaxis: { title: "回数" } }), { responsive: true });

            /* Discount effect */
            const discountKeys = Object.keys(discountStats).sort((a, b) => discountStats[b].cnt - discountStats[a].cnt);
            const avgTotal = discountKeys.map(k => { const s = discountStats[k]; return s.cnt ? Math.round(s.totalYen / s.cnt) : 0; });
            const avgDiscount = discountKeys.map(k => { const s = discountStats[k]; return s.cnt ? Math.round(s.discountYen / s.cnt) : 0; });
            Plotly.newPlot("discount_effect", [
              { type: "bar", name: "平均会計額", x: discountKeys, y: avgTotal, marker: { color: "#2563eb" } },
              { type: "scatter", mode: "lines+markers", name: "平均値引額", x: discountKeys, y: avgDiscount, yaxis: "y2", line: { color: "#ef4444" } },
            ], L({
              title: "割引別の効果",
              yaxis: { title: "平均会計額(円)" },
              yaxis2: { title: "平均値引額(円)", overlaying: "y", side: "right" },
            }), { responsive: true });

            /* ============================================
               STORE TAB
               ============================================ */
            const benchStores = [...storeIds].sort();
            const benchRevenue = benchStores.map(s => storeAgg[s] ? storeAgg[s].revenue : 0);
            const benchAvgTicket = benchStores.map((s, i) => {
              const vc = storeAgg[s] ? storeAgg[s].visits : 0;
              return vc ? Math.round((benchRevenue[i] || 0) / vc) : 0;
            });
            const benchAvgStay = benchStores.map(s => {
              const row = storeAgg[s];
              return row && row.durationCnt ? Number((row.durationSum / row.durationCnt).toFixed(1)) : 0;
            });
            const benchExtraRate = benchStores.map(s => {
              const row = storeAgg[s];
              return row && row.visits ? Number(((row.extraVisits / row.visits) * 100).toFixed(1)) : 0;
            });
            const benchColors = benchStores.map(s => (selectedStore !== "ALL" && s === selectedStore) ? "#2563eb" : "#6b7280");

            Plotly.newPlot("store_benchmark", [
              { type: "bar", name: "売上", x: benchStores, y: benchRevenue, marker: { color: benchColors } },
              { type: "scatter", mode: "lines+markers", name: "客単価", x: benchStores, y: benchAvgTicket, yaxis: "y2", line: { color: "#d97706" } },
            ], L({
              title: "店舗別ベンチマーク（売上/客単価）",
              yaxis: { title: "売上(円)" },
              yaxis2: { title: "客単価(円)", overlaying: "y", side: "right" },
            }), { responsive: true });

            Plotly.newPlot("store_efficiency", [
              { type: "bar", name: "平均滞在時間", x: benchStores, y: benchAvgStay, marker: { color: benchColors } },
              { type: "scatter", mode: "lines+markers", name: "追加注文率", x: benchStores, y: benchExtraRate, yaxis: "y2", line: { color: "#059669" } },
            ], L({
              title: "店舗別運用効率（滞在時間/追加注文率）",
              yaxis: { title: "平均滞在時間(分)" },
              yaxis2: { title: "追加注文率(%)", overlaying: "y", side: "right", range: [0, 100] },
            }), { responsive: true });

            /* Visits by store */
            const visitsByStore = counter(fVisits, "store_id");
            Plotly.newPlot("visits_store", [{
              type: "bar",
              x: Object.keys(visitsByStore),
              y: Object.values(visitsByStore),
              marker: { color: "#059669" },
            }], L({ title: "来店数（店舗別）", xaxis: { title: "店舗ID" }, yaxis: { title: "来店数" } }), { responsive: true });

            /* ============================================
               MENU TAB
               ============================================ */
            const menuById = {};
            menu.forEach(m => { menuById[m["menu_item_id"]] = m; });
            const orderToVisit = {};
            fOrders.forEach(o => { orderToVisit[o["order_id"]] = o["visit_id"]; });

            /* Top 10 menu sales */
            const menuSales = {};
            fItems.forEach(i => {
              const m = menuById[i["menu_item_id"]];
              const menuName = m ? m["name"] : i["menu_item_id"];
              const sales = parseInt(i["line_subtotal_yen"] || "0", 10);
              menuSales[menuName] = (menuSales[menuName] || 0) + sales;
            });
            const menuRanked = Object.entries(menuSales).sort((a, b) => b[1] - a[1]);
            const top10 = menuRanked.slice(0, 10);
            Plotly.newPlot("menu_sales_top", [{
              type: "bar",
              orientation: "h",
              x: top10.map(e => e[1]).reverse(),
              y: top10.map(e => e[0]).reverse(),
              marker: { color: "#2563eb" },
            }], L({ title: "商品別売上 Top10", xaxis: { title: "売上(円)" } }), { responsive: true });

            /* ABC analysis */
            const totalMenuSales = menuRanked.reduce((acc, [, yen]) => acc + yen, 0);
            let cumulative = 0;
            const cumulativeRatio = menuRanked.map(([, yen]) => {
              cumulative += yen;
              return totalMenuSales ? (cumulative / totalMenuSales) * 100 : 0;
            });
            Plotly.newPlot("menu_abc", [
              { type: "bar", name: "売上", x: menuRanked.map(e => e[0]), y: menuRanked.map(e => e[1]), marker: { color: "#2563eb" } },
              { type: "scatter", mode: "lines+markers", name: "累積構成比", x: menuRanked.map(e => e[0]), y: cumulativeRatio, yaxis: "y2", line: { color: "#d97706" } },
            ], L({
              title: "メニューABC分析（売上順）",
              yaxis: { title: "売上(円)" },
              yaxis2: { title: "累積構成比(%)", overlaying: "y", side: "right", range: [0, 100] },
            }), { responsive: true });

            /* Season/Event */
            const seasonEvent = {};
            fItems.forEach(i => {
              const m = menuById[i["menu_item_id"]];
              if (!m) return;
              const sales = parseInt(i["line_subtotal_yen"] || "0", 10);
              const tags = [];
              if (m["season"]) tags.push("季節:" + m["season"]);
              if (m["event"]) tags.push("イベント:" + m["event"]);
              if (tags.length === 0) tags.push("通常");
              tags.forEach(tag => { seasonEvent[tag] = (seasonEvent[tag] || 0) + sales; });
            });
            const seasonEventRanked = Object.entries(seasonEvent).sort((a, b) => b[1] - a[1]).slice(0, 12);
            Plotly.newPlot("season_event", [{
              type: "bar",
              x: seasonEventRanked.map(e => e[0]),
              y: seasonEventRanked.map(e => e[1]),
              marker: { color: "#8b5cf6" },
            }], L({ title: "季節/イベント別 売上寄与（上位）", xaxis: { title: "カテゴリ" }, yaxis: { title: "売上(円)" } }), { responsive: true });

            /* Stay duration & extra order */
            const visitSummary = {};
            fVisits.forEach(v => {
              visitSummary[v["visit_id"]] = { duration: minutesBetween(v["seated_at"], v["left_at"]), extraOrdered: false, totalYen: 0 };
            });
            fOrders.forEach(o => {
              const key = o["visit_id"];
              if (!visitSummary[key]) return;
              if (parseInt(o["order_seq_in_visit"] || "0", 10) >= 2) visitSummary[key].extraOrdered = true;
            });
            fReceipts.forEach(r => {
              const key = r["visit_id"];
              if (!visitSummary[key]) return;
              visitSummary[key].totalYen += parseInt(r["total_yen"] || "0", 10);
            });
            const stayBins = [
              { label: "<45分", min: 0, max: 44 },
              { label: "45-59分", min: 45, max: 59 },
              { label: "60-89分", min: 60, max: 89 },
              { label: "90分以上", min: 90, max: Number.POSITIVE_INFINITY },
            ];
            const stayAgg = {};
            stayBins.forEach(b => { stayAgg[b.label] = { cnt: 0, extra: 0, total: 0 }; });
            Object.values(visitSummary).forEach(v => {
              if (v.duration === null) return;
              const bin = stayBins.find(b => v.duration >= b.min && v.duration <= b.max);
              if (!bin) return;
              const row = stayAgg[bin.label];
              row.cnt += 1; row.total += v.totalYen;
              if (v.extraOrdered) row.extra += 1;
            });
            const stayLabels = stayBins.map(b => b.label);
            const stayExtraRate = stayLabels.map(label => { const row = stayAgg[label]; return row.cnt ? Number(((row.extra / row.cnt) * 100).toFixed(1)) : 0; });
            const stayAvgYen = stayLabels.map(label => { const row = stayAgg[label]; return row.cnt ? Math.round(row.total / row.cnt) : 0; });
            Plotly.newPlot("stay_extra_order", [
              { type: "bar", name: "平均会計額", x: stayLabels, y: stayAvgYen, marker: { color: "#2563eb" } },
              { type: "scatter", mode: "lines+markers", name: "追加注文率", x: stayLabels, y: stayExtraRate, yaxis: "y2", line: { color: "#059669" } },
            ], L({
              title: "滞在時間別の追加注文率と単価",
              yaxis: { title: "平均会計額(円)" },
              yaxis2: { title: "追加注文率(%)", overlaying: "y", side: "right", range: [0, 100] },
            }), { responsive: true });

          } /* end renderAll */

          storeSelect.onchange = () => renderAll(storeSelect.value, document.getElementById("periodSelect").value);
          document.getElementById("periodSelect").onchange = () => renderAll(storeSelect.value, document.getElementById("periodSelect").value);
          renderAll("ALL", "ALL");
        }).catch(err => {
          console.error(err);
          setStatus("データの読み込みに失敗しました。/data/*.csv を確認してください。");
        });
      }

      window.addEventListener("DOMContentLoaded", () => {
        render();
      });
    </script>
  </body>
</html>
"""


def create_app(data_dir: Path) -> FastAPI:
    app = FastAPI()

    @app.get("/", response_class=HTMLResponse)
    def index():
        return _index_html()

    @app.get("/data/{name}")
    def get_data(name: str):
        if not name.endswith(".csv"):
            raise HTTPException(status_code=400, detail="csv only")
        content = _load_csv(data_dir / name)
        return Response(content=content, media_type="text/csv")

    return app
