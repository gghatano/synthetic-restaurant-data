## fami-synth

Family restaurant synthetic data generator.

### Usage
```bash
uv run fami-synth generate --start 2026-02-10 --end 2026-02-12 --seed 42 --out-dir data/output
```

### Overrides (CLI)
```bash
uv run fami-synth generate \
  --start 2026-02-10 --end 2026-02-12 --seed 42 --out-dir data/output \
  --table-count 20 --visit-range 6,12 --order-range 1,2 --item-range 1,3 \
  --stay-range 30,90 --cook-range 240,900
```

### Dashboard
```bash
uv run fami-synth dashboard --data-dir data/output --host 127.0.0.1 --port 8000
```

### Quick Steps
1. Generate data.
2. Build dashboard.
3. Run tests.

Details: see `docs/06_運用ガイド.md`.

### Standard Run Rules
- Output directory: `data/output` (single source of truth).
- Date range: pass an inclusive start and exclusive end.
- Seed: keep fixed for reproducibility unless you intend to vary distributions.

### Default Generation Parameters
- `table_count`: 30
- `visit_count_range`: 8-16 per store/day
- `order_count_range`: 1-3 per visit
- `item_count_range`: 1-4 per order
- `stay_minutes_range`: 35-120 minutes
- `cook_time_seconds_range`: 240-1200 seconds

### Tests
```bash
uv run pytest -q
```
