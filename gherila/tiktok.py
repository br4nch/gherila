import aiofiles

from pathlib import Path
from io import BytesIO
from re import compile
from orjson import loads
from munch import munchify
from typing import Dict

from .http import State
from .exceptions import Error
from .models import (
  TikTokUser,
  TikTokStats,
  TikTokVideo
)

TIKTOK_REGEX = compile(r"^.*https:\/\/(?:m|www|vm)?\.?tiktok\.com\/((?:.*\b(?:(?:v|embed|photo|video|t)\/|\?shareId=|\&item_id=)(\d+))|\w+)")
REHYDRATION_REGEX = compile(r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>')

class TikTok:
  def __init__(self: "TikTok", ttwid: str, msToken: str):
    self.session = State()
    self.headers = {
      "Cookie": f"ttwid={ttwid}; msToken={msToken}",
      "Referer": "https://www.tiktok.com/",
      "Sec-Fetch-Dest": "document",
      "Sec-Fetch-Mode": "navigate",
      "Sec-Fetch-Site": "same-origin",
      "Sec-Fetch-User": "?1",
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    self._user_cache: Dict[str, TikTokUser] = {}

  async def get_user(self: "TikTok", username: str):
    """
    Get user information by username.

    Parameters
    ----------
    username : :class:`str`
      The username of the user to fetch the info.

    Returns
    -------
    :class:`TikTokUser`
      A TikTokUser object with the user information.
    """
    if username in self._user_cache:
      return self._user_cache[username]

    data = await self.session.request(
      "GET",
      f"https://www.tiktok.com/@{username}",
      headers=self.headers,
    )
    result = REHYDRATION_REGEX.search(data)
    raw = loads(result.group(1))["__DEFAULT_SCOPE__"]["webapp.user-detail"]
    loaded = munchify(raw)

    if loaded.statusCode == 10221:
      raise Error(f"Can't find an user with the username `@{username}`.")

    stats = TikTokStats(**loaded.userInfo.stats)
    loaded.userInfo.user.stats = stats
    obj = TikTokUser(**loaded.userInfo.user)
    self._user_cache[username] = obj
    return obj

  async def get_video(self: "TikTok", url: str):
    """
    Get video data based on the given url.

    Parameters
    ----------
    url : :class:`str`
      The tiktok video url.

    Returns
    -------
    :class:`TikTokVideo`
      A TikTokVideo object containing the video information.
    """
    if not TIKTOK_REGEX.match(url):
      raise Error("This is not a valid tiktok url.")

    data = await self.session.request(
      "GET",
      url,
      headers=self.headers,
    )
    result = REHYDRATION_REGEX.search(data)
    loaded = munchify(loads(result.group(1))["__DEFAULT_SCOPE__"]["webapp.video-detail"])

    r = loaded.itemInfo.itemStruct
    user = await self.get_user(r.author.uniqueId)
    r.author = user
    r.url = r.video.playAddr
    return TikTokVideo(**r)

  async def download_video(self: "TikTok", video: TikTokVideo, path: str | Path | None) -> Path | BytesIO:
    """
    Download a tiktok video.

    Parameters
    ----------
    video : :class:`TikTokVideo`
      The TikTokVideo object to download.
    path : :class:`str` | :class:`Path` | None
      The path to save the video. If None, it will return a BytesIO object.

    Returns
    -------
    :class:`Path` | :class:`BytesIO`
      The path to the downloaded video or a BytesIO object if path is None.
    """
    video_data = await self.session.request(
      "GET",
      video.url,
      headers=self.headers,
    )

    if path:
      save_path = Path(path)

      async with aiofiles.open(save_path, "wb") as f:
        await f.write(video_data)

      return save_path
    else:
      return BytesIO(video_data)