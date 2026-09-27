from __future__ import annotations

import pytest

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Host, Route, Router
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
        ("[::1]:99999", 400),
        ("[2001:db8::1]", 400),
        ("[fe80::1::2]", 400),
        ("[::1", 400),
        ("[::1]evil.example.com", 400),
        ("[::1]@attacker", 400),
        ("[::1].", 400),
        ("[::1]:evil", 400),
        ("[::1]:", 400),
        ("api_service", 200),
        ("api_service:8000", 200),
        ("api_service:65535", 200),
        ("api_service:99999", 400),
        ("api_service/evil", 400),
        ("api_service?evil", 400),
        ("api_service#evil", 400),
        ("api_service@attacker", 400),
        ("api service", 400),
        ("api.example.com:8443", 200),
        ("api.example.com:99999", 400),
        ("api.example.com:abc", 400),
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


@pytest.mark.parametrize("host", ["api.example.com:abc", "api.example.com:99999", "[fe80::1::2]"])
def test_trusted_host_middleware_and_host_routing_agree(test_client_factory: TestClientFactory, host: str) -> None:
    """A Host header rejected by the middleware must not match any `Host` route either."""

    def api_endpoint(request: Request) -> PlainTextResponse:
        return PlainTextResponse("API")

    api_app = Router([Route("/", endpoint=api_endpoint)])
    app = Starlette(
        routes=[Host("api.example.com", app=api_app)],
        middleware=[Middleware(TrustedHostMiddleware, allowed_hosts=["api.example.com"])],
    )

    client = test_client_factory(app)
    response = client.get("/", headers={"host": host})
    assert response.status_code == 400
    assert response.text == "Invalid host header"
