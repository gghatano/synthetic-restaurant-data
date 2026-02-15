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
      body { font-family: "BIZ UDPGothic", "Noto Sans JP", system-ui, sans-serif; margin: 0; background: #f3f5f6; color: #1c2421; }
      header { padding: 16px 24px; background: #0f1f2e; color: #f4f7f8; }
      header h2 { margin: 0 0 4px; font-size: 20px; }
      .sub { opacity: 0.8; font-size: 13px; }
      .toolbar { display: flex; gap: 12px; padding: 12px 24px; background: #e9eef1; align-items: center; }
      .toolbar label { font-size: 13px; }
      select { padding: 6px 10px; border-radius: 8px; border: 1px solid #c7d1d7; }
      .grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; padding: 16px; }
      .card { background: #ffffff; border-radius: 12px; padding: 10px 12px; box-shadow: 0 6px 16px rgba(0,0,0,0.06); }
      .wide { grid-column: span 4; }
      .half { grid-column: span 2; }
      .kpi { display: flex; flex-direction: column; gap: 4px; }
      .kpi .label { font-size: 12px; color: #5b6b74; }
      .kpi .value { font-size: 20px; font-weight: 700; }
      #table { height: 360px; }
      @media (max-width: 1200px) { .grid { grid-template-columns: 1fr; } .wide, .half { grid-column: span 1; } }
    </style>
  </head>
  <body>
    <header>
      <h2>ファミシン セールスダッシュボード</h2>
      <div class="sub">店舗責任者 / 全体統括向けの購買・来店ダッシュボード</div>
    </header>
    <div class="toolbar">
      <label>表示対象</label>
      <select id="storeSelect"></select>
      <span class="sub">対象: 全店 / 店舗別の切替</span>
    </div>
    <div class="toolbar sub" id="status">読み込み中...</div>
    <noscript>JavaScriptが無効です。ブラウザ設定をご確認ください。</noscript>
    <div class="grid">
      <div class="card kpi" id="kpi_visits"></div>
      <div class="card kpi" id="kpi_revenue"></div>
      <div class="card kpi" id="kpi_avg"></div>
      <div class="card kpi" id="kpi_loyalty"></div>

      <div class="card half" id="daily_visits"></div>
      <div class="card half" id="daily_revenue"></div>
      <div class="card wide" id="weekday_trend"></div>
      <div class="card wide" id="sales_decomposition"></div>

      <div class="card" id="visits_store"></div>
      <div class="card" id="time_slot"></div>
      <div class="card" id="time_slot_kpi"></div>
      <div class="card" id="orders_per_visit"></div>
      <div class="card" id="items_per_order"></div>
      <div class="card half" id="store_benchmark"></div>
      <div class="card half" id="store_efficiency"></div>

      <div class="card" id="revenue_hist"></div>
      <div class="card" id="loyalty"></div>
      <div class="card" id="new_existing"></div>
      <div class="card" id="discount_usage"></div>
      <div class="card" id="discount_effect"></div>
      <div class="card" id="tax_rate"></div>
      <div class="card half" id="season_event"></div>
      <div class="card half" id="season_event_period"></div>
      <div class="card half" id="menu_sales_top"></div>
      <div class="card half" id="menu_abc"></div>
      <div class="card wide" id="stay_extra_order"></div>

      <div class="card wide" id="table"></div>
    </div>

    <script>
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

      function renderKpi(id, label, value) {
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
      }

      function minutesBetween(isoStart, isoEnd) {
        const start = Date.parse(isoStart || "");
        const end = Date.parse(isoEnd || "");
        if (!Number.isFinite(start) || !Number.isFinite(end) || end < start) return null;
        return Math.round((end - start) / 60000);
      }

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

          function filterByStore(rows, storeIdKey, selected) {
            if (selected === "ALL") return rows;
            return rows.filter(r => r[storeIdKey] === selected);
          }

          function renderAll(selectedStore) {
            const fVisits = filterByStore(visits, "store_id", selectedStore);
            const visitIds = new Set(fVisits.map(v => v["visit_id"]));
            const fOrders = orders.filter(o => visitIds.has(o["visit_id"]));
            const orderIds = new Set(fOrders.map(o => o["order_id"]));
            const fItems = items.filter(i => orderIds.has(i["order_id"]));
            const fReceipts = receipts.filter(r => visitIds.has(r["visit_id"]));

            const visitsByStore = counter(fVisits, "store_id");
            Plotly.newPlot("visits_store", [{
              type: "bar",
              x: Object.keys(visitsByStore),
              y: Object.values(visitsByStore)
            }], { title: "来店数（店舗別）" });

            const timeSlot = counter(fVisits, "time_slot");
            Plotly.newPlot("time_slot", [{
              type: "bar",
              x: Object.keys(timeSlot),
              y: Object.values(timeSlot)
            }], { title: "時間帯分布" });

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
            const slotAvgParty = slotKeys.map(k => {
              const cnt = visitCountByTimeSlot[k] || 0;
              return cnt ? Number(((partyByTimeSlot[k] || 0) / cnt).toFixed(2)) : 0;
            });
            Plotly.newPlot("time_slot_kpi", [
              {
                type: "bar",
                name: "売上",
                x: slotKeys,
                y: slotRevenue,
                yaxis: "y",
              },
              {
                type: "scatter",
                mode: "lines+markers",
                name: "客単価",
                x: slotKeys,
                y: slotAvgRevenue,
                yaxis: "y2",
              },
              {
                type: "scatter",
                mode: "lines+markers",
                name: "平均人数",
                x: slotKeys,
                y: slotAvgParty,
                yaxis: "y3",
              },
            ], {
              title: "時間帯別KPI（売上/客単価/平均人数）",
              yaxis: { title: "売上(円)" },
              yaxis2: { title: "客単価(円)", overlaying: "y", side: "right" },
              yaxis3: { title: "平均人数", overlaying: "y", side: "right", position: 0.95 },
              legend: { orientation: "h" },
            });

            const revenue = fReceipts.map(r => parseInt(r["total_yen"] || "0", 10));
            Plotly.newPlot("revenue_hist", [{
              type: "histogram",
              x: revenue,
              nbinsx: 20
            }], { title: "客単価分布" });

            const ordersPerVisit = counter(fOrders, "visit_id");
            Plotly.newPlot("orders_per_visit", [{
              type: "histogram",
              x: Object.values(ordersPerVisit),
              nbinsx: 10
            }], { title: "1来店あたり注文数" });

            const itemsPerOrder = counter(fItems, "order_id");
            Plotly.newPlot("items_per_order", [{
              type: "histogram",
              x: Object.values(itemsPerOrder),
              nbinsx: 10
            }], { title: "1注文あたり商品数" });

            const allVisitExtra = {};
            orders.forEach(o => {
              const vid = o["visit_id"];
              const seq = parseInt(o["order_seq_in_visit"] || "0", 10);
              if (!allVisitExtra[vid]) allVisitExtra[vid] = false;
              if (seq >= 2) allVisitExtra[vid] = true;
            });
            const storeAgg = {};
            storeIds.forEach(s => {
              storeAgg[s] = { visits: 0, revenue: 0, durationSum: 0, durationCnt: 0, extraVisits: 0 };
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
            const benchStores = [...storeIds].sort();
            const benchRevenue = benchStores.map(s => storeAgg[s] ? storeAgg[s].revenue : 0);
            const benchAvgTicket = benchStores.map((s, i) => {
              const visitsCnt = storeAgg[s] ? storeAgg[s].visits : 0;
              return visitsCnt ? Math.round((benchRevenue[i] || 0) / visitsCnt) : 0;
            });
            const benchAvgStay = benchStores.map(s => {
              const row = storeAgg[s];
              return row && row.durationCnt ? Number((row.durationSum / row.durationCnt).toFixed(1)) : 0;
            });
            const benchExtraRate = benchStores.map(s => {
              const row = storeAgg[s];
              return row && row.visits ? Number(((row.extraVisits / row.visits) * 100).toFixed(1)) : 0;
            });
            const benchColors = benchStores.map(s => (selectedStore !== "ALL" && s === selectedStore) ? "#0f1f2e" : "#6f8592");
            Plotly.newPlot("store_benchmark", [
              {
                type: "bar",
                name: "売上",
                x: benchStores,
                y: benchRevenue,
                marker: { color: benchColors },
                yaxis: "y",
              },
              {
                type: "scatter",
                mode: "lines+markers",
                name: "客単価",
                x: benchStores,
                y: benchAvgTicket,
                yaxis: "y2",
              },
            ], {
              title: "店舗別ベンチマーク（売上/客単価）",
              yaxis: { title: "売上(円)" },
              yaxis2: { title: "客単価(円)", overlaying: "y", side: "right" },
              legend: { orientation: "h" },
            });
            Plotly.newPlot("store_efficiency", [
              {
                type: "bar",
                name: "平均滞在時間",
                x: benchStores,
                y: benchAvgStay,
                marker: { color: benchColors },
                yaxis: "y",
              },
              {
                type: "scatter",
                mode: "lines+markers",
                name: "追加注文率",
                x: benchStores,
                y: benchExtraRate,
                yaxis: "y2",
              },
            ], {
              title: "店舗別運用効率（滞在時間/追加注文率）",
              yaxis: { title: "平均滞在時間(分)" },
              yaxis2: { title: "追加注文率(%)", overlaying: "y", side: "right", range: [0, 100] },
              legend: { orientation: "h" },
            });

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
              y: Object.values(discountUsage)
            }], { title: "割引利用回数" });

            const discountKeys = Object.keys(discountStats).sort((a, b) => discountStats[b].cnt - discountStats[a].cnt);
            const avgTotal = discountKeys.map(k => {
              const s = discountStats[k];
              return s.cnt ? Math.round(s.totalYen / s.cnt) : 0;
            });
            const avgDiscount = discountKeys.map(k => {
              const s = discountStats[k];
              return s.cnt ? Math.round(s.discountYen / s.cnt) : 0;
            });
            Plotly.newPlot("discount_effect", [
              {
                type: "bar",
                name: "平均会計額",
                x: discountKeys,
                y: avgTotal,
                yaxis: "y",
              },
              {
                type: "scatter",
                mode: "lines+markers",
                name: "平均値引額",
                x: discountKeys,
                y: avgDiscount,
                yaxis: "y2",
              },
            ], {
              title: "割引別の効果（平均会計額/平均値引額）",
              yaxis: { title: "平均会計額(円)" },
              yaxis2: {
                title: "平均値引額(円)",
                overlaying: "y",
                side: "right",
              },
            });

            const taxRate = counter(fReceipts, "tax_rate_applied");
            Plotly.newPlot("tax_rate", [{
              type: "bar",
              x: Object.keys(taxRate),
              y: Object.values(taxRate)
            }], { title: "税率適用分布" });

            const loyaltyYes = fReceipts.filter(r => r["customer_id"]).length;
            const loyaltyNo = fReceipts.length - loyaltyYes;
            Plotly.newPlot("loyalty", [{
              type: "pie",
              labels: ["提示あり", "提示なし"],
              values: [loyaltyYes, loyaltyNo]
            }], { title: "ロイヤルティ提示率" });

            const seg = {
              new_member: { cnt: 0, total: 0 },
              returning_member: { cnt: 0, total: 0 },
              guest: { cnt: 0, total: 0 },
            };
            fReceipts.forEach(r => {
              const v = visitById[r["visit_id"]];
              const cid = r["customer_id"];
              const total = parseInt(r["total_yen"] || "0", 10);
              if (!cid) {
                seg.guest.cnt += 1;
                seg.guest.total += total;
                return;
              }
              const visitDate = v ? (v["visit_date"] || "") : "";
              if (visitDate && customerFirstDate[cid] && visitDate === customerFirstDate[cid]) {
                seg.new_member.cnt += 1;
                seg.new_member.total += total;
              } else {
                seg.returning_member.cnt += 1;
                seg.returning_member.total += total;
              }
            });
            const segKeys = ["new_member", "returning_member", "guest"];
            const segLabels = ["新規会員(初回来店)", "既存会員", "非会員"];
            const segCounts = segKeys.map(k => seg[k].cnt);
            const segAvg = segKeys.map(k => seg[k].cnt ? Math.round(seg[k].total / seg[k].cnt) : 0);
            Plotly.newPlot("new_existing", [
              {
                type: "bar",
                name: "会計件数",
                x: segLabels,
                y: segCounts,
                yaxis: "y",
              },
              {
                type: "scatter",
                mode: "lines+markers",
                name: "平均会計額",
                x: segLabels,
                y: segAvg,
                yaxis: "y2",
              },
            ], {
              title: "新規/既存/非会員 比較",
              yaxis: { title: "会計件数" },
              yaxis2: { title: "平均会計額(円)", overlaying: "y", side: "right" },
            });

            const menuById = {};
            menu.forEach(m => { menuById[m["menu_item_id"]] = m; });
            const orderToVisit = {};
            fOrders.forEach(o => { orderToVisit[o["order_id"]] = o["visit_id"]; });
            const seasonEvent = {};
            const seasonalPeriod = {
              early: { seasonalRevenue: 0, totalRevenue: 0 },
              late: { seasonalRevenue: 0, totalRevenue: 0 },
            };
            const sortedDates = [...new Set(fVisits.map(v => v["visit_date"]).filter(Boolean))].sort();
            const pivotDate = sortedDates.length ? sortedDates[Math.floor(sortedDates.length / 2)] : "";
            fItems.forEach(i => {
              const m = menuById[i["menu_item_id"]];
              if (!m) return;
              const sales = parseInt(i["line_subtotal_yen"] || "0", 10);
              const tags = [];
              if (m["season"]) tags.push("季節:" + m["season"]);
              if (m["event"]) tags.push("イベント:" + m["event"]);
              if (tags.length === 0) tags.push("通常");
              tags.forEach(tag => {
                seasonEvent[tag] = (seasonEvent[tag] || 0) + sales;
              });
              const visitId = orderToVisit[i["order_id"]];
              const visit = visitId ? visitById[visitId] : null;
              const visitDate = visit ? (visit["visit_date"] || "") : "";
              const periodKey = (pivotDate && visitDate && visitDate < pivotDate) ? "early" : "late";
              seasonalPeriod[periodKey].totalRevenue += sales;
              if ((m["season"] || m["event"])) seasonalPeriod[periodKey].seasonalRevenue += sales;
            });
            const seasonEventRanked = Object.entries(seasonEvent).sort((a, b) => b[1] - a[1]).slice(0, 12);
            Plotly.newPlot("season_event", [{
              type: "bar",
              x: seasonEventRanked.map(e => e[0]),
              y: seasonEventRanked.map(e => e[1])
            }], { title: "季節/イベント別 売上寄与（上位）" });
            const periodLabels = ["前半", "後半"];
            const seasonalRevenueByPeriod = [
              seasonalPeriod.early.seasonalRevenue,
              seasonalPeriod.late.seasonalRevenue,
            ];
            const seasonalRatioByPeriod = [
              seasonalPeriod.early.totalRevenue ? Number(((seasonalPeriod.early.seasonalRevenue / seasonalPeriod.early.totalRevenue) * 100).toFixed(1)) : 0,
              seasonalPeriod.late.totalRevenue ? Number(((seasonalPeriod.late.seasonalRevenue / seasonalPeriod.late.totalRevenue) * 100).toFixed(1)) : 0,
            ];
            Plotly.newPlot("season_event_period", [
              {
                type: "bar",
                name: "季節/イベント売上",
                x: periodLabels,
                y: seasonalRevenueByPeriod,
                yaxis: "y",
              },
              {
                type: "scatter",
                mode: "lines+markers",
                name: "売上構成比",
                x: periodLabels,
                y: seasonalRatioByPeriod,
                yaxis: "y2",
              },
            ], {
              title: "季節/イベント売上の期間比較",
              yaxis: { title: "売上(円)" },
              yaxis2: { title: "構成比(%)", overlaying: "y", side: "right", range: [0, 100] },
              legend: { orientation: "h" },
            });

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
            }], {
              title: "商品別売上 Top10",
              xaxis: { title: "売上(円)" },
            });

            const totalMenuSales = menuRanked.reduce((acc, [, yen]) => acc + yen, 0);
            let cumulative = 0;
            const cumulativeRatio = menuRanked.map(([, yen]) => {
              cumulative += yen;
              return totalMenuSales ? (cumulative / totalMenuSales) * 100 : 0;
            });
            Plotly.newPlot("menu_abc", [
              {
                type: "bar",
                name: "売上",
                x: menuRanked.map(e => e[0]),
                y: menuRanked.map(e => e[1]),
                yaxis: "y",
              },
              {
                type: "scatter",
                mode: "lines+markers",
                name: "累積構成比",
                x: menuRanked.map(e => e[0]),
                y: cumulativeRatio,
                yaxis: "y2",
              },
            ], {
              title: "メニューABC分析（売上順）",
              yaxis: { title: "売上(円)" },
              yaxis2: {
                title: "累積構成比(%)",
                overlaying: "y",
                side: "right",
                range: [0, 100],
              },
            });

            const visitsByDate = {};
            fVisits.forEach(v => {
              if (!visitsByDate[v["visit_date"]]) visitsByDate[v["visit_date"]] = {};
              visitsByDate[v["visit_date"]][v["store_id"]] = (visitsByDate[v["visit_date"]][v["store_id"]] || 0) + 1;
            });
            const dates = Object.keys(visitsByDate).sort();
            const stores = selectedStore === "ALL" ? storeIds : [selectedStore];
            const traces = stores.map(s => ({
              type: "scatter",
              mode: "lines",
              name: "店舗 " + s,
              x: dates,
              y: dates.map(d => visitsByDate[d][s] || 0)
            }));
            Plotly.newPlot("daily_visits", traces, { title: "日別来店数（店舗別）" });

            const revenueByDate = {};
            fReceipts.forEach(r => {
              const d = (r["paid_at"] || "").slice(0,10);
              revenueByDate[d] = (revenueByDate[d] || 0) + parseInt(r["total_yen"] || "0", 10);
            });
            const revDates = Object.keys(revenueByDate).sort();
            Plotly.newPlot("daily_revenue", [{
              type: "scatter",
              mode: "lines",
              x: revDates,
              y: revDates.map(d => revenueByDate[d] || 0)
            }], { title: "日別売上" });

            const weekdayOrder = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
            const weekdayLabel = {
              Mon: "月",
              Tue: "火",
              Wed: "水",
              Thu: "木",
              Fri: "金",
              Sat: "土",
              Sun: "日",
            };
            const weekdayAgg = {};
            weekdayOrder.forEach(w => {
              weekdayAgg[w] = { visits: 0, revenue: 0 };
            });
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
            const presentWeekdays = weekdayOrder.filter(w => (weekdayAgg[w] && weekdayAgg[w].visits > 0));
            const weekdayX = presentWeekdays.map(w => weekdayLabel[w] || w);
            const weekdayVisits = presentWeekdays.map(w => weekdayAgg[w].visits);
            const weekdayRevenue = presentWeekdays.map(w => weekdayAgg[w].revenue);
            const weekdayAvg = presentWeekdays.map((w, i) => {
              const visits = weekdayVisits[i] || 0;
              return visits ? Math.round((weekdayRevenue[i] || 0) / visits) : 0;
            });
            Plotly.newPlot("weekday_trend", [
              {
                type: "bar",
                name: "来店数",
                x: weekdayX,
                y: weekdayVisits,
                yaxis: "y",
              },
              {
                type: "bar",
                name: "売上",
                x: weekdayX,
                y: weekdayRevenue,
                yaxis: "y2",
              },
              {
                type: "scatter",
                mode: "lines+markers",
                name: "客単価",
                x: weekdayX,
                y: weekdayAvg,
                yaxis: "y3",
              },
            ], {
              title: "曜日別トレンド（来店数/売上/客単価）",
              barmode: "group",
              yaxis: { title: "来店数" },
              yaxis2: { title: "売上(円)", overlaying: "y", side: "right" },
              yaxis3: { title: "客単価(円)", overlaying: "y", side: "right", position: 0.95 },
              legend: { orientation: "h" },
            });

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
              const visits = decompVisits[i] || 0;
              return visits ? Math.round((decompRevenue[i] || 0) / visits) : 0;
            });
            Plotly.newPlot("sales_decomposition", [
              {
                type: "bar",
                name: "売上",
                x: decompDates,
                y: decompRevenue,
                yaxis: "y",
              },
              {
                type: "scatter",
                mode: "lines+markers",
                name: "客数",
                x: decompDates,
                y: decompVisits,
                yaxis: "y2",
              },
              {
                type: "scatter",
                mode: "lines+markers",
                name: "客単価",
                x: decompDates,
                y: decompAvg,
                yaxis: "y3",
              },
            ], {
              title: "売上分解（日別）: 売上 = 客数 × 客単価",
              barmode: "group",
              legend: { orientation: "h" },
              yaxis: { title: "売上(円)" },
              yaxis2: {
                title: "客数",
                overlaying: "y",
                side: "right",
              },
              yaxis3: {
                title: "客単価(円)",
                overlaying: "y",
                side: "right",
                position: 0.95,
              },
            });

            const visitSummary = {};
            fVisits.forEach(v => {
              visitSummary[v["visit_id"]] = {
                duration: minutesBetween(v["seated_at"], v["left_at"]),
                extraOrdered: false,
                totalYen: 0,
              };
            });
            fOrders.forEach(o => {
              const key = o["visit_id"];
              if (!visitSummary[key]) return;
              const seq = parseInt(o["order_seq_in_visit"] || "0", 10);
              if (seq >= 2) visitSummary[key].extraOrdered = true;
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
            stayBins.forEach(b => {
              stayAgg[b.label] = { cnt: 0, extra: 0, total: 0 };
            });
            Object.values(visitSummary).forEach(v => {
              if (v.duration === null) return;
              const bin = stayBins.find(b => v.duration >= b.min && v.duration <= b.max);
              if (!bin) return;
              const row = stayAgg[bin.label];
              row.cnt += 1;
              row.total += v.totalYen;
              if (v.extraOrdered) row.extra += 1;
            });
            const stayLabels = stayBins.map(b => b.label);
            const stayExtraRate = stayLabels.map(label => {
              const row = stayAgg[label];
              return row.cnt ? Number(((row.extra / row.cnt) * 100).toFixed(1)) : 0;
            });
            const stayAvgYen = stayLabels.map(label => {
              const row = stayAgg[label];
              return row.cnt ? Math.round(row.total / row.cnt) : 0;
            });
            Plotly.newPlot("stay_extra_order", [
              {
                type: "bar",
                name: "平均会計額",
                x: stayLabels,
                y: stayAvgYen,
                yaxis: "y",
              },
              {
                type: "scatter",
                mode: "lines+markers",
                name: "追加注文率",
                x: stayLabels,
                y: stayExtraRate,
                yaxis: "y2",
              },
            ], {
              title: "滞在時間別の追加注文率と単価",
              yaxis: { title: "平均会計額(円)" },
              yaxis2: {
                title: "追加注文率(%)",
                overlaying: "y",
                side: "right",
                range: [0, 100],
              },
              legend: { orientation: "h" },
            });

            const sample = fReceipts.slice(0, 10);
            Plotly.newPlot("table", [{
              type: "table",
              header: { values: ["レシートID","来店ID","会計時刻","小計","割引額","税額","合計"] },
              cells: { values: [
                sample.map(r => r["receipt_id"]),
                sample.map(r => r["visit_id"]),
                sample.map(r => r["paid_at"]),
                sample.map(r => r["subtotal_yen"]),
                sample.map(r => r["discount_total_yen"]),
                sample.map(r => r["tax_yen"]),
                sample.map(r => r["total_yen"]),
              ] }
            }], { title: "レシート事例" });

            const totalVisits = fVisits.length;
            const totalRevenue = fReceipts.reduce((acc, r) => acc + parseInt(r["total_yen"] || "0", 10), 0);
            const avgRevenue = totalVisits ? Math.round(totalRevenue / totalVisits) : 0;
            const loyaltyRate = fReceipts.length ? Math.round((loyaltyYes / fReceipts.length) * 100) : 0;
            renderKpi("kpi_visits", "来店数", totalVisits.toLocaleString());
            renderKpi("kpi_revenue", "売上合計", "¥" + totalRevenue.toLocaleString());
            renderKpi("kpi_avg", "客単価", "¥" + avgRevenue.toLocaleString());
            renderKpi("kpi_loyalty", "ロイヤルティ提示率", loyaltyRate + "%");
          }

          storeSelect.onchange = () => renderAll(storeSelect.value);
          renderAll("ALL");
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
