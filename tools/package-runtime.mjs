// Bundle the same Python source into npm or a portable launcher directory.
// Node is needed only to assemble the bundle, never to use it from other languages.
import { cp, mkdir, readdir, rm } from 'node:fs/promises';
import { resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));
const output = process.argv[2] ? resolve(process.argv[2]) : resolve(root, 'bindings/javascript/runtime');
const sourceRuntime = resolve(root, 'runtime');
const sourceCore = resolve(root, 'gherila');
if (output === resolve(root) || [sourceRuntime, sourceCore].some(path => output === path || output.startsWith(path + sep))) {
  throw new Error('Choose an output directory outside the source runtime and Python package.');
}
await mkdir(output, { recursive: true });
for (const file of await readdir(resolve(root, 'runtime'))) {
  await cp(resolve(root, 'runtime', file), resolve(output, file), { recursive: true });
}
// Replace only the generated core, leaving any unrelated output files untouched.
await rm(resolve(output, 'core'), { recursive: true, force: true });
await mkdir(resolve(output, 'core/gherila'), { recursive: true });
for (const file of ['pyproject.toml', 'setup.py', 'requirements.txt', 'README.md', 'LICENSE']) {
  await cp(resolve(root, file), resolve(output, 'core', file));
}
for (const file of await readdir(resolve(root, 'gherila'))) {
  if (file.endsWith('.py')) await cp(resolve(root, 'gherila', file), resolve(output, 'core/gherila', file));
}
console.error(`Bundled Gherila runtime: ${output}`);
