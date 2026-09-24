# Gherila for JavaScript and TypeScript

This client calls Gherila's existing providers through a local worker. Install
the client; its npm install hook automatically prepares Python, Gherila and dependencies:

```sh
npm install ./bindings/javascript
```

This package is included in the repository; it has not been published to npm.
Node 18+ is required. TypeScript projects also need `@types/node`. The npm package
includes the matching Python source; automatic setup installs it with private
Python 3.13, without relying on the current PyPI release.

To explicitly install or prepare the runtime from either JavaScript or TypeScript:

```js
import { install } from '@gherila/client';

const runtime = await install();
// { python: '/absolute/private/python', args: ['-I', '-X', 'utf8', '-u', '-m', 'gherila'], protocol: 1 }
```

Or run the package's command after installing it:

```sh
npx --no-install gherila-runtime install
```

All three entry points use the same installer. They finish only after Python,
Gherila and its dependencies are ready. Repeated installs reuse the cache and
do not start a persistent worker. `install({ env, cwd, timeout, signal })` supports
a custom environment, working directory, timeout in milliseconds (default 300000)
and an `AbortSignal`. Failures reject the promise or exit the CLI with a nonzero
status. The CLI prints one JSON report to stdout and setup messages to stderr.

If npm install scripts are disabled or require approval under your package manager's
policy, use the explicit command/function. Automatic first use also remains available.
`install()` always prepares the managed runtime; `GHERILA_PYTHON` only overrides
the interpreter used by ordinary client calls.

```js
import { Gherila } from '@gherila/client';

const api = new Gherila(); // Automatically prepares and caches its runtime.
try {
  const ig = await api.create('instagram', {
    csrf: process.env.INSTAGRAM_CSRF,
    session_id: process.env.INSTAGRAM_SESSION_ID,
  });
  const user = await ig.get_user({ username: 'instagram' });
  console.log(user);
  const followers = await ig.get_followers({ username: 'instagram', amount: 10 });
  console.log(followers);
} finally {
  await api.close();
}
```

Method names and keyword argument names match Python. All seven providers are
supported: `brave`, `github`, `instagram`, `reddit`, `snapchat`, `tiktok`, `twitter`.
`await api.describe()` lists their constructor options and method parameters.
`client.call('method', { keyword: 'value' }, [positionalArgument])` handles generic
calls, including future public async methods discovered by the worker.

Results are ordinary objects using Python model field names. Dates and URLs are
strings. Integers outside JavaScript's safe range become `bigint`; binary results
become `Buffer`. You can pass returned objects directly to subsequent methods:

```js
const tiktok = await api.create('tiktok', { ttwid: 'YOUR_TTWID', msToken: 'YOUR_MS_TOKEN' });
const video = await tiktok.get_video({ url: 'https://www.tiktok.com/@USER/video/ID' });
const bytes = await tiktok.download_video({ video, path: null });
```

Wrap the whole lifetime in `try/finally` as above. `client.close()` releases one
provider; `api.close()` closes stdin, waits for the worker, and kills it after five
seconds if it has not exited. Always await calls before closing for large downloads.
Different clients retain separate credentials and provider caches. The Python
installation and dependencies are shared in the per-user runtime cache.

Calls can run concurrently and responses are matched by ID. Defaults: eight
simultaneous provider calls, 60 seconds per provider call, 65 seconds total per
client request (including worker startup/queue time), and 256 pending requests. Configure
`concurrency`, `callTimeout` (seconds), `timeout` (milliseconds) and `maxPending` as
needed. A client-side timeout does not cancel a worker call; it may still finish,
including writing a requested download. Provider exceptions reject with a
`GherilaError` containing `code` and an optional Python exception `type`.

Runtime preparation has its own five-minute deadline (`setupTimeout`, in
milliseconds); ordinary request timeouts start after preparation. Set
`GHERILA_CACHE_DIR` in `env` to choose a cache directory and `GHERILA_OFFLINE=1`
to require cached setup. First use requires internet access. Closing during setup
cancels the installer and its child processes. Installation logs go to stderr.

Set `GHERILA_PYTHON` or pass `python` to use an executable with Gherila already
installed and skip setup. `{ autoInstall: false }` uses the default system Python
without installing anything. For the Windows
launcher use `{ python: 'py', pythonArgs: ['-3'] }`. `cwd` and `env` configure the
child process. Worker calls start without a shell; automatic setup uses the
bundled POSIX/PowerShell launcher. The Windows launcher permits execution only
within its own PowerShell process; it does not change machine execution policy.
This is a Node client; browser JavaScript cannot start local processes.
