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

      <div class="card" id="visits_store"></div>
      <div class="card" id="time_slot"></div>
      <div class="card" id="orders_per_visit"></div>
      <div class="card" id="items_per_order"></div>

      <div class="card" id="revenue_hist"></div>
      <div class="card" id="discount_usage"></div>
      <div class="card" id="tax_rate"></div>
      <div class="card" id="season_event"></div>

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

            const discountUsage = {};
            fReceipts.forEach(r => {
              (r["applied_discount_ids"] || "").split("|").filter(Boolean).forEach(d => {
                discountUsage[d] = (discountUsage[d] || 0) + 1;
              });
            });
            Plotly.newPlot("discount_usage", [{
              type: "bar",
              x: Object.keys(discountUsage),
              y: Object.values(discountUsage)
            }], { title: "割引利用回数" });

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

            const menuById = {};
            menu.forEach(m => { menuById[m["menu_item_id"]] = m; });
            const seasonEvent = {};
            fItems.forEach(i => {
              const m = menuById[i["menu_item_id"]];
              if (!m) return;
              if (m["season"]) seasonEvent["季節:" + m["season"]] = (seasonEvent["季節:" + m["season"]] || 0) + parseInt(i["qty"] || "1", 10);
              if (m["event"]) seasonEvent["イベント:" + m["event"]] = (seasonEvent["イベント:" + m["event"]] || 0) + parseInt(i["qty"] || "1", 10);
            });
            Plotly.newPlot("season_event", [{
              type: "bar",
              x: Object.keys(seasonEvent),
              y: Object.values(seasonEvent)
            }], { title: "季節/イベントメニュー比率" });

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
            document.getElementById("kpi_visits").innerHTML = "<div class=\"label\">来店数</div><div class=\"value\">" + totalVisits.toLocaleString() + "</div>";
            document.getElementById("kpi_revenue").innerHTML = "<div class=\"label\">売上合計</div><div class=\"value\">¥" + totalRevenue.toLocaleString() + "</div>";
            document.getElementById("kpi_avg").innerHTML = "<div class=\"label\">客単価</div><div class=\"value\">¥" + avgRevenue.toLocaleString() + "</div>";
            document.getElementById("kpi_loyalty").innerHTML = "<div class=\"label\">ロイヤルティ提示率</div><div class=\"value\">" + loyaltyRate + "%</div>";
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
