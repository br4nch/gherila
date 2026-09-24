"""Offline upstream fixtures used by the real Python and Node subprocess tests."""

import asyncio
import json
import sys

from munch import DefaultMunch

from gherila.http import State

USER = {
  "id": 9223372036854775807, "uniqueId": "demo", "nickname": "Demo",
  "signature": "Test", "avatarLarger": "https://example.com/avatar.jpg",
  "verified": False, "privateAccount": False,
}
STATS = {"followingCount": 1, "followerCount": 2, "heartCount": 3, "videoCount": 4}
VIDEO = {
  "id": 9223372036854775806, "desc": "Test video", "createTime": 1700000000,
  "stats": {"diggCount": 1, "shareCount": 2, "commentCount": 3, "playCount": 4, "collectCount": 5},
  "author": USER, "video": {"playAddr": "https://example.com/video.mp4"},
}
MEDIA = b"\x00\xfffixture-video\n"


async def request(self, method, url, **kwargs):
  if url.startswith("https://api.github.com/users/"):
    username = url.rsplit("/", 1)[1]
    if username == "slow":
      await asyncio.sleep(0.15)
    if username == "failure":
      raise RuntimeError("secret-cookie-must-not-leak")
    if username == "print":
      print("provider diagnostic")
    return DefaultMunch.fromDict({
      "id": 9223372036854775807, "login": username,
      "avatar_url": "https://example.com/avatar.jpg", "url": url,
      "name": "Ștefan 日本語", "type": "User", "public_repos": 1,
      "followers": 2, "following": 3, "created_at": "2020-01-01T00:00:00Z",
    })
  if url == "https://example.com/video.mp4":
    return MEDIA
  if "tiktok.com" in url:
    scope = ({"webapp.video-detail": {"itemInfo": {"itemStruct": VIDEO}}}
             if "/video/" in url else
             {"webapp.user-detail": {"statusCode": 0, "userInfo": {"user": USER, "stats": STATS}}})
    return '<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__">' + json.dumps({"__DEFAULT_SCOPE__": scope}) + '</script>'
  raise AssertionError(f"Unmocked upstream URL: {url}")


if __name__ == "__main__":
  # The JS SDK appends its normal Python module arguments after this script.
  if sys.argv[1:4] == ["-u", "-m", "gherila"]:
    sys.argv = [sys.argv[0], *sys.argv[4:]]
  State.request = request
  from gherila.bridge import main
  main()
