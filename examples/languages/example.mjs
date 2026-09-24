import { Gherila, install } from '../../bindings/javascript/index.js';

if (process.argv.length > 2) {
  if (process.argv.length !== 3 || process.argv[2] !== 'install') throw new Error('Expected install or no arguments.');
  console.log(JSON.stringify(await install()));
} else {
  const api = new Gherila();
  try {
    const github = await api.create('github');
    const user = await github.get_user({ username: 'octocat' });
    console.log(user);
  } finally {
    await api.close();
  }
}
