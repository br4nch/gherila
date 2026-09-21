# gherila

Async Python clients for GitHub, Instagram, TikTok, Twitter/X, Reddit, Snapchat,
and Brave, with an optional HTTP API for applications written in other languages.

## Install

Python **3.10 or newer** is required. The CI matrix covers Python 3.10–3.14 on
Linux, Windows, and macOS, with an additional Linux ARM64 job. Passing CI on a
release is the compatibility evidence; adding a runner alone does not establish support.

```sh
python -m pip install -U gherila
# Optional JSON/HTML acceleration:
python -m pip install 'gherila[fast]'
# Optional HTTP server:
python -m pip install 'gherila[api]'
```

For an unreleased checkout, run `python -m pip install -e '.[api,dev]'` instead.
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

## Other languages: HTTP + JSON

Run the server on any supported Python host:

```sh
gherila-api --host 127.0.0.1 --port 8000
```

- Interactive documentation: `http://127.0.0.1:8000/docs`
- OpenAPI schema: `http://127.0.0.1:8000/openapi.json`
- Health check: `http://127.0.0.1:8000/health`

Any language with an HTTP client can use the API. The library itself remains
Python; other languages communicate with the server instead of importing it.
You can also generate language-specific clients from the OpenAPI schema.

```sh
curl --fail 'http://127.0.0.1:8000/v1/github/get_user?username=br4nch'
```

JavaScript (Node.js with built-in fetch, or a browser using a same-origin proxy):

```javascript
const response = await fetch(
  'http://127.0.0.1:8000/v1/github/get_user?username=br4nch'
);
if (!response.ok) throw new Error(`HTTP ${response.status}`);
const user = await response.json();
console.log(user.login, user.id);
```

Examples for Go, Java, C#, PHP, and Ruby are in [docs/languages.md](docs/languages.md).

JSON identifiers (`id`, `pk`, and `user_id`) are strings to avoid losing precision
in languages with limited numeric precision. Python model attributes keep their
native types. API query arguments are described by OpenAPI; collection sizes
are capped at 500 and otherwise-unbounded methods default to 50 in the API.
The Python clients permit larger collections and expose GitHub async iterators.

### Server credentials and access

Configure credentials in the server environment, never in request URLs:

| Platform | Environment variables |
|---|---|
| GitHub | `GITHUB_TOKEN` (optional) |
| Instagram | `INSTAGRAM_CSRF`, `INSTAGRAM_SESSION_ID` |
| TikTok | `TIKTOK_TTWID`, `TIKTOK_MS_TOKEN` |
| Twitter/X | `TWITTER_AUTH_TOKEN`, `TWITTER_CT0`, `TWITTER_CSRF`, `TWITTER_AUTHORIZATION` |
| Reddit, Snapchat, Brave | No credentials configured by this adapter |

Unconfigured authenticated platforms return HTTP 503. Platform operations use
`/v1/{platform}/{method}`, for example `/v1/instagram/get_post?url=...`.
Local filesystem downloads are intentionally available only in the Python client.

Set `GHERILA_API_KEY` to require an `X-API-Key` header. The CLI requires this key
when binding to a non-loopback address. Use HTTPS through a reverse proxy for
remote deployment. The server represents one set of platform accounts and is
intended for trusted applications, not a public multi-tenant scraping service.
CORS is not enabled by default. Health/docs/schema contain no account credentials.

The API has a 60-second operation deadline and a concurrency limit of 32.
Applications can customize these using `gherila.api.create_app(...)`.
The app owns and closes any clients passed to `create_app(clients=...)`.

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
python -m pip install -e '.[api,dev]'
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
