# gherila

An async wrapper for Instagram, TikTok, Brave, GitHub, Twitter, Reddit and Snapchat.
Gherila runs on your machine and fetches data directly from those platforms.

Python applications use the existing async classes. Other languages can call the
same implementations through a local subprocess exchanging newline-delimited JSON.
This provides access from any language with process execution and JSON support;
it is not a separate native implementation for every language. The provided
clients and launchers automatically install a private Python runtime and Gherila
during installation or on first use, then reuse the cache. Users of other languages do not need to install
Python manually. Linux, Windows and macOS are covered by the test workflow.

## Installation

For Python applications, install from the source containing these changes until
they are included in a PyPI release (Python 3.10+):

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
Its npm install hook sets up private Python 3.13, the matching Gherila source and
all dependencies. If install scripts are disabled, run `npx --no-install gherila-runtime install`
after installing the package, call `await install()` below, or let the first client call prepare it.

```js
import { install } from '@gherila/client';

const runtime = await install(); // Works in JavaScript and TypeScript; safe to repeat.
console.log(runtime.python);
```

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

Run the install command from any language's process API. It downloads Python and
sets up Gherila and its dependencies, prints one JSON runtime report, then exits:

```sh
# Linux / macOS
sh runtime/gherila.sh install
```

```powershell
# Windows
powershell.exe -NoProfile -ExecutionPolicy Bypass -File runtime/gherila.ps1 install
```

The included [language examples](examples/languages/README.md) have `install`
commands for Go, C#, Rust, Ruby, Java and PHP. C and C++ can call
`gherila_install(NULL)` from the [shared header](bindings/c/gherila.h).
No Python or Node installation is needed by those integrations. Repeated installs
reuse the same private environment.

Start `sh runtime/gherila.sh` on Linux/macOS or
`powershell.exe -NoProfile -ExecutionPolicy Bypass -File runtime/gherila.ps1` on
Windows. These launchers set up Python and Gherila automatically. Send one JSON
object per stdin line and read one response per stdout line. The existing
`python -u -m gherila` and `gherila` commands remain available to Python users.

```json
{"id":"1","platform":"github","method":"get_user","kwargs":{"username":"octocat"}}
```

The reply has `result` or `error`, plus the matching `id` and `version: 1`.
Keep the process open for repeated calls. Use `create` for persistent authenticated
clients. Pass `--describe` to the launcher to list every method and argument.

| Integration | Included |
| --- | --- |
| Python | Existing async classes and Pydantic models |
| JavaScript / TypeScript | Typed client, `install()` API, CLI and npm install hook |
| C / C++ | Shared header with `gherila_install()` and process/JSON bridge |
| Rust | Dependency-free install and process/JSON example |
| Go, Java, C#, PHP, Ruby | Runnable examples with `install` commands and automatic setup |
| Other languages | Shared automatic launcher and documented process/JSON interface |

See [automatic setup](runtime/README.md), [the protocol](docs/bridge.md) and
[language examples](examples/languages). First use needs internet access and a
writable user cache. The host must allow local processes; browser-only and
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
and compiles/runs C, C++ and Rust on all three systems. Go, Java, C#, PHP and Ruby
installation commands, shared cache reuse and errors are checked on Linux.
