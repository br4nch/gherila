"""Bounded per-client cache and cancellation-safe request coalescing."""

import asyncio
from collections import OrderedDict
from collections.abc import MutableMapping
from functools import wraps
from time import monotonic


class TTLCache(MutableMapping):
    def __init__(self, maxsize: int = 256, ttl: float = 300):
        if maxsize < 0 or ttl < 0:
            raise ValueError("Cache size and TTL must be non-negative")
        self.maxsize, self.ttl = maxsize, ttl
        self._items = OrderedDict()

    def __getitem__(self, key):
        expires, value = self._items[key]
        if expires <= monotonic():
            del self._items[key]
            raise KeyError(key)
        self._items.move_to_end(key)
        return value

    def __setitem__(self, key, value):
        if not self.maxsize or not self.ttl:
            return
        self._items[key] = (monotonic() + self.ttl, value)
        self._items.move_to_end(key)
        while len(self._items) > self.maxsize:
            self._items.popitem(last=False)

    def __delitem__(self, key):
        del self._items[key]

    def __iter__(self):
        now = monotonic()
        for key in list(self._items):
            if self._items[key][0] <= now:
                del self._items[key]
        return iter(self._items)

    def __len__(self):
        return sum(1 for _ in self)


def coalesce_user(method):
    @wraps(method)
    async def wrapped(self, username: str):
        self._check_open()
        username = username.strip().lstrip("@").lower()
        if not username or any(c in username for c in "/\\?#&"):
            raise ValueError("Invalid username")
        try:
            return self._user_cache[username].model_copy(deep=True)
        except KeyError:
            pass
        key = (method.__name__, username)
        task = self._inflight.get(key)
        if task is None:
            task = asyncio.create_task(method(self, username))
            self._inflight[key] = task

            def done(completed):
                if self._inflight.get(key) is completed:
                    self._inflight.pop(key, None)
                if not completed.cancelled():
                    completed.exception()

            task.add_done_callback(done)
        result = await asyncio.shield(task)
        return result.model_copy(deep=True)

    return wrapped
