from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
from munch import DefaultMunch

from gherila import GitHub
from gherila.api import create_app
from gherila.exceptions import RateLimitError


def test_api_auth_models_openapi_and_cleanup(github_user):
    github = GitHub()
    github.session.request = AsyncMock(return_value=DefaultMunch.fromDict(github_user))
    app = create_app(clients={"github": github}, api_key="test-key")
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/v1/github/get_user", params={"username": "example"}).status_code == 401
        response = client.get(
            "/v1/github/get_user", params={"username": "example"}, headers={"X-API-Key": "test-key"}
        )
        assert response.status_code == 200
        assert response.json()["id"] == "9007199254740993"
        assert response.json()["name"] is None
        assert (
            client.get(
                "/v1/github/get_repos",
                params={"username": "example", "limit": 501},
                headers={"X-API-Key": "test-key"},
            ).status_code
            == 422
        )
        assert (
            client.get(
                "/v1/instagram/get_user",
                params={"username": "example"},
                headers={"X-API-Key": "test-key"},
            ).status_code
            == 503
        )
        schema = client.get("/openapi.json").json()
        assert len(schema["paths"]) == 28
        assert "download_video" not in str(schema["paths"])
        assert schema["components"]["schemas"]["GitHubUser"]["properties"]["id"]["type"] == "string"
    assert github._closed


def test_api_upstream_error_does_not_expose_response():
    github = GitHub()
    github.session.request = AsyncMock(
        side_effect=RateLimitError("private secret", status=429, retry_after=12.5)
    )
    with TestClient(create_app(clients={"github": github})) as client:
        response = client.get("/v1/github/get_user", params={"username": "example"})
        assert response.status_code == 429
        assert response.headers["retry-after"] == "13"
        assert "secret" not in response.text


def test_api_defaults_bound_collection_size():
    github = GitHub()
    github.get_repos = AsyncMock(return_value=[])
    with TestClient(create_app(clients={"github": github})) as client:
        assert client.get("/v1/github/get_repos", params={"username": "example"}).status_code == 200
        github.get_repos.assert_awaited_once_with(username="example", limit=50)
