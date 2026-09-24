import { Gherila } from '../../bindings/javascript/index.js';

const api = new Gherila();
try {
  const github = await api.create('github');
  const user = await github.get_user({ username: 'octocat' });
  console.log(user);
} finally {
  await api.close();
}
