# AGENTS.md

## 目的
ファミレスの擬似業務データを、追記型（append-only）のCSVとして日次で生成する。

## 重要制約
- 営業時間：開店 07:00、閉店 23:00（Asia/Tokyo）
- メニュー/割引/税率の変更は業務時間外（23:00-翌07:00）に決定し、翌営業日07:00から有効
- 生成は増分：既に生成済みの日付はスキップ（--force指定時のみ再生成）
- CSVヘッダは docs/02_CSVスキーマ.md の定義に厳密に一致させる

## 実行方法（目標）
- `uv run fami-synth generate --start YYYY-MM-DD --end YYYY-MM-DD --seed N --out-dir data/output [--force]`
- `uv run pytest -q`

## 実装方針
- src/fami_synth/ 配下を小さなモジュールに分割
- 同一入力（start/end/seed/config）で同一出力（再現性）
- 可能な限り標準ライブラリで実装

