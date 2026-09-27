from __future__ import annotations

import pytest

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from tests.types import TestClientFactory


def test_trusted_host_middleware(test_client_factory: TestClientFactory) -> None:
    def homepage(request: Request) -> PlainTextResponse:
        return PlainTextResponse("OK", status_code=200)

    app = Starlette(
        routes=[Route("/", endpoint=homepage)],
        middleware=[Middleware(TrustedHostMiddleware, allowed_hosts=["testserver", "*.testserver"])],
    )

    client = test_client_factory(app)
    response = client.get("/")
    assert response.status_code == 200

    client = test_client_factory(app, base_url="http://subdomain.testserver")
    response = client.get("/")
    assert response.status_code == 200

    client = test_client_factory(app, base_url="http://invalidhost")
    response = client.get("/")
    assert response.status_code == 400


@pytest.mark.parametrize(
    ("host", "status_code"),
    [
        ("[::1]", 200),
        ("[::1]:8000", 200),
        ("[2001:db8::1]", 400),
        ("[::1", 400),
        ("[::1]evil.example.com", 400),
        ("[::1]@attacker", 400),
        ("[::1].", 400),
        ("[::1]:evil", 400),
        ("[::1]:", 400),
        ("[::1]:99999", 400),
        ("[fe80::1::2]", 400),
        ("[1.2.3.4]", 400),
        ("api_service", 200),
        ("api_service:8000", 200),
        ("api_service:65535", 200),
        ("api_service:65536", 400),
        ("api_service:99999", 400),
        ("api_service:abc", 400),
        ("api_service/evil", 400),
        ("api_service?evil", 400),
        ("api_service#evil", 400),
        ("api_service@attacker", 400),
        ("api service", 400),
    ],
)
def test_trusted_host_middleware_ipv6(test_client_factory: TestClientFactory, host: str, status_code: int) -> None:
    def homepage(request: Request) -> PlainTextResponse:
        return PlainTextResponse("OK")

    app = Starlette(
        routes=[Route("/", endpoint=homepage)],
        middleware=[Middleware(TrustedHostMiddleware, allowed_hosts=["[::1]", "api_service", "*.example.com"])],
    )

    client = test_client_factory(app)
    response = client.get("/", headers={"host": host})
    assert response.status_code == status_code


def test_default_allowed_hosts() -> None:
    app = Starlette()
    middleware = TrustedHostMiddleware(app)
    assert middleware.allowed_hosts == ["*"]


@pytest.mark.parametrize(
    "host",
    [
        pytest.param("example.com:99999", id="port-out-of-range"),
        pytest.param("example.com:abc", id="non-numeric-port"),
        pytest.param("[fe80::1::2]", id="malformed-ipv6"),
    ],
)
def test_invalid_host_header_does_not_break_url(test_client_factory: TestClientFactory, host: str) -> None:
    """An invalid Host header must not cause a 500 downstream.

    With a permissive `allowed_hosts` the middleware lets the request through,
    and URL construction falls back to the server address.
    """

    def homepage(request: Request) -> PlainTextResponse:
        return PlainTextResponse(str(request.url))

    app = Starlette(
        routes=[Route("/", endpoint=homepage)],
        middleware=[Middleware(TrustedHostMiddleware, allowed_hosts=["*"])],
    )

    client = test_client_factory(app)
    response = client.get("/", headers={"host": host})
    assert response.status_code == 200
    assert response.text == "http://testserver/"


def test_www_redirect(test_client_factory: TestClientFactory) -> None:
    def homepage(request: Request) -> PlainTextResponse:
        return PlainTextResponse("OK", status_code=200)

    app = Starlette(
        routes=[Route("/", endpoint=homepage)],
        middleware=[Middleware(TrustedHostMiddleware, allowed_hosts=["www.example.com"])],
    )

    client = test_client_factory(app, base_url="https://example.com")
    response = client.get("/")
    assert response.status_code == 200
    assert response.url == "https://www.example.com/"
