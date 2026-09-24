# Local language protocol (version 1)

For automatic Python installation, start `sh runtime/gherila.sh` on Linux/macOS,
or `powershell.exe -NoProfile -ExecutionPolicy Bypass -File runtime/gherila.ps1`
on Windows. They prepare a private runtime and execute this exact interface.
Add `install` to either launcher to prepare everything and return a JSON runtime
report without starting the request loop. This is a launcher command, not a
protocol operation sent over stdin. See [installation from other languages](../runtime/README.md#install-from-any-language).
Python users can also run `python -u -m gherila` or the installed `gherila` command.
See [automatic setup](../runtime/README.md). Write UTF-8 JSON objects, one per line, to stdin; read UTF-8
response objects, one per line, from stdout. Diagnostics go to stderr. Each request
must fit in 8 MiB including its newline. No listening port, shared service or
network connection is used between your application and the worker. The providers
still make their normal outbound HTTP requests.

This is Gherila's small versioned protocol, not JSON-RPC 2.0. All requests receive
a reply, even if `id` is omitted. An ID may be a string, safe integer or null;
use unique strings when issuing concurrent requests. `version` defaults to `1`.

## Operations

### Discover the API

```json
{"id":"schema","op":"describe"}
```

The result contains `protocol: 1` and `platforms`, with constructor `options` and
`methods`. Each parameter includes `name`, `required`, any `default`, and a JSON
Schema when the Python parameter is annotated. The signatures are discovered from
the installed Python classes, including future public async methods. Pydantic input
schemas include aliases; model field names are also accepted where the Python
model supports them. Run `python -m gherila --describe` to print the schema and exit.

### Create a persistent provider

```json
{"id":"create","op":"create","client":"ig","platform":"instagram","options":{"csrf":"YOUR_CSRF","session_id":"YOUR_SESSION"}}
```

Response:

```json
{"version":1,"id":"create","result":{"client":"ig"}}
```

`client` is a nonempty name up to 128 characters, unique within the worker.
Creation with an existing name fails; close it before replacing credentials.
Options match the Python constructor and travel in stdin, not command-line arguments.

| Platform | Required options | Optional options |
| --- | --- | --- |
| `brave` | None | None |
| `github` | None | None |
| `instagram` | `csrf`, `session_id` | `proxy` (array of URLs), `max_concurrent` |
| `reddit` | None | None |
| `snapchat` | None | None |
| `tiktok` | `ttwid`, `msToken` | None |
| `twitter` | `auth_token`, `ct0`, `crsf`, `authorization` | None |

The `crsf` spelling above matches the existing Twitter constructor.

### Call a method

```json
{"id":"user","client":"ig","method":"get_user","kwargs":{"username":"instagram"}}
{"id":"followers","client":"ig","method":"get_followers","args":["instagram"],"kwargs":{"amount":10}}
```

`op` defaults to `call`. `args` defaults to `[]`; `kwargs` defaults to `{}`.
Positional and keyword arguments follow the Python signature. Annotated arguments
are validated and model-valued parameters are reconstructed as Python models.
Only public async provider methods are callable. Private attributes, constructors,
arbitrary imports and arbitrary Python expressions are not exposed.

For a single call, omit `client` and supply `platform` plus any `options`:

```json
{"id":"repo","platform":"github","method":"get_repo","kwargs":{"username":"br4nch","repo_name":"gherila"}}
```

This creates a provider for that call only. Named clients preserve their Python
state, credentials and caches; they cannot be combined with `platform` or `options`
on a call. The existing Python transport's connection behavior is unchanged.

### Close a provider

```json
{"id":"close","op":"close","client":"ig"}
```

Returns `null` after earlier calls have completed. All operations other than `call`
act as barriers: earlier calls finish before the operation runs. This makes
pipelined create/call/close sequences predictable. Calls between barriers can
finish out of order. Match replies by `id`, not by line position.

Close stdin when finished; the worker drains pending calls and exits. Read stdout
while writing requests, and inherit or drain stderr to avoid pipe deadlocks.
Defaults: at most eight active calls and a 60-second timeout per call. Change these
using `--concurrency 16 --timeout 120`. A call's timeout begins when it is dispatched,
not while waiting in the queue. The worker applies backpressure by bounding the
number of tasks and each request's size. Downloading to a file avoids returning a
large base64 response, though the existing downloader still buffers the media in
Python memory. Stop the process to abort the entire session.

## Values

| Python value | Wire representation |
| --- | --- |
| Pydantic model / Munch / dict | JSON object using model field names, recursively |
| list / tuple | JSON array |
| bool / null / finite float | Corresponding JSON value |
| Integer within ±9,007,199,254,740,991 | JSON number |
| Larger integer | `{"$gherila":"int","value":"9223372036854775807"}` |
| datetime / date | ISO 8601 string |
| URL / Path | String |
| bytes / BytesIO | `{"$gherila":"bytes","value":"AP8="}` (base64) |

The exact two-key objects with `$gherila` and `value` above are reserved wire
values. They are recursively decoded in input arguments too. JavaScript bindings
automatically convert them to/from `bigint` and `Buffer`. Other clients may keep
the integer's decimal string or convert it to an appropriate integer type. Never
convert a large identifier to an IEEE-754 number. Non-finite numbers are rejected.

Model results can be passed directly to methods expecting that model. For example,
send the result of `tiktok.get_video` as `kwargs.video` to `download_video` with
`path: null` for bytes or a string path to save a file on the local host. Unlike
Python objects, results do not retain Python methods or object identity.

## Errors

```json
{"version":1,"id":"user","error":{"code":"invalid_params","message":"Arguments do not match the method signature. See describe."}}
```

| Code | Meaning |
| --- | --- |
| `invalid_json` | Malformed UTF-8/JSON; ID could not be read |
| `request_too_large` | Line exceeds 8 MiB; ID could not be read |
| `invalid_request` | Unsupported version, operation or envelope value |
| `invalid_params` | Constructor or method argument mismatch |
| `unknown_platform` / `unknown_client` / `unknown_method` | Requested target is unavailable |
| `client_exists` | Provider name is already in use |
| `timeout` | Provider call exceeded its deadline |
| `provider_error` | Provider or serialization failed; `type` names the Python exception |

Provider exception messages and validation inputs are not returned because they
may contain credentials or proxy passwords. Errors do not end the worker. A normal
worker exit status of zero means the protocol finished, not that every call succeeded;
check every response's `error` field. Upstream authentication, limits and scraping
failures are the same as when calling Python directly.

Use this as a local library interface with trusted application input. Provider
calls can make outbound requests, and download paths can write files with the
worker user's permissions.
