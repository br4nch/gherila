// Exercise the language entry points without contacting provider endpoints.
import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { promisify } from 'node:util';

const exec = promisify(execFile);
const examples = [
  ['Go', 'go', ['run', 'examples/languages/main.go']],
  ['Java', 'java', ['examples/languages/GherilaExample.java']],
  ['C#', 'dotnet', ['examples/languages/csharp/bin/Debug/net8.0/GherilaExample.dll']],
  ['PHP', 'php', ['examples/languages/example.php']],
  ['Ruby', 'ruby', ['examples/languages/example.rb']],
];
let python;
for (const [language, command, args] of examples) {
  // Only the first language needs a download; all others must reuse that install.
  const env = { ...process.env, GHERILA_OFFLINE: python ? '1' : '0',
    GHERILA_PYTHON: 'gherila-no-host-python', GHERILA_REQUEST: '{"id":"example","op":"describe"}' };
  const ready = await exec(command, [...args, 'install'], { env, timeout: 300000 });
  const report = JSON.parse(ready.stdout);
  assert.equal(report.protocol, 1, language);
  assert.ok(report.python.startsWith(process.env.GHERILA_CACHE_DIR), language);
  if (python) assert.equal(report.python, python, language + ' reuses the same Python');
  python = report.python;
  const response = await exec(command, args, { env: { ...env, GHERILA_PYTHON: '', GHERILA_OFFLINE: '1' }, timeout: 60000 });
  const parsed = JSON.parse(response.stdout);
  assert.equal((parsed.result || parsed).protocol, 1, language + ' can call the worker');
  const empty = await mkdtemp(join(tmpdir(), 'gherila-install-failure-'));
  try {
    await assert.rejects(exec(command, [...args, 'install'], {
      env: { ...env, GHERILA_CACHE_DIR: empty, GHERILA_OFFLINE: '1' }, timeout: 60000,
    }), error => error.code !== 0 && !error.stdout.trim() && /first setup needs internet/.test(error.stderr));
  } finally { await rm(empty, { recursive: true, force: true }); }
  console.log(language + ': install, shared cache, provider discovery and failure propagation passed.');
}
