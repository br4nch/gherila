# Language examples

Install this checkout first with `python -m pip install .`. Set `GHERILA_PYTHON`
to the Python executable containing Gherila if it is not the default `python3`
(`python` on Windows). The examples run locally and use the same provider methods
as Python. Credentials and request parameters are sent over stdin.

Run these commands from the repository root:

| Language | Command | Runtime |
| --- | --- | --- |
| JavaScript | `node examples/languages/example.mjs` | Node 18+ |
| Go | `go run examples/languages/main.go` | Go 1.20+ |
| Java | `java examples/languages/GherilaExample.java` | Java 11+ |
| C# | `dotnet run --project examples/languages/csharp` | .NET 8 |
| PHP | `php examples/languages/example.php` | PHP 7.4+ |
| Ruby | `ruby examples/languages/example.rb` | Ruby 2.7+ |

Each fetches `octocat` on GitHub. Go, Java, C#, PHP and Ruby also accept a
`GHERILA_REQUEST` environment variable containing a request from
[the protocol documentation](../../docs/bridge.md). For an offline smoke check,
set it to `{"id":"example","op":"describe"}`. The Java example prints the whole
response envelope; use your application's JSON parser and check `error` before
reading `result`. The other examples unwrap the result and fail on provider errors.

These small examples start a worker per invocation. For repeated calls, keep the
process and both pipes open, use `create` once, then correlate `call` replies by
`id`. Drain stdout while writing requests and inherit or drain stderr; closing
stdin waits for pending calls and exits. The JavaScript client handles this for you.

The same protocol can be used from Rust, C/C++, Swift, Kotlin, Dart, Lua, R,
PowerShell, and other languages with process execution and JSON support. This
repository does not claim a tested native SDK for each of those languages.
