# Automatic local runtime

The JavaScript/TypeScript client and Go, Java, C#, PHP and Ruby examples call this
shared launcher automatically. Users do not need to install Python or run pip.
Other languages can launch it using their normal process API and exchange the
same [JSON requests](../docs/bridge.md). All provider methods run the same Python
implementation with the same arguments and results.

Linux/macOS:

```sh
sh runtime/gherila.sh --describe
```

Windows:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File runtime/gherila.ps1 --describe
```

Without `--describe`, the launcher accepts protocol requests on stdin. Setup
messages go to stderr, so first-use installation never mixes with JSON responses.
The caller's input is preserved during setup. `--print-python` (or `-PrintPython`
on PowerShell) prepares the runtime and prints its executable path for clients
that prefer to spawn the worker themselves.

## What happens on first use

1. Download the platform-specific **uv 0.12.18** archive from Astral's GitHub release.
2. Verify its SHA-256 against the checked-in `uv-checksums.txt` before extraction.
3. Use uv to download managed Python 3.13 and install Gherila with its dependencies.
4. Cache the completed environment and reuse it on later calls.

The Python source is bundled with the client, rather than fetched from an
independent PyPI release. A source fingerprint keeps different core versions in
separate environments. Building happens in the cache so the installed client can
be read-only. Failed setup never writes a completed-environment marker and can be
retried. Concurrent processes share uv's locked caches. No administrator access,
global pip installation, PATH edits or shell profile edits are used. Windows runs
the bundled script with a process-scoped execution policy; enterprise policy can
still prevent execution.

## Cache and configuration

| Setting | Behavior |
| --- | --- |
| Linux default | `$XDG_CACHE_HOME/gherila`, falling back to `~/.cache/gherila` |
| macOS default | `~/Library/Caches/gherila` |
| Windows default | `%LOCALAPPDATA%\gherila` |
| `GHERILA_CACHE_DIR` | Override the cache directory |
| `GHERILA_OFFLINE=1` | Require cached setup; fail clearly if runtime files are missing |
| `GHERILA_PYTHON` | Clients/examples use this preconfigured executable and skip setup |
| `GHERILA_LAUNCHER` | Non-JavaScript examples use this relocated launcher path |

Cached launchers can start without internet, but fetching platform data still
needs internet. First setup needs HTTPS access to GitHub and the Python package
index. Unsupported architectures or download/install failures produce errors;
the launcher never silently falls back to an unrelated Gherila version.

The launchers handle x86_64 and ARM64 on Linux, macOS and Windows. Platform support
also depends on Python and dependency availability; CI exercises Linux x86_64,
Windows x86_64 and the hosted macOS runner. POSIX hosts need a shell, curl, tar,
SHA-256 tooling and standard file utilities. Windows uses built-in PowerShell.
Browser-only JavaScript and restricted mobile/WASM sandboxes cannot install or
launch this local runtime themselves.

## Distributing another language integration

Build a portable directory containing the launcher and matching Python source:

```sh
node tools/package-runtime.mjs /path/to/output/gherila-runtime
```

Ship that directory with your integration and launch `gherila.sh` or `gherila.ps1`.
Node is used only by this packaging helper, not by the launcher or by Go, Java,
C#, PHP or Ruby applications. `npm pack` runs this bundling step automatically
for the JavaScript client. The repository checkout works directly too.

uv uses Python builds from [python-build-standalone](https://docs.astral.sh/uv/guides/install-python/).
The pinned uv archives and their hashes are available in the
[upstream release](https://github.com/astral-sh/uv/releases/tag/0.12.18).
