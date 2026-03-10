from __future__ import annotations

from starlette.testclient import TestClient

from remora_ui.app import create_app
from remora_ui.config import RemoraUIConfig


def test_index_injects_remora_base_url() -> None:
    app = create_app(RemoraUIConfig(remora_base_url="http://example-remora:9999"))

    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "window.REMORA_BASE_URL = \"http://example-remora:9999\";" in response.text


def test_config_json_endpoint() -> None:
    app = create_app(RemoraUIConfig(remora_base_url="http://localhost:8765"))

    with TestClient(app) as client:
        response = client.get("/config.json")

    assert response.status_code == 200
    assert response.json() == {"remora_base_url": "http://localhost:8765"}


def test_static_assets_are_served() -> None:
    app = create_app()

    with TestClient(app) as client:
        html_response = client.get("/static/index.html")
        js_response = client.get("/static/main.js")
        css_response = client.get("/static/style.css")

    assert html_response.status_code == 200
    assert "<title>Remora Swarm View</title>" in html_response.text
    assert js_response.status_code == 200
    assert "function initCytoscape()" in js_response.text
    assert css_response.status_code == 200
    assert "#cy" in css_response.text
