from re import compile
from orjson import loads
from munch import munchify, DefaultMunch

from .http import State
from .exceptions import Error
from .models import SnapUser

SNAP_REGEX = compile(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>')

class Snapchat:
  def __init__(self: "Snapchat"):
    self.session = State()
    self.headers = {
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    }
    self._user_cache = {}

  async def get_user(self: "Snapchat", username: str):
    """
    Get user information by username.

    Parameters
    ----------
    username : :class:`str`
      The username of the user to fetch the info.
    
    Returns
    -------
    :class:`SnapUser`
      A SnapUser object with the user information.
    """
    if username in self._user_cache:
      return self._user_cache[username]

    data = await self.session.request(
      "GET",
      f"https://story.snapchat.com/add/{username}",
      headers=self.headers,
    )
    d = SNAP_REGEX.search(data)
    munch = loads(d.group(1))["props"]["pageProps"]
    error = DefaultMunch(None, munch)
    loaded = munchify(munch)

    if not error.pageMetadata:
      raise Error(f"Can't find an user with the username `@{username}`.")

    user = {
      **loaded.userProfile,
      "spotlightHighlights": loaded.spotlightHighlights,
      "story": loaded.story,
    }
    snap_user = SnapUser(
      **user,
      username=username,
      url=f"https://story.snapchat.com/add/{username}"
    )
    self._user_cache[username] = snap_user
    return snap_user