from re import search
from orjson import loads
from munch import munchify

from .http import State
from .exceptions import Error
from .models import (
  TikTokUser,
  TikTokStats,
  TikTokVideo
)

class TikTok:
  def __init__(self: "TikTok"):
    self.session = State()
    self.headers = {
      "Referer": "https://www.tiktok.com/",
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
  
  async def get_user(self: "TikTok", username: str):
    """
    Get use information by username.

    Parameters
    ----------
    username: :class:`str`
      The username of the user to fetch the info.
    
    Returns
    -------
    :class:`TikTokUser`
      A TikTokUser object with the user info.
    """
    data = await self.session.request(
      "GET",
      f"https://www.tiktok.com/@{username}",
      headers=self.headers,
    )
    result = search(r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>', data)
    raw = loads(result.group(1))["__DEFAULT_SCOPE__"]["webapp.user-detail"]
    loaded = munchify(raw)

    if loaded.statusCode == 10221:
      raise Error(f"Can't find an user with the username `@{username}`.")

    stats = TikTokStats(**loaded.userInfo.stats)
    loaded.userInfo.user.stats = stats
    return TikTokUser(**loaded.userInfo.user)

  async def get_video(self: "TikTok", url: str):
    """
    Get video data based on the given url.

    Parameters
    ----------
    url: :class:`str`
      The tiktok video url.
    """
    data = await self.session.request(
      "GET",
      url,
      headers=self.headers,
    )
    result = search(r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>', data)
    loaded = munchify(loads(result.group(1))["__DEFAULT_SCOPE__"]["webapp.video-detail"])

    if loaded.statusCode == 10204:
      raise Error(f"This is not a valid tiktok url.")

    r = loaded.itemInfo.itemStruct
    user = await self.get_user(r.author.uniqueId)
    r.author = user
    r.url = r.video.playAddr
    return TikTokVideo(**r)