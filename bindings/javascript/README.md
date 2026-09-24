# Gherila for JavaScript and TypeScript

This client launches a local Python subprocess and calls Gherila's existing
providers. Install the Python package from this checkout, then install this client:

```sh
python -m pip install .
npm install ./bindings/javascript
```

This package is included in the repository; it has not been published to npm.
Node 18+ and Python 3.10+ are required. TypeScript projects also need `@types/node`.

```js
import { Gherila } from '@gherila/client';

const api = new Gherila(); // Or { python: '/path/to/venv/bin/python' }
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
Different clients retain separate credentials and caches.

Calls can run concurrently and responses are matched by ID. Defaults: eight
simultaneous provider calls, 60 seconds per provider call, 65 seconds total per
client request (including startup/queue time), and 256 pending requests. Configure
`concurrency`, `callTimeout` (seconds), `timeout` (milliseconds) and `maxPending` as
needed. A client-side timeout does not cancel a worker call; it may still finish,
including writing a requested download. Provider exceptions reject with a
`GherilaError` containing `code` and an optional Python exception `type`.

Set `GHERILA_PYTHON` or pass `python` to choose an executable. For the Windows
launcher use `{ python: 'py', pythonArgs: ['-3'] }`. `cwd` and `env` configure the
child process. The process starts without a shell. This is a Node client; browser
JavaScript cannot start local processes.
