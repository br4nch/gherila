# Changelog

## 1.4.0 (unreleased)

- Require Python 3.10+ to match the actual annotation syntax.
- Reuse HTTP sessions, bound response sizes, retry transient GET/HEAD failures,
  and expose structured errors. Clients must now be closed explicitly or used
  as async context managers; caller-supplied aiohttp sessions remain caller-owned.
- Make orjson/selectolax optional and add a portable HTML parser.
- Bound user caches by size/TTL and coalesce concurrent lookups.
- Fix GitHub list handling and pagination; add token support and async iterators.
- Fix TikTok video parsing and stream downloads through an atomic temporary file.
- Preserve Instagram carousel slides and stop repeated pagination cursors.
- Validate platform URLs, encode Reddit queries, handle missing scripts/tweets,
  and accept nullable GitHub display names.
- Add deterministic regression tests and cross-platform CI.

### Migration notes

- Existing constructors still accept their original positional credentials.
  Reuse clients with `async with` or call `await client.close()`.
- `get_repos()` and `get_commits()` now fetch all pages by default; pass `limit`
  or use their async iterators to bound work.
- Instagram carousel results contain one `InstagramMedia` per slide; `amount`
  limits slides. Each item selects its best image/video; `image_urls` no longer
  enumerates every resolution. Instagram media `id` is a string because the
  upstream identifier can contain an underscore; `pk` remains an integer.
- Empty Brave searches return an empty result model instead of raising `Error`.
- Passing zero for a collection size returns an empty result without a request;
  negative values raise `ValueError`.
- The standard HTML parser's Brave search descriptions may be empty. Install
  `gherila[fast]` for the selectolax description parser.
