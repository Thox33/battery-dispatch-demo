import re
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from battery_dispatch.communication.http.server import FRONTEND_DIR, create_app
from battery_dispatch.config.config_manager import AppConfig
from battery_dispatch.core.controller import Controller
from tests.fakes import FakeComponent


JAVASCRIPT_TYPES = ("text/javascript", "application/javascript")


@pytest.fixture
def client() -> Generator[TestClient]:
    controller = Controller(AppConfig())
    controller.components = [FakeComponent("storage")]
    with TestClient(create_app(controller)) as test_client:
        yield test_client


def test_root_redirects_to_page(client: TestClient) -> None:
    response = client.get("/", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/ui/"


def test_page_without_trailing_slash_redirects(client: TestClient) -> None:
    response = client.get("/ui", follow_redirects=False)

    assert response.status_code in (307, 308)
    assert response.headers["location"].endswith("/ui/")


def test_page_is_served(client: TestClient) -> None:
    response = client.get("/ui/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<title>Battery dispatch</title>" in response.text
    assert 'src="app.js"' in response.text


@pytest.mark.parametrize(
    ("path", "content_types"),
    [
        pytest.param("/ui/app.js", JAVASCRIPT_TYPES, id="app.js"),
        pytest.param("/ui/style.css", ("text/css",), id="style.css"),
        pytest.param("/ui/vendor/uPlot.iife.min.js", JAVASCRIPT_TYPES, id="uPlot js"),
        pytest.param("/ui/vendor/uPlot.min.css", ("text/css",), id="uPlot css"),
    ],
)
def test_assets_are_served_with_content_type(
    client: TestClient, path: str, content_types: tuple[str, ...]
) -> None:
    response = client.get(path)

    assert response.status_code == 200
    assert response.headers["content-type"].split(";")[0] in content_types


def test_library_licence_is_served(client: TestClient) -> None:
    response = client.get("/ui/vendor/LICENSE")

    assert response.status_code == 200
    assert "MIT License" in response.text


def test_page_loads_only_local_files(client: TestClient) -> None:
    html = client.get("/ui/").text
    references = re.findall(r'<(?:script|link)\b[^>]*\b(?:src|href)="([^"]+)"', html)

    assert references, "the page references no scripts or stylesheets"
    for reference in references:
        assert not re.match(r"^(?:[a-z]+:)?//", reference), reference
        assert client.get(f"/ui/{reference}").status_code == 200, reference


def test_unknown_file_returns_404(client: TestClient) -> None:
    assert client.get("/ui/missing.js").status_code == 404


def test_api_and_docs_are_unchanged(client: TestClient) -> None:
    assert client.get("/health").status_code == 200
    assert client.get("/docs").status_code == 200
    paths = client.get("/openapi.json").json()["paths"]
    assert "/health" in paths
    assert "/dispatch/optimize" in paths
    assert "/" not in paths


def test_frontend_directory_is_part_of_the_package() -> None:
    for name in ("index.html", "app.js", "style.css", "vendor/uPlot.iife.min.js"):
        assert (FRONTEND_DIR / name).is_file(), name
