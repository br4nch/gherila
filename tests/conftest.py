from contextlib import asynccontextmanager

import pytest
from aiohttp import web


@pytest.fixture
def server():
    @asynccontextmanager
    async def start(handler):
        app = web.Application()
        app.router.add_route("*", "/{path:.*}", handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        try:
            yield f"http://127.0.0.1:{runner.addresses[0][1]}"
        finally:
            await runner.cleanup()

    return start


@pytest.fixture
def github_user():
    return dict(
        id=9007199254740993,
        login="example",
        avatar_url="https://example.com/avatar",
        url="https://api.github.com/users/example",
        name=None,
        type="User",
        public_repos=0,
        followers=0,
        following=0,
        created_at="2025-01-01T00:00:00Z",
    )
