import functools
import sys
from typing import Any
from unittest.mock import create_autospec

import pytest

from starlette._utils import create_collapsing_task_group, get_route_path, is_async_callable, parse_host_header
from starlette.types import Scope

if sys.version_info < (3, 11):  # pragma: no cover
    from exceptiongroup import ExceptionGroup


def test_async_func() -> None:
    async def async_func() -> None: ...  # pragma: no cover

    def func() -> None: ...  # pragma: no cover

    assert is_async_callable(async_func)
    assert not is_async_callable(func)


def test_async_partial() -> None:
    async def async_func(a: Any, b: Any) -> None: ...  # pragma: no cover

    def func(a: Any, b: Any) -> None: ...  # pragma: no cover

    partial = functools.partial(async_func, 1)
    assert is_async_callable(partial)

    partial = functools.partial(func, 1)  # type: ignore
    assert not is_async_callable(partial)


def test_async_method() -> None:
    class Async:
        async def method(self) -> None: ...  # pragma: no cover

    class Sync:
        def method(self) -> None: ...  # pragma: no cover

    assert is_async_callable(Async().method)
    assert not is_async_callable(Sync().method)


def test_async_object_call() -> None:
    class Async:
        async def __call__(self) -> None: ...  # pragma: no cover

    class Sync:
        def __call__(self) -> None: ...  # pragma: no cover

    assert is_async_callable(Async())
    assert not is_async_callable(Sync())


def test_async_partial_object_call() -> None:
    class Async:
        async def __call__(
            self,
            a: Any,
            b: Any,
        ) -> None: ...  # pragma: no cover

    class Sync:
        def __call__(
            self,
            a: Any,
            b: Any,
        ) -> None: ...  # pragma: no cover

    partial = functools.partial(Async(), 1)
    assert is_async_callable(partial)

    partial = functools.partial(Sync(), 1)  # type: ignore
    assert not is_async_callable(partial)


def test_async_nested_partial() -> None:
    async def async_func(
        a: Any,
        b: Any,
    ) -> None: ...  # pragma: no cover

    partial = functools.partial(async_func, b=2)
    nested_partial = functools.partial(partial, a=1)
    assert is_async_callable(nested_partial)


def test_async_mocked_async_function() -> None:
    async def async_func() -> None: ...  # pragma: no cover

    mock = create_autospec(async_func)
    assert is_async_callable(mock)


@pytest.mark.parametrize(
    "scope, expected_result",
    [
        ({"path": "/foo-123/bar", "root_path": "/foo"}, "/foo-123/bar"),
        ({"path": "/foo/bar", "root_path": "/foo"}, "/bar"),
        ({"path": "/foo", "root_path": "/foo"}, ""),
        ({"path": "/foo/bar", "root_path": "/bar"}, "/foo/bar"),
    ],
)
def test_get_route_path(scope: Scope, expected_result: str) -> None:
    assert get_route_path(scope) == expected_result


@pytest.mark.parametrize(
    "host_header, expected",
    [
        ("example.com", "example.com"),
        ("example.com:8000", "example.com"),
        ("example.com:0", "example.com"),
        ("example.com:65535", "example.com"),
        ("api_service", "api_service"),
        ("[::1]", "[::1]"),
        ("[::1]:8000", "[::1]"),
        ("[2001:DB8::1]", "[2001:DB8::1]"),
        ("[::ffff:1.2.3.4]", "[::ffff:1.2.3.4]"),
        # Ports out of the 0-65535 range are invalid.
        ("example.com:65536", None),
        ("example.com:99999", None),
        ("[::1]:99999", None),
        # Ports must be decimal digits.
        ("example.com:abc", None),
        ("example.com:", None),
        ("example.com:-1", None),
        ("example.com:80:90", None),
        # Bracketed hosts must be valid IPv6 addresses.
        ("[fe80::1::2]", None),
        ("[1.2.3.4]", None),
        ("[]", None),
        ("[::1", None),
        ("::1]", None),
        ("[::1]evil.example.com", None),
        # Bare IPv6 addresses and empty headers are invalid.
        ("::1", None),
        ("", None),
    ],
)
def test_parse_host_header(host_header: str, expected: str | None) -> None:
    assert parse_host_header(host_header) == expected


@pytest.mark.anyio
async def test_collapsing_task_group_one_exc() -> None:
    class MyException(Exception):
        pass

    with pytest.raises(MyException):
        async with create_collapsing_task_group():
            raise MyException


@pytest.mark.anyio
async def test_collapsing_task_group_two_exc() -> None:
    class MyException(Exception):
        pass

    async def raise_exc() -> None:
        raise MyException

    with pytest.raises(ExceptionGroup) as exc:
        async with create_collapsing_task_group() as task_group:
            task_group.start_soon(raise_exc)
            raise MyException

    exc1, exc2 = exc.value.exceptions
    assert isinstance(exc1, MyException)
    assert isinstance(exc2, MyException)
