/// <reference types="node" />

export type Platform = 'brave' | 'github' | 'instagram' | 'reddit' | 'snapchat' | 'tiktok' | 'twitter';
export type Value = null | boolean | number | bigint | string | Uint8Array | Value[] | { [key: string]: Value };
export type Fields = { [key: string]: Value };
export type Model = { [key: string]: Value };
export interface InstallOptions {
  cwd?: string;
  env?: Record<string, string>;
  /** Setup timeout in milliseconds. Default: 300000. */
  timeout?: number;
  /** Cancels setup and its child processes. */
  signal?: AbortSignal;
}
export interface Installation {
  /** Absolute path to the prepared private Python executable. */
  python: string;
  /** Arguments for starting the JSON worker using this executable. */
  args: string[];
  protocol: 1;
}
/** Prepare private Python, Gherila and all dependencies without starting a worker. */
export function install(options?: InstallOptions): Promise<Installation>;
export interface Options {
  /** Use an existing Python with Gherila installed; bypasses automatic setup. */
  python?: string;
  /** Automatically set up a private Python and Gherila when python is omitted. Default: true. */
  autoInstall?: boolean;
  /** First-run setup timeout in milliseconds. Default: 300000. */
  setupTimeout?: number;
  pythonArgs?: string[];
  cwd?: string;
  env?: Record<string, string>;
  /** Response timeout after runtime setup, including queue time, in milliseconds. Default: 65000. */
  timeout?: number;
  /** Python provider call timeout in seconds. Default: 60. */
  callTimeout?: number;
  concurrency?: number;
  maxPending?: number;
}
export interface PlatformOptions {
  brave: Record<string, never>;
  github: Record<string, never>;
  instagram: { csrf: string; session_id: string; proxy?: string[] | null; max_concurrent?: number };
  reddit: Record<string, never>;
  snapchat: Record<string, never>;
  tiktok: { ttwid: string; msToken: string };
  twitter: { auth_token: string; ct0: string; crsf: string; authorization: string };
}
export interface Parameter {
  name: string;
  required: boolean;
  default?: Value;
  schema?: Record<string, unknown>;
}
export interface Description {
  protocol: 1;
  platforms: Record<Platform, { options: Parameter[]; methods: Record<string, Parameter[]> }>;
}
export class GherilaError extends Error {
  code: string;
  type?: string;
  constructor(error: { code: string; message: string; type?: string });
}
export class Client {
  constructor(bridge: Gherila, id: string);
  call<T = Value>(method: string, kwargs?: Fields, args?: Value[]): Promise<T>;
  close(): Promise<void>;
}
export interface BraveClient extends Client {
  get_images(params: { query: string; safe?: boolean; limit?: number }): Promise<Model>;
  get_search(params: { query: string; safe?: boolean; limit?: number }): Promise<Model>;
}
export interface GitHubClient extends Client {
  get_user(params: { username: string }): Promise<Model>;
  get_repo(params: { username: string; repo_name: string }): Promise<Model>;
  get_repos(params: { username: string }): Promise<Model[]>;
  get_commits(params: { username: string; repository_name: string }): Promise<Model[]>;
}
export interface InstagramClient extends Client {
  get_user(params: { username: string }): Promise<Model>;
  get_story(params: { username: string; amount?: number | null }): Promise<Model[]>;
  get_highlights(params: { username: string; amount?: number | null }): Promise<Model[]>;
  get_post(params: { url: string; amount?: number | null }): Promise<Model[]>;
  get_comments(params: { url: string; amount?: number | null }): Promise<Model[]>;
  get_followers(params: { username: string; amount?: number | null }): Promise<Model[]>;
  get_following(params: { username: string; amount?: number | null }): Promise<Model[]>;
}
export interface RedditClient extends Client {
  get_user(params: { username: string }): Promise<Model>;
  get_subreddit(params: { name: string }): Promise<Model>;
  get_subreddit_posts(params: { name: string; sort?: string; limit?: number }): Promise<Model[]>;
  get_post(params: { url: string }): Promise<Model>;
  search(params: { query: string; sort?: string; limit?: number }): Promise<Model[]>;
  get_comments(params: { url: string }): Promise<Model[]>;
}
export interface SnapchatClient extends Client {
  get_user(params: { username: string }): Promise<Model>;
  get_story(params: { username: string }): Promise<Model>;
  get_highlights(params: { username: string }): Promise<Model>;
}
export interface TikTokClient extends Client {
  get_user(params: { username: string }): Promise<Model>;
  get_video(params: { url: string }): Promise<Model>;
  download_video(params: { video: Model; path: null }): Promise<Buffer>;
  download_video(params: { video: Model; path: string }): Promise<string>;
  download_video(params: { video: Model; path: string | null }): Promise<Buffer | string>;
}
export interface TwitterClient extends Client {
  get_user(params: { username: string }): Promise<Model>;
  get_tweet(params: { url: string }): Promise<Model>;
  get_user_tweets(params: { username: string }): Promise<Model[]>;
}
export interface Clients {
  brave: BraveClient;
  github: GitHubClient;
  instagram: InstagramClient;
  reddit: RedditClient;
  snapchat: SnapchatClient;
  tiktok: TikTokClient;
  twitter: TwitterClient;
}
export class Gherila {
  constructor(options?: Options);
  request<T = Value>(request: Fields): Promise<T>;
  describe(): Promise<Description>;
  create<P extends Platform>(platform: P, ...options: P extends 'instagram' | 'tiktok' | 'twitter'
    ? [options: PlatformOptions[P]] : [options?: PlatformOptions[P]]): Promise<Clients[P]>;
  close(): Promise<void>;
}
