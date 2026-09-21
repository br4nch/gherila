import asyncio

import pytest
from aiohttp import ClientSession, web

from gherila.exceptions import (
    AuthenticationError,
    HTTPError,
    ParseError,
    RateLimitError,
    ResponseTooLargeError,
    TransportError,
)
from gherila.http import State, retry_after_seconds


async def test_pool_reuse_and_formats(server):
    transports = []

    async def handler(request):
        transports.append(request.transport)
        if request.path == "/binary":
            return web.Response(body=b"\x00\xff", content_type="application/octet-stream")
        if request.path == "/unknown":
            return web.Response(body=b"raw", content_type="application/custom")
        if request.path == "/text":
            return web.Response(text="hello")
        return web.Response(text='{"answer": 42}', content_type="application/problem+json")

    state = State()
    async with server(handler) as url:
        try:
            assert (await state.request("GET", url)).answer == 42
            assert await state.request("GET", url + "/binary") == b"\x00\xff"
            assert await state.request("GET", url + "/unknown") == b"raw"
            assert await state.request("GET", url + "/text") == "hello"
            assert all(transport is transports[0] for transport in transports)
        finally:
            await state.close()
    assert state._session.closed


async def test_borrowed_session_is_not_closed(server):
    async def handler(request):
        return web.json_response({})

    async with server(handler) as url, ClientSession() as session:
        state = State(session=session)
        await state.request("GET", url)
        await state.close()
        assert not session.closed
        with pytest.raises(RuntimeError):
            await state.request("GET", url)


@pytest.mark.parametrize(
    "status,error,count",
    [(503, HTTPError, 3), (401, AuthenticationError, 1), (429, RateLimitError, 3)],
)
async def test_status_retries(server, status, error, count):
    attempts = 0

    async def handler(request):
        nonlocal attempts
        attempts += 1
        return web.Response(status=status, headers={"Retry-After": "0"}, text="secret response")

    state = State(retries=2, max_retry_delay=0)
    async with server(handler) as url:
        try:
            with pytest.raises(error) as caught:
                await state.request("GET", url)
            assert caught.value.status == status
            assert "secret" not in str(caught.value)
            assert attempts == count
        finally:
            await state.close()


async def test_long_retry_after_and_post_are_not_retried(server):
    calls = []

    async def handler(request):
        calls.append(request.method)
        return web.Response(status=429, headers={"Retry-After": "3600"})

    state = State()
    async with server(handler) as url:
        try:
            for method in ["GET", "POST"]:
                with pytest.raises(RateLimitError) as error:
                    await state.request(method, url)
                assert error.value.retry_after == 3600
            assert calls == ["GET", "POST"]
        finally:
            await state.close()


async def test_size_limit_and_bad_json(server):
    async def handler(request):
        return web.Response(body=b"not json" if request.path == "/bad" else b"x" * 100)

    state = State(max_response_bytes=16)
    async with server(handler) as url:
        try:
            with pytest.raises(ResponseTooLargeError):
                await state.request("GET", url)
            with pytest.raises(ParseError):
                await state.request("GET", url + "/bad", response_type="json")
        finally:
            await state.close()


async def test_download_atomic_cleanup_and_memory_limit(server, tmp_path):
    async def handler(request):
        return web.Response(body=b"x" * 100)

    path = tmp_path / "video.bin"
    path.write_bytes(b"original")
    state = State(max_response_bytes=50, max_download_bytes=50)
    async with server(handler) as url:
        try:
            with pytest.raises(ResponseTooLargeError):
                await state.download(url, path)
            assert path.read_bytes() == b"original"
            assert not list(tmp_path.glob("*.part"))
            with pytest.raises(ResponseTooLargeError):
                await state.download(url)
            state.max_download_bytes = 200
            assert await state.download(url, path) == path
            assert path.read_bytes() == b"x" * 100
        finally:
            await state.close()


async def test_timeout(server):
    async def handler(request):
        await asyncio.sleep(0.05)
        return web.Response()

    state = State(timeout=0.01, retries=0)
    async with server(handler) as url:
        try:
            with pytest.raises(TransportError):
                await state.request("GET", url)
        finally:
            await state.close()


async def test_same_origin_redirect(server):
    async def handler(request):
        if request.path == "/start":
            raise web.HTTPFound("/finish")
        return web.json_response({"ok": True})

    state = State()
    async with server(handler) as url:
        try:
            assert (await state.request("GET", url + "/start")).ok
        finally:
            await state.close()


@pytest.mark.parametrize(
    "value,expected",
    [
        ("12", 12),
        ("-1", 0),
        ("bad", None),
        ("nan", None),
        ("inf", None),
        (None, None),
        ("Wed, 21 Oct 2015 07:28:00 GMT", 0),
    ],
)
def test_retry_after(value, expected):
    assert retry_after_seconds(value) == expected


async def test_cross_origin_redirect_strips_credentials_and_blocks_unknown_hosts():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock

    first = SimpleNamespace(
        status=302, headers={"Location": "https://b.example/page"}, release=Mock()
    )
    final = SimpleNamespace(status=200)
    session = SimpleNamespace(
        closed=False, headers={}, auth=None, request=AsyncMock(side_effect=[first, final])
    )
    state = State(session=session)
    assert (
        await state._follow(
            "GET",
            "https://a.example/page",
            {"a.example", "b.example"},
            {
                "headers": {
                    "Cookie": "secret",
                    "Authorization": "secret",
                    "X-Csrf-Token": "secret",
                    "User-Agent": "test",
                }
            },
        )
        is final
    )
    assert session.request.call_args.kwargs["headers"] == {"User-Agent": "test"}
    first.headers["Location"] = "https://evil.example/page"
    session.request = AsyncMock(return_value=first)
    with pytest.raises(ValueError):
        await state._follow("GET", "https://a.example/page", {"a.example", "b.example"}, {})
    assert session.request.await_count == 1


async def test_download_cancellation_cleans_partial_file(server, tmp_path):
    started = asyncio.Event()
    release = asyncio.Event()

    async def handler(request):
        response = web.StreamResponse()
        await response.prepare(request)
        await response.write(b"chunk")
        started.set()
        await release.wait()
        return response

    state = State()
    destination = tmp_path / "file.bin"
    async with server(handler) as url:
        task = asyncio.create_task(state.download(url, destination))
        try:
            await started.wait()
            # Let the client consume the first chunk and wait for the next one.
            for _ in range(100):
                if list(tmp_path.glob("*.part")):
                    break
                await asyncio.sleep(0.001)
            assert list(tmp_path.glob("*.part"))
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert not list(tmp_path.iterdir())
        finally:
            release.set()
            await state.close()
