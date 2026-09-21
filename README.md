# gherila

Async Python clients for GitHub, Instagram, TikTok, Twitter/X, Reddit, Snapchat,
and Brave. Install the package in your application and call it directly: requests
run on the user’s machine using their network connection and credentials.

## Install

Python **3.10 or newer** is required. The CI matrix covers Python 3.10–3.14 on
Linux, Windows, and macOS, with an additional Linux ARM64 job. Passing CI on a
release is the compatibility evidence; adding a runner alone does not establish support.

```sh
python -m pip install -U gherila
# Optional JSON/HTML acceleration:
python -m pip install 'gherila[fast]'
```

For an unreleased checkout, run `python -m pip install -e '.[dev]'` instead.
On Windows Command Prompt, use double quotes around package extras.

The base installation uses standard-library JSON and HTML parsing. `orjson` and
`selectolax` are optional. Other dependencies, including aiohttp and Pydantic,
still determine which Python runtimes/architectures can install the package.
We do not claim support for MicroPython, browser-only Python, or every embedded runtime.

## Python usage

```python
import asyncio
from gherila import GitHub


async def main():
    async with GitHub() as github:
        user = await github.get_user("br4nch")
        print(user.login)
        async for repo in github.iter_repos("br4nch", limit=100):
            print(repo.name)


asyncio.run(main())
```

Reuse one client per platform/account in an application. Each client pools HTTP
connections and must be closed with `async with` or `await client.close()`.
Clients belong to one event loop; do not share them between loops or threads.
In an existing async application, await methods directly rather than calling
`asyncio.run()` again.

```python
import os
from gherila import Instagram


async def fetch_user():
    async with Instagram(
        os.environ["INSTAGRAM_CSRF"],
        os.environ["INSTAGRAM_SESSION_ID"],
        timeout=30,
        retries=2,
        cache_size=256,
        cache_ttl=300,
    ) as instagram:
        return await instagram.get_user("username")
```

All clients accept these keyword options:

| Option | Default | Meaning |
|---|---|---|
| `session` | `None` | Optional aiohttp session. Caller retains ownership and must close it. |
| `timeout` | `30` | Per-request timeout in seconds, or an aiohttp `ClientTimeout`. |
| `retries` | `2` | Additional attempts for GET/HEAD transient transport/HTTP failures. |
| `max_connections` | `30` | Pool connection limit. |
| `max_connections_per_host` | `10` | Per-host connection limit. |
| `cache_size` | `256` | Maximum cached users per client; `0` disables storage. |
| `cache_ttl` | `300` | User cache lifetime in seconds; `0` disables storage. |
| `max_response_bytes` | `16777216` | Limit for decoded in-memory responses. |
| `max_download_bytes` | `268435456` | Limit for streamed downloads. |
| `max_retry_delay` | `30` | Maximum automatic wait; longer Retry-After values raise immediately. |
| `proxy` | `None` | HTTP proxy; Instagram retains its list-of-proxies argument. |
| `trust_env` | `False` | Opt into environment proxy configuration. |

Concurrent lookups for the same user share one request. Each caller receives an
independent model. Cancelling one caller does not cancel other callers' lookup;
closing the client cancels pending shared lookups. Failures are not cached.
Retries and redirects can make a whole operation exceed one request timeout.
For an operation deadline, use `asyncio.wait_for(...)`.

## Local wrapper and language support

Gherila is a Python library, not a hosted service. Your application creates a
client and calls its methods directly; no gherila server, account, port, or
separate background process is needed. Platform requests still require internet
access and, where applicable, the user's own platform credentials.

Linux, Windows, and macOS are operating-system targets. Programming-language
support is separate: a Python package cannot be imported natively by JavaScript,
Go, Java, C#, or other languages. Native support for those languages would require
separate wrappers/packages or explicit language bindings. This release focuses
on the local Python wrapper and does not add a server as a substitute.

Credentials are supplied to the client constructors. `GitHub(token=...)` is
optional; Instagram, TikTok, and Twitter require their existing credential
arguments. Avoid hardcoding secrets in source code; environment variables or
your application's secret configuration work well.

## Errors and platform limits

Catch `gherila.exceptions.Error` for library failures, or its subclasses:
`AuthenticationError`, `NotFoundError`, `RateLimitError`, `HTTPError`,
`TransportError`, `ParseError`, and `ResponseTooLargeError`.
HTTP errors expose `status` and `retry_after`. Invalid caller parameters raise
`ValueError`. HTTP 403 is reported as an authentication/access error; it can also
represent an upstream block. The transport does not retry 401/403/404.

Platform HTTP responses may contain login challenges, restrictions, or changed
schemas even when the request returns HTTP 200. Private Instagram endpoints,
Twitter GraphQL operation IDs, and scraped HTML are not stable public contracts.
Valid credentials and allowed network access are still required; the package
cannot guarantee that every platform works from every IP or region.

Brave's portable HTML parser may return empty descriptions; the `fast` extra
adds surrounding-text descriptions. Reddit comment results include the comment
nodes returned by the endpoint; `more` placeholders are not expanded. TikTok
photo posts without a playable video raise `ParseError`.

## Development

```sh
python -m pip install -e '.[dev]'
python -m pytest -q
ruff check .
ruff format --check .
python -m build
```

Tests use synthetic fixtures and local HTTP servers, with no platform credentials.
CI tests optional accelerators separately, checks minimum dependency versions,
and installs both wheel and source distributions outside the source checkout.
Live platform checks are separate from these deterministic regression tests.

See [CHANGELOG.md](CHANGELOG.md) for migration notes.
