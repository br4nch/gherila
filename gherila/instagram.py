from urllib.parse import urlparse
from re import compile
from random import uniform
from asyncio import (
  Semaphore,
  sleep
)

from .http import State
from typing import (
  Optional,
  Dict
)
from .exceptions import Error
from .models import (
  InstagramUser,
  InstagramStory,
  InstagramHighlight,
  InstagramMedia,
  InstagramComment,
  InstagramFollowerUser
)

INSTAGRAM_REGEX = compile(r"^(?:https?:\/\/)?(?:www\.)?instagram\.com\/(?:p|reel|tv)\/([a-zA-Z0-9_-]+)")

class Instagram:
  def __init__(
    self: "Instagram",
    csrf: str,
    session_id: str,
    proxy: str = None
  ):
    self.session = State()
    self.proxy = proxy
    self.headers = {
      "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 12_3_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Instagram 105.0.0.11.118 (iPhone11,8; iOS 12_3_1; en_US; en-US; scale=2.00; 828x1792; 165586599)",
      "Cookie": f"csrftoken={csrf}; sessionid={session_id}",
    }
    self._user_cache: Dict[str, InstagramUser] = {}

  async def _request(
    self: "Instagram",
    method: str,
    url: str,
    max_concurrent: int = 3,
    max_retries: int = 2,
    **kwargs
  ):
    async with Semaphore(max_concurrent):
      for a in range(max_retries):
        try:
          await sleep(uniform(0.5, 1.5))
          kwargs.setdefault("headers", self.headers)
          kwargs.setdefault("proxy", self.proxy)
          return await self.session.request(method, url, **kwargs)
        except Exception:
          raise

  async def get_user(self: "Instagram", username: str):
    """
    Get user information by username.

    Parameters
    ----------
    username : :class:`str`
      The username of the user to fetch the info.

    Returns
    -------
    :class:`InstagramUser`
      An InstagramUser object with the user info.
    """
    if username in self._user_cache:
      return self._user_cache[username]

    data = await self._request(
      "GET",
      f"https://i.instagram.com/api/v1/users/{username}/usernameinfo",
    )

    if not getattr(data, "user", None):
      raise Error(f"Can't find an user with the username `{username}`.")

    obj = InstagramUser(**data.user)
    self._user_cache[username] = obj
    return obj

  async def get_story(self: "Instagram", username: str, amount: Optional[int] = None):
    """
    Get the stories of a user by username.

    Parameters
    ----------
    username : :class:`str`
      The username of the user to fetch the stories.
    amount : Optional[:class:`int`]
      The amount of stories to fetch. If the amount is not given all stories will be fetched.

    Returns
    -------
    :class:`List[InstagramStory]`
      A list of InstagramStory objects with the user stories.
    """
    user_id = (await self.get_user(username)).pk
    data = (
      await self._request(
        "GET",
        f"https://i.instagram.com/api/v1/feed/user/{user_id}/story/",
      )
    ).get("reel", {})

    items = data.get("items", [])
    if amount:
      items = items[:amount]

    stories = []
    for story in items:
      if "video_versions" in story:
        story.video_url = max(
          story.video_versions,
          key=lambda x: x.height * x.width
        ).url

      if "image_versions2" in story:
        story.image_url = max(
          story.image_versions2.candidates,
          key=lambda x: x.height * x.width,
        ).url

      stories.append(story)

    return [InstagramStory(**s) for s in stories]

  async def get_highlights(self: "Instagram", username: str, amount: Optional[int] = None):
    """
    Get the highlights of a user by username.

    Parameters
    ----------
    username : :class:`str`
      The username of the user to fetch the highlights.
    amount : Optional[:class:`int`]
      The amount of highlights to fetch. If the amount is not given all highlights will be fetched.

    Returns
    -------
    :class:`List[InstagramHighlight]`
      A list of InstagramHighlight objects with the user highlights.
    """
    user_id = (await self.get_user(username)).pk
    data = await self._request(
      "GET",
      f"https://i.instagram.com/api/v1/highlights/{user_id}/highlights_tray/",
    )
    tray = data.get("tray", [])
    if amount:
      tray = tray[:amount]

    highlights = []
    for highlight in tray:
      highlight.id = highlight.id.split(":")[1]
      highlight.cover_media = highlight.cover_media.cropped_image_version.url

      highlights.append(highlight)

    return [InstagramHighlight(**h) for h in highlights]

  async def get_post(self: "Instagram", url: str, amount: Optional[int] = None):
    """
    Get the info about a post by url.

    Parameters
    ----------
    url : :class:`str`
      The url of the post to fetch it.
    amount : Optional[:class:`int`]
      The amount of images/videos to fetch. If the amount is not given all will be fetched.

    Returns
    -------
    :class:`List[InstagramMedia]`
      A list of InstagramMedia objects with the post images/videos.
    """
    if not INSTAGRAM_REGEX.match(url):
      raise Error("This is not a valid instagram post url.")

    char = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    code = [p for p in (urlparse(url).path).split("/") if p][1]
    media_id = sum(char.index(x) * (len(char) ** i) for i, x in enumerate(reversed(code)))

    data = await self._request(
      "GET",
      f"https://i.instagram.com/api/v1/media/{media_id}/info",
    )

    medias = []
    for media in data.get("items", []):
      if "carousel_media" in media:
        for slide in media.carousel_media:
          if "image_versions2" in slide:
            media.image_urls = [media_url.url for media_url in slide.image_versions2.candidates]

          if "video_versions" in slide:
            media.video_url = max(
              slide.video_versions,
              key=lambda x: x.height * x.width,
            ).url

      if "video_versions" in media:
        media.video_url = max(
          media.video_versions,
          key=lambda x: x.height * x.width,
        ).url

      if "image_versions2" in media:
        urls = [media_url.url for media_url in media.image_versions2.candidates]
        if amount:
          urls = urls[:amount]

        media.image_urls = urls
        media.thumbnail_url = max(
          media.image_versions2.candidates,
          key=lambda x: x.height * x.width,
        ).url

      medias.append(media)

    return [InstagramMedia(**m) for m in medias]

  async def get_comments(self: "Instagram", url: str, amount: Optional[int] = None):
    """
    Get the comments of a post by url.

    Parameters
    ----------
    url : :class:`str`
      The url of the post to fetch the comments from.
    amount : Optional[:class:`int`]
      The amount of comments to fetch. If the amount is not given all will be fetched.

    Returns
    -------
    :class:`List[InstagramComment]`
      A list of InstagramComment object with the post comments.
    """
    post = await self.get_post(url)
    data = await self._request(
      "GET",
      f"https://www.instagram.com/api/v1/media/{post[0].pk}/comments",
    )
    comments = data.get("comments", [])

    if amount:
      comments = comments[:amount]

    return [InstagramComment(**comment) for comment in comments]

  async def get_followers(self: "Instagram", username: str, amount: Optional[int] = None):
    """
    Get a user followers by username.

    Parameters
    ----------
    username : :class:`str`
      The username of the user to fetch the followers.
    amount : Optional[:class:`int`]
      The amount of followers to fetch. If the amount is not given all followers will be fetched.

    Returns
    -------
    :class:`List[InstagramFollowerUser]`
      A list of InstagramFollowerUser objects with the user followers.
    """
    user = await self.get_user(username)
    data = await self._request(
      "GET",
      f"https://i.instagram.com/api/v1/friendships/{user.pk}/followers/",
    )
    followers = []
    for f in data.get("users", []):
      followers.append(InstagramFollowerUser(**f))

    if amount:
      followers = followers[:amount]

    return followers

  async def get_following(self: "Instagram", username: str, amount: Optional[int] = None):
    """
    Get a user following by username.

    Parameters
    ----------
    username : :class:`str`
      The username of the user to fetch the following.
    amount : Optional[:class:`int`]
      The amount of following to fetch. If the amount is not given all following will be fetched.

    Returns
    -------
    :class:`List[InstagramFollowerUser]`
      A list of InstagramFollowerUser objects with the user following.
    """
    user = await self.get_user(username)
    data = await self._request(
      "GET",
      f"https://i.instagram.com/api/v1/friendships/{user.pk}/following/",
    )
    following = []
    for f in data.get("users", []):
      following.append(InstagramFollowerUser(**f))

    if amount:
      following = following[:amount]

    return following