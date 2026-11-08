"""HTTP layer for results (needs Django: run with pytest)."""
import pytest

from .results_helpers import SLUG, build_processed


@pytest.fixture
def data_dir(tmp_path, settings):
    settings.RANGDRISHTI_DATA_DIR = tmp_path
    return tmp_path


def test_shows_endpoint(client, data_dir):
    build_processed(data_dir)
    body = client.get("/api/shows/").json()
    assert body["status"] == "ok"
    assert body["data"]["shows"][0]["slug"] == SLUG


def test_promos_endpoint(client, data_dir):
    build_processed(data_dir)
    data = client.get(f"/api/shows/{SLUG}/promos/").json()["data"]
    assert data["promos"] and data["run"]["is_mock"] is True


def test_clip_endpoint(client, data_dir):
    build_processed(data_dir)
    first = client.get(f"/api/shows/{SLUG}/promos/").json()["data"]["promos"][0]["id"]
    body = client.get(f"/api/shows/{SLUG}/promos/{first}/").json()
    assert body["data"]["lines"]


def test_csv_download(client, data_dir):
    build_processed(data_dir)
    response = client.get(f"/api/shows/{SLUG}/promos.csv")
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
    assert "attachment" in response["Content-Disposition"]


def test_errors_use_the_envelope(client, data_dir):
    build_processed(data_dir, judged=False)
    not_judged = client.get(f"/api/shows/{SLUG}/promos/")
    assert not_judged.status_code == 404 and not_judged.json()["error"]["code"] == "not_judged"
    bad = client.get("/api/shows/BAD_SLUG/promos/")
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "invalid_slug"
