import pytest

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from tests.types import TestClientFactory


def test_https_redirect_middleware(test_client_factory: TestClientFactory) -> None:
    def homepage(request: Request) -> PlainTextResponse:
        return PlainTextResponse("OK", status_code=200)

    app = Starlette(
        routes=[Route("/", endpoint=homepage)],
        middleware=[Middleware(HTTPSRedirectMiddleware)],
    )

    client = test_client_factory(app, base_url="https://testserver")
    response = client.get("/")
    assert response.status_code == 200

    client = test_client_factory(app)
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "https://testserver/"

    client = test_client_factory(app, base_url="http://testserver:80")
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "https://testserver/"

    client = test_client_factory(app, base_url="http://testserver:443")
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "https://testserver/"

    client = test_client_factory(app, base_url="http://testserver:123")
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "https://testserver:123/"


@pytest.mark.parametrize(
    "host",
    [
        pytest.param("testserver:99999", id="port-out-of-range"),
        pytest.param("testserver:abc", id="non-numeric-port"),
        pytest.param("[fe80::1::2]", id="malformed-ipv6"),
    ],
)
def test_https_redirect_middleware_with_invalid_host(test_client_factory: TestClientFactory, host: str) -> None:
    """An invalid Host header must not cause a 500.

    The header is ignored and the redirect is built from the server address.
    """

    def homepage(request: Request) -> PlainTextResponse:
        return PlainTextResponse("OK", status_code=200)

    app = Starlette(
        routes=[Route("/", endpoint=homepage)],
        middleware=[Middleware(HTTPSRedirectMiddleware)],
    )

    client = test_client_factory(app)
    response = client.get("/", headers={"host": host}, follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "https://testserver/"


@pytest.mark.parametrize(
    "base_url, host, expected_location",
    [
        pytest.param("http://[::1]", None, "https://[::1]/", id="ipv6-default-port"),
        pytest.param("http://[::1]:8080", None, "https://[::1]:8080/", id="ipv6-non-default-port"),
        pytest.param("http://[::1]", "[::1]:80", "https://[::1]/", id="ipv6-explicit-port-80"),
        pytest.param("http://[::1]", "[::1]:443", "https://[::1]/", id="ipv6-explicit-port-443"),
    ],
)
def test_https_redirect_middleware_with_ipv6(
    test_client_factory: TestClientFactory, base_url: str, host: str | None, expected_location: str
) -> None:
    """Redirects must keep IPv6 addresses usable, brackets included."""

    def homepage(request: Request) -> PlainTextResponse:
        return PlainTextResponse("OK", status_code=200)

    app = Starlette(
        routes=[Route("/", endpoint=homepage)],
        middleware=[Middleware(HTTPSRedirectMiddleware)],
    )

    client = test_client_factory(app, base_url=base_url)
    headers = {"host": host} if host is not None else {}
    response = client.get("/", headers=headers, follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == expected_location
