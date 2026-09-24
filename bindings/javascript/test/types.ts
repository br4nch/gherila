import { Gherila, install, type Installation, type Model } from '../index.js';

async function example() {
  const runtime: Installation = await install({ timeout: 300000, signal: new AbortController().signal });
  const executable: string = runtime.python;
  // @ts-expect-error Install timeout must be numeric.
  await install({ timeout: 'slow' });
  const api = new Gherila();
  try {
    const github = await api.create('github');
    const user: Model = await github.get_user({ username: 'octocat' });
    const tiktok = await api.create('tiktok', { ttwid: 'test', msToken: 'test' });
    const video = await tiktok.get_video({ url: 'https://www.tiktok.com/@test/video/123' });
    const bytes: Buffer = await tiktok.download_video({ video, path: null });
    const file: string = await tiktok.download_video({ video, path: 'video.mp4' });
    // @ts-expect-error Authenticated providers require options.
    await api.create('instagram');
    // @ts-expect-error Wrong argument name.
    await github.get_user({ name: 'octocat' });
    // @ts-expect-error Unknown provider.
    await api.create('unknown');
    return { user, bytes, file, executable };
  } finally { await api.close(); }
}

void example; // Type-check only; do not contact any provider.
