from datetime import date

from fami_synth.cli import GenerateParams, generate


def _run(out_dir, force: bool):
    params = GenerateParams(
        start=date(2026, 2, 10),
        end=date(2026, 2, 12),
        seed=7,
        out_dir=out_dir,
        force=force,
    )
    generate(params)


def test_incremental_skip(tmp_path):
    _run(tmp_path, force=False)
    before = {p.name: p.read_text(encoding="utf-8") for p in tmp_path.iterdir()}

    _run(tmp_path, force=False)
    after = {p.name: p.read_text(encoding="utf-8") for p in tmp_path.iterdir()}

    assert before == after
