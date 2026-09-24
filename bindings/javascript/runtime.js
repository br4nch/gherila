import { execFile, spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

/** Install private Python, Gherila and its dependencies, then exit the installer. */
export async function install({ env = {}, cwd, timeout = 300000, signal = new AbortController().signal } = {}) {
  if (!Number.isFinite(timeout) || timeout <= 0 || timeout > 2147483647) {
    throw new TypeError('Install timeout must be between 0 and 2147483647 milliseconds.');
  }
  if (signal.aborted) throw new Error('Gherila automatic setup was cancelled.');
  const packaged = new URL('./runtime/', import.meta.url);
  const root = existsSync(new URL('uv-version', packaged)) ? packaged : new URL('../../runtime/', import.meta.url);
  const windows = process.platform === 'win32';
  const launcher = fileURLToPath(new URL(windows ? 'gherila.ps1' : 'gherila.sh', root));
  const command = windows ? 'powershell.exe' : '/bin/sh';
  const args = windows
    ? ['-NoLogo', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', launcher, 'install']
    : [launcher, 'install'];
  return new Promise((resolve, reject) => {
    let stopped = false;
    let timer;
    const stop = () => {
      if (stopped) return;
      stopped = true;
      if (child.pid) {
        if (windows) {
          // Kill only this setup process and its children, including uv downloads.
          const killer = spawn('taskkill.exe', ['/PID', String(child.pid), '/T', '/F'], { stdio: 'ignore', windowsHide: true });
          killer.on('error', () => child.kill());
        } else {
          try { process.kill(-child.pid, 'SIGTERM'); } catch { child.kill(); }
        }
      }
      reject(new Error(signal.aborted ? 'Gherila automatic setup was cancelled.' : 'Gherila automatic setup timed out.'));
    };
    const child = execFile(command, args, {
      cwd, env: { ...process.env, ...env }, detached: !windows, windowsHide: true, maxBuffer: 1024 * 1024, encoding: 'utf8',
    }, (error, stdout, stderr) => {
      clearTimeout(timer);
      signal.removeEventListener('abort', stop);
      if (error) {
        reject(new Error(`Gherila automatic setup failed: ${stderr.trim() || error.message}`, { cause: error }));
      } else {
        try {
          const result = JSON.parse(stdout);
          if (result.protocol !== 1 || typeof result.python !== 'string' || !result.python ||
              !Array.isArray(result.args) || !result.args.every(arg => typeof arg === 'string')) {
            throw new Error('Invalid runtime report.');
          }
          resolve(result);
        } catch (cause) {
          reject(new Error('Gherila automatic setup returned an invalid runtime report.', { cause }));
        }
      }
    });
    timer = setTimeout(stop, timeout);
    signal.addEventListener('abort', stop, { once: true });
    if (signal.aborted) stop();
    child.stdin.end();
    child.stderr.on('data', data => process.stderr.write(data));
  });
}
