#!/usr/bin/env node
import { install } from './runtime.js';

const args = process.argv.slice(2);
if (args.length === 1 && args[0] === 'install') {
  const controller = new AbortController();
  const cancel = () => controller.abort();
  process.once('SIGINT', cancel);
  process.once('SIGTERM', cancel);
  try {
    console.log(JSON.stringify(await install({ signal: controller.signal })));
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  } finally {
    process.removeListener('SIGINT', cancel);
    process.removeListener('SIGTERM', cancel);
  }
} else {
  console.error('Usage: gherila-runtime install\nInstalls private Python, Gherila and dependencies; prints a JSON runtime report.');
  if (!(args.length === 1 && ['--help', '-h'].includes(args[0]))) process.exitCode = 2;
}
