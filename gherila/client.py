import asyncio
from functools import wraps

from pydantic import ValidationError

from .cache import TTLCache
from .exceptions import ParseError
from .http import State


class Client:
    """Clients are reusable within one event loop. Close them when finished."""

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        for name, method in list(cls.__dict__.items()):
            if not name.startswith("_") and asyncio.iscoroutinefunction(method):
                setattr(cls, name, _normalize_errors(method))

    def __init__(self, *, cache_size=256, cache_ttl=300, **transport_options):
        self.session = State(**transport_options)
        self._user_cache = TTLCache(cache_size, cache_ttl)
        self._inflight = {}
        self._closed = False

    def _check_open(self):
        if self._closed:
            raise RuntimeError("This client is closed; create a new client")

    async def __aenter__(self):
        self._check_open()
        return self

    async def __aexit__(self, *exc):
        await self.close()

    async def close(self):
        self._closed = True
        tasks = list(self._inflight.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._inflight.clear()
        self._user_cache.clear()
        await self.session.close()


def _normalize_errors(method):
    @wraps(method)
    async def wrapped(self, *args, **kwargs):
        self._check_open()
        try:
            return await method(self, *args, **kwargs)
        except (ValidationError, KeyError, IndexError, AttributeError) as exc:
            raise ParseError("Upstream response does not match the expected model") from exc

    return wrapped
