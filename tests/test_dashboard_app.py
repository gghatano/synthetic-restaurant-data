from datetime import date

from fastapi.testclient import TestClient

from dashboard.app import create_app
from fami_synth.cli import GenerateParams, generate


def test_dashboard_app_serves_index_and_csv(tmp_path):
    params = GenerateParams(
        start=date(2026, 2, 10),
        end=date(2026, 2, 11),
        seed=21,
        out_dir=tmp_path,
        force=False,
    )
    generate(params)

    app = create_app(tmp_path)
    client = TestClient(app)

    res = client.get("/")
    assert res.status_code == 200
    assert "ファミシン セールスダッシュボード" in res.text

    res = client.get("/data/visit.csv")
    assert res.status_code == 200
    assert "visit_id" in res.text
