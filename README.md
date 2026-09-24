# gherila

An async wrapper for Instagram, TikTok, Brave, GitHub, Twitter, Reddit and Snapchat.
Gherila runs on your machine and fetches data directly from those platforms.

Python applications use the existing async classes. Other languages can call the
same implementations through a local subprocess exchanging newline-delimited JSON.
This provides access from any language with process execution and JSON support;
it is not a separate native implementation for every language. Python 3.10+ is
required on the host. Linux, Windows and macOS are covered by the test workflow.

## Installation

The bridge and JavaScript client are new in this checkout. Install from the source
containing these changes until they are included in a PyPI release:

```sh
python -m pip install .
```

For released Python-only functionality: `python -m pip install -U gherila`.

## Python

```python
import asyncio
import os
from gherila import Instagram

async def main():
  ig = Instagram(os.environ["INSTAGRAM_CSRF"], os.environ["INSTAGRAM_SESSION_ID"])
  user = await ig.get_user("instagram")
  print(user)

asyncio.run(main())
```

## JavaScript / TypeScript

Install the included client with `npm install ./bindings/javascript` from your
application, adjusting the path to this checkout. It is not yet published to npm.

```js
import { Gherila } from '@gherila/client';

const api = new Gherila();
try {
  const github = await api.create('github');
  const user = await github.get_user({ username: 'octocat' });
  console.log(user);
} finally {
  await api.close();
}
```

The client preserves credentials and caches across calls, supports concurrent
requests, and converts binary downloads to `Buffer` and large integers to `bigint`.
See [client options and authentication](bindings/javascript/README.md).

## Other languages

Start `python -u -m gherila`, send one JSON object per stdin line, and read one
response per stdout line. The installed `gherila` command does the same thing.

```json
{"id":"1","platform":"github","method":"get_user","kwargs":{"username":"octocat"}}
```

The reply has `result` or `error`, plus the matching `id` and `version: 1`.
Keep the process open for repeated calls. Use `create` for persistent authenticated
clients. `python -m gherila --describe` lists every available method and argument.

| Integration | Included |
| --- | --- |
| Python | Existing async classes and Pydantic models |
| JavaScript / TypeScript | Local client with typed methods for all seven providers |
| Go, Java, C#, PHP, Ruby | Runnable examples using the same JSON protocol |
| Other languages | Documented process/JSON interface |

See [the protocol](docs/bridge.md) and [language examples](examples/languages).
This interface requires a host that can run Python subprocesses; browser-only and
restricted mobile/WebAssembly environments need a host-side integration.

The bridge shares Python's upstream behavior, credentials, limits and platform
availability. The automated tests use offline fixtures; they do not establish
that every third-party endpoint is currently available.

## Development

```sh
python -m pip install -e . build
python -m unittest discover -s tests -v
node --test bindings/javascript/test/*.test.js
python -m build
```

Set `GHERILA_PYTHON` to the executable with Gherila installed when testing the Node
client. CI runs the Python and Node integration tests on Linux, Windows and macOS,
and compiles/runs the other language examples on Linux.
