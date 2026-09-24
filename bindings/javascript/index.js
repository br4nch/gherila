import { spawn } from 'node:child_process';
import { createInterface } from 'node:readline';

export class GherilaError extends Error {
  constructor({ code, message, type }) {
    super(message);
    this.name = 'GherilaError';
    this.code = code;
    this.type = type;
  }
}

function encode(value) {
  if (typeof value === 'bigint') return { $gherila: 'int', value: String(value) };
  if (Buffer.isBuffer(value) || value instanceof Uint8Array) {
    return { $gherila: 'bytes', value: Buffer.from(value).toString('base64') };
  }
  if (Array.isArray(value)) return value.map(encode);
  if (value !== null && typeof value === 'object') {
    if (Object.getPrototypeOf(value) !== Object.prototype && Object.getPrototypeOf(value) !== null) {
      throw new TypeError('Arguments must be JSON values, BigInts or byte buffers.');
    }
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, encode(item)]));
  }
  if (typeof value === 'number' && (!Number.isFinite(value) || Number.isInteger(value) && !Number.isSafeInteger(value))) {
    throw new TypeError('Use BigInt for integers outside the safe range.');
  }
  if (value === null || ['string', 'number', 'boolean'].includes(typeof value)) return value;
  throw new TypeError('Arguments must be JSON values, BigInts or byte buffers.');
}

function decode(value) {
  if (Array.isArray(value)) return value.map(decode);
  if (value !== null && typeof value === 'object') {
    if (Object.keys(value).length === 2 && typeof value.value === 'string') {
      if (value.$gherila === 'int') return BigInt(value.value);
      if (value.$gherila === 'bytes') return Buffer.from(value.value, 'base64');
    }
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, decode(item)]));
  }
  return value;
}

/** One local Python worker, shared by all provider clients. */
export class Gherila {
  #process;
  #pending = new Map();
  #sequence = 0;
  #clientSequence = 0;
  #timeout;
  #maxPending;
  #ended;
  #closing = false;
  #failure;
  #closePromise;

  constructor({
    python = process.env.GHERILA_PYTHON || (process.platform === 'win32' ? 'python' : 'python3'),
    pythonArgs = [], cwd, env = {}, timeout = 65000, callTimeout = 60,
    concurrency = 8, maxPending = 256,
  } = {}) {
    if (!Number.isFinite(timeout) || timeout <= 0 || !Number.isFinite(callTimeout) || callTimeout <= 0 ||
        !Number.isInteger(concurrency) || concurrency < 1 || !Number.isInteger(maxPending) || maxPending < 1) {
      throw new TypeError('Timeouts, concurrency and maxPending must be positive.');
    }
    this.#timeout = timeout;
    this.#maxPending = maxPending;
    this.#process = spawn(python, [...pythonArgs, '-u', '-m', 'gherila',
      '--concurrency', String(concurrency), '--timeout', String(callTimeout)], {
      cwd, env: { ...process.env, ...env, PYTHONIOENCODING: 'utf-8' },
      stdio: ['pipe', 'pipe', 'inherit'], windowsHide: true, shell: false,
    });
    this.#ended = new Promise(resolve => {
      this.#process.once('close', (code, signal) => {
        this.#fail(new Error(`Gherila worker exited (${signal || code}).`));
        resolve();
      });
    });
    this.#process.on('error', error => this.#fail(error));
    this.#process.stdin.on('error', error => this.#fail(error));
    this.#process.stdout.on('error', error => this.#fail(error));
    const lines = createInterface({ input: this.#process.stdout, crlfDelay: Infinity });
    lines.on('line', line => {
      try {
        const response = JSON.parse(line);
        if (!response || response.version !== 1 || typeof response.id !== 'string' ||
            Object.hasOwn(response, 'result') === Object.hasOwn(response, 'error')) {
          throw new Error('Invalid Gherila response.');
        }
        const pending = this.#pending.get(response.id);
        if (!pending) return; // A response may arrive after its caller timed out.
        const error = response.error ? new GherilaError(response.error) : null;
        const result = error ? undefined : decode(response.result);
        clearTimeout(pending.timer);
        this.#pending.delete(response.id);
        if (error) pending.reject(error);
        else pending.resolve(result);
      } catch (error) {
        this.#fail(error);
        this.#process.kill();
      }
    });
  }

  #fail(error) {
    this.#failure ||= error;
    for (const pending of this.#pending.values()) {
      clearTimeout(pending.timer);
      pending.reject(error);
    }
    this.#pending.clear();
  }

  async request(request) {
    if (this.#failure) throw this.#failure;
    if (this.#closing) throw new Error('Gherila is closed.');
    if (this.#pending.size >= this.#maxPending) throw new Error('Too many pending Gherila requests.');
    const id = String(++this.#sequence);
    const line = JSON.stringify(encode({ ...request, version: 1, id })) + '\n';
    if (Buffer.byteLength(line) > 8 * 1024 * 1024) throw new Error('Gherila requests must fit in 8 MiB.');
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.#pending.delete(id);
        reject(new GherilaError({ code: 'timeout', message: 'Timed out waiting for the local Gherila worker.' }));
      }, this.#timeout);
      this.#pending.set(id, { resolve, reject, timer });
      this.#process.stdin.write(line, error => { if (error) this.#fail(error); });
    });
  }

  describe() {
    return this.request({ op: 'describe' });
  }

  async create(platform, options = {}) {
    const id = `client-${++this.#clientSequence}`;
    await this.request({ op: 'create', client: id, platform, options });
    return new Proxy(new Client(this, id), {
      get(target, name) {
        if (name in target) {
          const value = Reflect.get(target, name);
          return typeof value === 'function' ? value.bind(target) : value;
        }
        // A provider must not accidentally become a Promise/thenable.
        if (typeof name !== 'string' || name === 'then' || name.startsWith('_')) return undefined;
        return (kwargs = {}) => target.call(name, kwargs);
      },
    });
  }

  close() {
    if (this.#closePromise) return this.#closePromise;
    this.#closing = true;
    this.#process.stdin.end();
    this.#closePromise = (async () => {
      const timer = setTimeout(() => this.#process.kill(), 5000);
      try { await this.#ended; }
      finally { clearTimeout(timer); }
    })();
    return this.#closePromise;
  }
}

export class Client {
  #bridge;
  #id;
  #closed = false;

  constructor(bridge, id) {
    this.#bridge = bridge;
    this.#id = id;
  }

  call(method, kwargs = {}, args = []) {
    if (this.#closed) return Promise.reject(new Error('This Gherila client is closed.'));
    return this.#bridge.request({ op: 'call', client: this.#id, method, kwargs, args });
  }

  async close() {
    if (this.#closed) return;
    this.#closed = true;
    await this.#bridge.request({ op: 'close', client: this.#id });
  }
}
