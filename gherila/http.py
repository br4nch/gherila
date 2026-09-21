"""Pooled, bounded HTTP transport shared by all platform clients."""

import asyncio
import math
import os
import random
import tempfile
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import aiofiles
from aiohttp import ClientError, ClientSession, ClientTimeout, TCPConnector
from munch import DefaultMunch

from ._json import loads
from ._utils import validate_url
from .exceptions import (
    AuthenticationError,
    HTTPError,
    NotFoundError,
    ParseError,
    RateLimitError,
    ResponseTooLargeError,
    TransportError,
)


def retry_after_seconds(value: str | None) -> float | None:
    if not value:
        return None
    try:
        seconds = float(value)
    except ValueError:
        try:
            date = parsedate_to_datetime(value)
            if date.tzinfo is None:
                date = date.replace(tzinfo=timezone.utc)
            seconds = (date - datetime.now(timezone.utc)).total_seconds()
        except (ValueError, TypeError, OverflowError):
            return None
    return max(0.0, seconds) if math.isfinite(seconds) else None


class State:
    def __init__(
        self,
        *,
        session: ClientSession | None = None,
        timeout: float | ClientTimeout = 30,
        retries: int = 2,
        max_connections: int = 30,
        max_connections_per_host: int = 10,
        max_response_bytes: int = 16 * 1024 * 1024,
        max_download_bytes: int = 256 * 1024 * 1024,
        max_retry_delay: float = 30,
        proxy: str | None = None,
        trust_env: bool = False,
    ):
        if retries < 0 or max_connections <= 0 or max_connections_per_host <= 0:
            raise ValueError("Retries must be non-negative and connection limits positive")
        if min(max_response_bytes, max_download_bytes) <= 0 or max_retry_delay < 0:
            raise ValueError("Byte limits must be positive and retry delay non-negative")
        if not isinstance(timeout, ClientTimeout) and timeout <= 0:
            raise ValueError("timeout must be positive")
        self._session = session
        self._owns_session = session is None
        self._closed = False
        self.timeout = (
            timeout
            if isinstance(timeout, ClientTimeout)
            else ClientTimeout(total=timeout, connect=min(timeout, 10), sock_read=timeout)
        )
        self.retries = retries
        self.max_connections = max_connections
        self.max_connections_per_host = max_connections_per_host
        self.max_response_bytes = max_response_bytes
        self.max_download_bytes = max_download_bytes
        self.max_retry_delay = max_retry_delay
        self.proxy = proxy
        self.trust_env = trust_env

    def _get_session(self) -> ClientSession:
        if self._closed:
            raise RuntimeError("HTTP client is closed")
        if self._session is None:
            self._session = ClientSession(
                timeout=self.timeout,
                trust_env=self.trust_env,
                connector=TCPConnector(
                    limit=self.max_connections, limit_per_host=self.max_connections_per_host
                ),
            )
        if self._session.closed:
            raise RuntimeError("The supplied HTTP session is closed")
        return self._session

    async def close(self):
        self._closed = True
        if self._owns_session and self._session is not None:
            await self._session.close()

    async def _follow(self, method, url, allowed_hosts, kwargs):
        url = validate_url(url, allowed_hosts)
        hosts = allowed_hosts if allowed_hosts is not None else {urlsplit(url).hostname}
        session = self._get_session()
        options = dict(kwargs)
        options.setdefault("timeout", self.timeout)
        options.setdefault("proxy", self.proxy)
        follow = options.pop("allow_redirects", True)
        for _ in range(6):
            response = await session.request(method, url, allow_redirects=False, **options)
            if response.status not in {301, 302, 303, 307, 308} or not follow:
                return response
            location = response.headers.get("Location")
            response.release()
            if not location:
                raise TransportError("Redirect has no Location header")
            target = validate_url(urljoin(url, location), allowed_hosts)
            if urlsplit(target).hostname not in hosts:
                raise TransportError("Redirect left the allowed platform hosts")
            if allowed_hosts is None and urlsplit(target).netloc != urlsplit(url).netloc:
                raise TransportError("Redirect changed the origin")
            old, new = urlsplit(url), urlsplit(target)
            if old.scheme == "https" and new.scheme != "https":
                raise TransportError("Refusing HTTPS downgrade")
            if (old.scheme, old.netloc) != (new.scheme, new.netloc):
                sensitive = {"authorization", "cookie", "x-csrf-token", "x-csrftoken"}
                if any(key.lower() in sensitive for key in session.headers) or session.auth:
                    raise TransportError(
                        "Cross-origin redirect with session credentials is unsupported"
                    )
                options["headers"] = {
                    key: value
                    for key, value in options.get("headers", {}).items()
                    if key.lower() not in sensitive
                }
                options.pop("auth", None)
                options.pop("cookies", None)
            options.pop("params", None)
            if (
                response.status == 303
                and method != "HEAD"
                or response.status in {301, 302}
                and method == "POST"
            ):
                method = "GET"
                options.pop("data", None)
                options.pop("json", None)
            url = target
        raise TransportError("Too many redirects")

    async def _open(self, method, url, *, allowed_hosts=None, **kwargs):
        method = method.upper()
        attempts = self.retries + 1 if method in {"GET", "HEAD"} else 1
        for attempt in range(attempts):
            try:
                response = await self._follow(method, url, allowed_hosts, kwargs)
            except (ClientError, asyncio.TimeoutError) as exc:
                if attempt + 1 == attempts:
                    raise TransportError("Network request failed or timed out") from exc
                await asyncio.sleep(min(self.max_retry_delay, random.uniform(0, 0.5 * 2**attempt)))
                continue
            status = response.status
            if 200 <= status < 300:
                return response
            retry_after = retry_after_seconds(response.headers.get("Retry-After"))
            response.release()
            error_type = {
                401: AuthenticationError,
                403: AuthenticationError,
                404: NotFoundError,
                429: RateLimitError,
            }.get(status, HTTPError)
            error = error_type(
                f"Upstream returned HTTP {status}", status=status, retry_after=retry_after
            )
            if status not in {429, 500, 502, 503, 504} or attempt + 1 == attempts:
                raise error
            if retry_after is not None and retry_after > self.max_retry_delay:
                raise error  # Never retry earlier than the server requested.
            delay = retry_after if retry_after is not None else random.uniform(0, 0.5 * 2**attempt)
            await asyncio.sleep(min(self.max_retry_delay, delay))
        raise TransportError("Request attempts exhausted")

    async def _read(self, response, limit):
        chunks = bytearray()
        async for chunk in response.content.iter_chunked(64 * 1024):
            if len(chunks) + len(chunk) > limit:
                raise ResponseTooLargeError("Response exceeds the configured byte limit")
            chunks.extend(chunk)
        return bytes(chunks)

    async def request(self, method: str, url: str, *, response_type="auto", **kwargs):
        if response_type not in {"auto", "json", "text", "bytes"}:
            raise ValueError("response_type must be auto, json, text, or bytes")
        response = await self._open(method, url, **kwargs)
        try:
            async with response:
                body = await self._read(response, self.max_response_bytes)
                kind = response_type
                if kind == "auto":
                    content_type = response.content_type
                    if content_type == "application/json" or content_type.endswith("+json"):
                        kind = "json"
                    elif (
                        content_type.startswith("text/") or content_type == "application/xhtml+xml"
                    ):
                        kind = "text"
                    else:
                        kind = "bytes"
                if kind == "bytes":
                    return body
                if kind == "text":
                    try:
                        return body.decode(response.charset or "utf-8")
                    except (UnicodeError, LookupError) as exc:
                        raise ParseError("Could not decode response text") from exc
                if not body and response.status in {204, 205}:
                    return None
                try:
                    return DefaultMunch.fromDict(loads(body))
                except (ValueError, TypeError) as exc:
                    raise ParseError("Could not parse response JSON") from exc
        except (ClientError, asyncio.TimeoutError) as exc:
            raise TransportError("Response body transfer failed") from exc

    async def download(self, url: str, path: str | Path | None = None, **kwargs) -> Path | BytesIO:
        """Stream to a temporary sibling, then atomically replace the destination."""
        response = await self._open("GET", url, **kwargs)
        temporary = None
        try:
            async with response:
                if path is None:
                    return BytesIO(await self._read(response, self.max_response_bytes))
                destination = Path(path)
                fd, temporary = tempfile.mkstemp(
                    prefix=".gherila-", suffix=".part", dir=destination.parent
                )
                os.close(fd)  # Windows requires closure before reopening/replacing.
                total = 0
                async with aiofiles.open(temporary, "wb") as output:
                    async for chunk in response.content.iter_chunked(64 * 1024):
                        total += len(chunk)
                        if total > self.max_download_bytes:
                            raise ResponseTooLargeError(
                                "Download exceeds the configured byte limit"
                            )
                        await output.write(chunk)
                os.replace(temporary, destination)
                temporary = None
                return destination
        except (ClientError, asyncio.TimeoutError) as exc:
            raise TransportError("Download transfer failed") from exc
        finally:
            if temporary is not None:
                Path(temporary).unlink(missing_ok=True)
