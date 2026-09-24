# Gherila from C and C++

Include `gherila.h` in C99 or C++11 code and ship the [portable runtime](../../runtime/README.md)
with your application. No Python headers, Python installation or Node runtime are required.
The same header supports Linux, macOS and Windows.

```c
#include "gherila.h"

int main(void) {
  return gherila_install(NULL);
}
```

This installs private Python, Gherila and its dependencies if needed, prints a
JSON runtime report to stdout and returns zero on success. It returns nonzero
and writes diagnostics to stderr on failure. It can be called again to reuse
the cache; it waits for installation but never reads stdin.

Pass a launcher filename to `gherila_install(path)` or set `GHERILA_LAUNCHER`.
Use `gherila.sh` on POSIX hosts and `gherila.ps1` on Windows. With no override,
the path is `runtime/gherila.sh` or `runtime/gherila.ps1`, relative to the current
working directory. Explicit filenames are UTF-8; Windows environment paths are
read with Unicode APIs. Spaces and non-ASCII filenames are supported.

`gherila_run(path, NULL)` forwards the caller's stdin/stdout/stderr to the
[JSON bridge](../../docs/bridge.md). `gherila_run(path, "--describe")` prints its
provider schema and exits. These calls also prepare the runtime automatically.
Use your application's JSON library to encode requests, read replies and check
their `error` field. This helper provides process execution; it does not create
native C structs for provider results.

See [the C/C++ examples and build commands](../../examples/languages/README.md).
