from datetime import date

from fami_synth.cli import GenerateParams, generate


def _generate_to(tmp_path, seed: int):
    params = GenerateParams(
        start=date(2026, 2, 10),
        end=date(2026, 2, 13),
        seed=seed,
        out_dir=tmp_path,
        force=False,
    )
    generate(params)


def test_determinism(tmp_path):
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    dir_a.mkdir()
    dir_b.mkdir()

    _generate_to(dir_a, 123)
    _generate_to(dir_b, 123)

    for file_a in dir_a.iterdir():
        file_b = dir_b / file_a.name
        assert file_b.exists()
        assert file_a.read_text(encoding="utf-8") == file_b.read_text(
            encoding="utf-8"
        )
