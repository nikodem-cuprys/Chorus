from fastapi.testclient import TestClient

from chorus.app import create_app
from chorus.config import get_settings


def test_health():
    assert TestClient(create_app()).get("/api/health").json() == {"status": "ok"}


def test_dev_routes_are_off_unless_enabled(monkeypatch):
    monkeypatch.setattr(get_settings(), "dev", False)
    response = TestClient(create_app()).post("/api/dev/jobs", json={"queue": "gpu"})
    assert response.status_code in (404, 405)


def test_the_frontend_is_served_for_every_non_api_path(tmp_path, monkeypatch):
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("console.log(1)")
    (tmp_path / "index.html").write_text("<div id=root></div>")
    monkeypatch.setattr(get_settings(), "frontend_dist", tmp_path)
    client = TestClient(create_app())

    assert client.get("/").text == "<div id=root></div>"
    assert client.get("/works/12").text == "<div id=root></div>"
    assert client.get("/assets/app.js").text == "console.log(1)"
    assert client.get("/api/nothing").status_code == 404
