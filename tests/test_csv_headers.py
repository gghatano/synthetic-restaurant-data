from datetime import date

from fami_synth.cli import GenerateParams, generate
from fami_synth.io_csv import HEADERS


def test_csv_headers(tmp_path):
    params = GenerateParams(
        start=date(2026, 2, 10),
        end=date(2026, 2, 11),
        seed=42,
        out_dir=tmp_path,
        force=False,
    )
    generate(params)

    for filename, header in HEADERS.items():
        path = tmp_path / filename
        assert path.exists()
        first_line = path.read_text(encoding="utf-8").splitlines()[0]
        assert first_line == ",".join(header)
