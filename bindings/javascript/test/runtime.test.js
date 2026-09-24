import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { mkdtemp, mkdir, readdir, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { delimiter, join, resolve } from 'node:path';
import { test } from 'node:test';
import { promisify } from 'node:util';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { Gherila } from '../index.js';

const exec = promisify(execFile);
const root = fileURLToPath(new URL('../../../', import.meta.url));

test('automatic setup errors reject callers and allow close', async () => {
  const cache = await mkdtemp(join(tmpdir(), 'gherila-offline-'));
  const api = new Gherila({ python: '', env: { GHERILA_CACHE_DIR: cache, GHERILA_OFFLINE: '1' } });
  try { await assert.rejects(api.describe(), /first setup needs internet/); }
  finally { await api.close(); await rm(cache, { recursive: true, force: true }); }
});

test('closing during automatic setup settles pending calls', async () => {
  const cache = await mkdtemp(join(tmpdir(), 'gherila-cancel-'));
  const api = new Gherila({ python: '', env: { GHERILA_CACHE_DIR: cache, GHERILA_OFFLINE: '1' } });
  const result = assert.rejects(api.describe());
  await api.close();
  await result;
  await rm(cache, { recursive: true, force: true });
});

test('packaged client installs private Python, shares setup, and works offline from cache', {
  skip: process.env.GHERILA_TEST_SETUP !== '1', timeout: 600000,
}, async () => {
  const directory = await mkdtemp(join(tmpdir(), 'gherila setup ü '));
  const cache = join(directory, 'cache');
  const blocked = join(directory, 'blocked');
  await mkdir(blocked);
  for (const name of ['python', 'python3', 'uv']) {
    await writeFile(join(blocked, name), '#!/bin/sh\necho "Unexpected host runtime" >&2\nexit 99\n', { mode: 0o755 });
    await writeFile(join(blocked, name + '.cmd'), '@echo Unexpected host runtime >&2\r\n@exit /b 99\r\n');
  }
  const env = {
    GHERILA_CACHE_DIR: cache, GHERILA_OFFLINE: '0',
    PATH: blocked + delimiter + process.env.PATH,
  };
  const module = process.env.GHERILA_TEST_CLIENT
    ? await import(pathToFileURL(resolve(process.env.GHERILA_TEST_CLIENT)).href)
    : { Gherila };
  const clients = [0, 1].map(() => new module.Gherila({ python: '', env, timeout: 5000 }));
  try {
    const results = await Promise.all(clients.map(client => client.describe()));
    for (const result of results) assert.equal(Object.keys(result.platforms).length, 7);
  } finally { await Promise.all(clients.map(client => client.close())); }

  const markers = await readdir(join(cache, 'environments'));
  assert.ok(markers.length >= 1);
  const python = (await readFile(join(cache, 'environments', markers[0]), 'utf8')).trim();
  assert.ok(python.startsWith(cache), 'Must use private Python, not a host installation.');
  const probe = await exec(python, ['-I', '-X', 'utf8', '-c', 'import gherila, sys; print(sys.prefix); print(gherila.__file__)']);
  assert.ok(probe.stdout.split('\n').every(line => !line.trim() || line.startsWith(cache)));

  const offline = { ...env, GHERILA_OFFLINE: '1', HTTPS_PROXY: 'http://127.0.0.1:9', HTTP_PROXY: 'http://127.0.0.1:9' };
  const api = new module.Gherila({ python: '', env: offline });
  try { assert.equal((await api.describe()).protocol, 1); }
  finally { await api.close(); }

  // The exact same cached launcher also works with raw process/JSON clients.
  const runtime = process.env.GHERILA_TEST_CLIENT
    ? join(resolve(process.env.GHERILA_TEST_CLIENT), '..', 'runtime') : join(root, 'runtime');
  const command = process.platform === 'win32' ? 'powershell.exe' : '/bin/sh';
  const args = process.platform === 'win32'
    ? ['-NoLogo', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', join(runtime, 'gherila.ps1'), '--describe']
    : [join(runtime, 'gherila.sh'), '--describe'];
  const described = await exec(command, args, { env: { ...process.env, ...offline }, timeout: 30000 });
  assert.equal(JSON.parse(described.stdout).protocol, 1);
  await rm(directory, { recursive: true, force: true });
});
