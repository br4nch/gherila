from re import search
from orjson import loads
from munch import munchify

from .http import State
from .exceptions import Error
from .models import (
  TikTokUser,
  TikTokStats
)

class TikTok:
  def __init__(self: "TikTok"):
    self.session = State()
  
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
    )
    result = search(r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>', data)
    raw = loads(result.group(1))["__DEFAULT_SCOPE__"]["webapp.user-detail"]
    loaded = munchify(raw)

    if loaded.statusCode == 10221:
      raise Error(f"Can't find an user with the username `@{username}`.")

    stats = TikTokStats(**loaded.userInfo.stats)
    loaded.userInfo.user.stats = stats
    return TikTokUser(**loaded.userInfo.user)