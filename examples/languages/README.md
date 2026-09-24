# Language examples

No Python installation step is needed. Each example invokes the shared launcher,
which automatically sets up private Python and Gherila on first use. Later calls
reuse the cached runtime. The examples run locally and use the same provider
methods as Python. Credentials and request parameters are sent over stdin.

## Install from your language

Run these from the repository root. Each command prepares Python, Gherila and all
Python dependencies automatically, prints a JSON runtime report, then exits.
Running another language's install afterward reuses that same environment.

| Language | Install command |
| --- | --- |
| JavaScript / TypeScript | `npm install ./bindings/javascript` (automatic npm hook) |
| JS / TS explicit API | `await install()` from `@gherila/client` |
| JS explicit example | `node examples/languages/example.mjs install` |
| Go | `go run examples/languages/main.go install` |
| C# | `dotnet run --project examples/languages/csharp -- install` |
| Ruby | `ruby examples/languages/example.rb install` |
| Java | `java examples/languages/GherilaExample.java install` |
| PHP | `php examples/languages/example.php install` |
| C | `./build/gherila-native/bin/gherila-c install` after compiling below |
| C++ | `./build/gherila-native/bin/gherila-cpp install` after compiling below |
| Rust | `./build/gherila-native/bin/gherila-rust install` after compiling below |

After installing the Node package, `npx --no-install gherila-runtime install`
is another explicit entry point. It also works when npm install hooks were disabled.
TypeScript uses the same typed `install()` API; no separate Python command is required.

For C/C++ and Rust, compile the examples once using your normal toolchain:

```sh
cmake -S examples/languages/native -B build/gherila-native
cmake --build build/gherila-native --config Release
rustc examples/languages/example.rs -o build/gherila-native/bin/gherila-rust
```

On Windows, add `.exe` to the Rust output filename and executable commands.
CMake produces `.exe` files automatically for C/C++. C99/C++11 and Rust's standard
library are sufficient. C/C++ programs can directly call `gherila_install(NULL)`
from [the provided header](../../bindings/c/gherila.h); Rust programs can reuse
the example's `install()` function. All setup steps run from the language's normal
process facilities. The launchers themselves require neither a compiler nor Node.

These commands are included integrations in this checkout, not registry releases
for Cargo, NuGet, RubyGems or Go. Use the shared launcher from any additional language
with process support; see [the install report contract](../../runtime/README.md).

## Call provider methods

Run these commands from the repository root:

| Language | Command | Runtime |
| --- | --- | --- |
| JavaScript | `node examples/languages/example.mjs` | Node 18+ |
| Go | `go run examples/languages/main.go` | Go 1.20+ |
| Java | `java examples/languages/GherilaExample.java` | Java 11+ |
| C# | `dotnet run --project examples/languages/csharp` | .NET 8 |
| PHP | `php examples/languages/example.php` | PHP 7.4+ |
| Ruby | `ruby examples/languages/example.rb` | Ruby 2.7+ |

The examples in this table fetch `octocat` on GitHub. Go, Java, C#, PHP and Ruby also accept a
`GHERILA_REQUEST` environment variable containing a request from
[the protocol documentation](../../docs/bridge.md). For an offline smoke check,
set it to `{"id":"example","op":"describe"}`. The Java example prints the whole
response envelope; use your application's JSON parser and check `error` before
reading `result`. The other examples unwrap the result and fail on provider errors.

The C, C++ and Rust examples forward stdin/stdout to the bridge when invoked
without arguments. Send the same JSON requests from your application, or pass
`--describe` to print all provider methods. They print the response envelope;
your JSON parser must check `error` before reading `result`.

These small examples start a worker per invocation. For repeated calls, keep the
process and both pipes open, use `create` once, then correlate `call` replies by
`id`. Drain stdout while writing requests and inherit or drain stderr; closing
stdin waits for pending calls and exits. The JavaScript client handles this for you.

The same protocol can be used from Swift, Kotlin, Dart, Lua, R,
PowerShell, and other languages with process execution and JSON support. This
repository does not claim a tested native SDK for each of those languages.

The launcher is `runtime/gherila.sh` on Linux/macOS (`/bin/sh` executes it) and
`runtime/gherila.ps1` on Windows (PowerShell executes it). It does not require
Node to run. Set `GHERILA_LAUNCHER` to use a relocated portable launcher, or
`GHERILA_PYTHON` in the Go/Java/C#/PHP/Ruby examples to use a preconfigured Python
for provider calls. Explicit install commands always prepare the private runtime.
JavaScript chooses
its bundled launcher automatically and supports an explicit `python` option.
`GHERILA_CACHE_DIR` sets the private cache location; `GHERILA_OFFLINE=1` requires
a previously prepared runtime. See [automatic setup](../../runtime/README.md).
