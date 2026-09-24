import assert from 'node:assert/strict';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { Gherila, GherilaError } from '../index.js';

const worker = fileURLToPath(new URL('../../../tests/fixture_worker.py', import.meta.url));
function fixture(options = {}) { return new Gherila({ pythonArgs: [worker], ...options }); }

test('all providers, keyword calls, concurrent correlation and exact IDs', async () => {
  const api = fixture();
  try {
    assert.equal(Object.keys((await api.describe()).platforms).length, 7);
    const github = await api.create('github');
    const order = [];
    const results = await Promise.all(['slow', 'demo'].map(username =>
      github.get_user({ username }).then(result => { order.push(result.login); return result; })));
    assert.deepEqual(order, ['demo', 'slow']);
    assert.equal(results[0].login, 'slow');
    assert.equal(results[1].id, 9223372036854775807n);
    assert.equal(results[1].name, 'Ștefan 日本語');
    assert.equal((await github.call('get_user', {}, ['demo'])).login, 'demo');
    await assert.rejects(github.call('__init__'), error => error instanceof GherilaError && error.code === 'unknown_method');
    await assert.rejects(github.get_user({ username: 'failure' }), error =>
      error.type === 'RuntimeError' && !error.message.includes('secret-cookie'));
    await github.close();
    await assert.rejects(github.get_user({ username: 'demo' }), /closed/);
  } finally { await api.close(); }
  await api.close();
  await assert.rejects(api.describe());
});

test('real TikTok model roundtrip and binary download', async () => {
  const api = fixture();
  try {
    const tiktok = await api.create('tiktok', { ttwid: 'test', msToken: 'test' });
    const video = await tiktok.get_video({ url: 'https://www.tiktok.com/@demo/video/123' });
    assert.equal(video.id, 9223372036854775806n);
    assert.equal(video.author.id, 9223372036854775807n);
    const result = await tiktok.download_video({ video, path: null });
    assert.ok(Buffer.isBuffer(result));
    assert.deepEqual(result, Buffer.from([0, 255, ...Buffer.from('fixture-video\n')]));
  } finally { await api.close(); }
});

test('worker startup failures reject pending calls and close', async () => {
  const api = new Gherila({ python: 'gherila-nonexistent-python-executable' });
  await assert.rejects(api.describe(), /ENOENT/);
  await api.close();
});

test('queued work drains on close and invalid numeric inputs are rejected', async () => {
  const api = fixture();
  const github = await api.create('github');
  await assert.rejects(github.get_user({ username: 2 ** 63 }), /BigInt/);
  const result = github.get_user({ username: 'slow' });
  const closed = api.close();
  assert.equal((await result).login, 'slow');
  await closed;
});

test('provider timeout is surfaced with its error code', async () => {
  const api = fixture({ callTimeout: 0.02 });
  try {
    const github = await api.create('github');
    await assert.rejects(github.get_user({ username: 'slow' }), error => error.code === 'timeout');
    assert.equal((await github.get_user({ username: 'demo' })).login, 'demo');
  } finally { await api.close(); }
});

test('pending limit provides backpressure without losing earlier requests', async () => {
  const api = fixture({ maxPending: 1 });
  try {
    const github = await api.create('github');
    const first = github.get_user({ username: 'slow' });
    await assert.rejects(github.get_user({ username: 'demo' }), /Too many pending/);
    assert.equal((await first).login, 'slow');
  } finally { await api.close(); }
});
