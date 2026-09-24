import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { cp, mkdtemp, mkdir, readdir, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { delimiter, join, resolve } from 'node:path';
import { test } from 'node:test';
import { promisify } from 'node:util';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { Gherila, install } from '../index.js';

const exec = promisify(execFile);
const root = fileURLToPath(new URL('../../../', import.meta.url));

test('explicit install rejects offline setup failures and pre-cancelled requests', async () => {
  const cache = await mkdtemp(join(tmpdir(), 'gherila-install-'));
  const options = { env: { GHERILA_CACHE_DIR: cache, GHERILA_OFFLINE: '1' } };
  try {
    await assert.rejects(install({ ...options, signal: AbortSignal.abort() }), /cancelled/);
    assert.deepEqual(await readdir(cache), [], 'Cancelled setup must not start an installer.');
    await assert.rejects(install({ ...options, timeout: 0 }), /timeout/i);
    await assert.rejects(install(options), /first setup needs internet/);
    await assert.rejects(exec(process.execPath, [join(root, 'bindings/javascript/cli.js'), 'install'], {
      env: { ...process.env, ...options.env }, timeout: 30000,
    }), error => error.code === 1 && !error.stdout.trim() && /first setup needs internet/.test(error.stderr));
  } finally { await rm(cache, { recursive: true, force: true }); }
});

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

test('explicit install and first use share setup; CLI and native clients reuse it offline', {
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
    : { Gherila, install };
  const client = new module.Gherila({ python: '', env, timeout: 5000 });
  try {
    const [installed, described] = await Promise.all([module.install({ env }), client.describe()]);
    assert.ok(installed.python.startsWith(cache));
    assert.equal(installed.protocol, 1);
    assert.equal(Object.keys(described.platforms).length, 7);
  } finally { await client.close(); }

  const markers = await readdir(join(cache, 'environments'));
  assert.ok(markers.length >= 1);
  const python = (await readFile(join(cache, 'environments', markers[0]), 'utf8')).trim();
  assert.ok(python.startsWith(cache), 'Must use private Python, not a host installation.');
  const probe = await exec(python, ['-I', '-X', 'utf8', '-c', 'import gherila, sys; print(sys.prefix); print(gherila.__file__)']);
  assert.ok(probe.stdout.split('\n').every(line => !line.trim() || line.startsWith(cache)));

  const offline = { ...env, GHERILA_OFFLINE: '1', HTTPS_PROXY: 'http://127.0.0.1:9', HTTP_PROXY: 'http://127.0.0.1:9' };
  const environments = await readdir(join(cache, 'envs'));
  const installed = await module.install({ env: offline });
  assert.equal(installed.python, python);
  assert.deepEqual(await readdir(join(cache, 'envs')), environments, 'Repeated install must reuse an environment.');
  const direct = await exec(installed.python, [...installed.args, '--describe']);
  assert.equal(JSON.parse(direct.stdout).protocol, 1);

  const entrypoint = process.env.GHERILA_TEST_CLIENT || join(root, 'bindings/javascript/index.js');
  const cli = join(resolve(entrypoint), '..', 'cli.js');
  const cliResult = await exec(process.execPath, [cli, 'install'], { env: { ...process.env, ...offline }, timeout: 30000 });
  assert.deepEqual(JSON.parse(cliResult.stdout), installed);
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
  const setup = await exec(command, [...args.slice(0, -1), 'install'], {
    env: { ...process.env, ...offline }, timeout: 30000,
  });
  assert.deepEqual(JSON.parse(setup.stdout), installed);
  const streamed = exec(command, args.slice(0, -1), {
    env: { ...process.env, ...offline }, timeout: 30000,
  });
  streamed.child.stdin.end('{"id":"launcher","op":"describe"}\n');
  const reply = JSON.parse((await streamed).stdout);
  assert.equal(reply.id, 'launcher');
  assert.equal(reply.result.protocol, 1);

  if (process.env.GHERILA_TEST_NATIVE === '1') {
    const build = join(directory, 'build');
    await exec('cmake', ['-S', join(root, 'examples/languages/native'), '-B', build], { timeout: 120000 });
    await exec('cmake', ['--build', build, '--config', 'Release'], { timeout: 120000 });
    const extension = process.platform === 'win32' ? '.exe' : '';
    const rust = join(build, 'bin', 'gherila-rust' + extension);
    await exec('rustc', [join(root, 'examples/languages/example.rs'), '-o', rust], { timeout: 120000 });
    const portable = join(directory, 'portable runtime ü');
    await cp(runtime, portable, { recursive: true });
    const nativeEnv = { ...process.env, ...offline,
      GHERILA_LAUNCHER: join(portable, process.platform === 'win32' ? 'gherila.ps1' : 'gherila.sh') };
    for (const name of ['gherila-c', 'gherila-cpp', 'gherila-rust']) {
      const program = join(build, 'bin', name + extension);
      const result = await exec(program, ['install'], { cwd: directory, env: nativeEnv, timeout: 30000 });
      assert.deepEqual(JSON.parse(result.stdout), installed, name + ' install');
      const described = await exec(program, ['--describe'], { cwd: directory, env: nativeEnv, timeout: 30000 });
      assert.equal(JSON.parse(described.stdout).protocol, 1, name + ' discovery');
      const response = exec(program, [], { cwd: directory, env: nativeEnv, timeout: 30000 });
      response.child.stdin.end('{"id":"native","op":"describe"}\n');
      const envelope = JSON.parse((await response).stdout);
      assert.equal(envelope.id, 'native');
      assert.equal(envelope.result.protocol, 1);
      assert.equal(Object.keys(envelope.result.platforms).length, 7);
      const empty = await mkdtemp(join(directory, 'offline-'));
      await assert.rejects(exec(program, ['install'], {
        cwd: directory, env: { ...nativeEnv, GHERILA_CACHE_DIR: empty }, timeout: 30000,
      }), error => error.code !== 0 && !error.stdout.trim() && /first setup needs internet/.test(error.stderr));
    }
  }
  await rm(directory, { recursive: true, force: true });
});
