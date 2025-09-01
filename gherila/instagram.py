from urllib.parse import urlparse

from .http import State
from typing import Optional
from .exceptions import Error
from .models import (
  InstagramUser,
  InstagramStory,
  InstagramHighlight,
  InstagramMedia
)

class Instagram:
  def __init__(self: "Instagram", csrf: str, session_id: str):
    self.session = State()
    self.headers = {
      "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 12_3_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Instagram 105.0.0.11.118 (iPhone11,8; iOS 12_3_1; en_US; en-US; scale=2.00; 828x1792; 165586599)",
      "Cookie": f"csrftoken={csrf}; sessionid={session_id}",
    }

  async def get_user(self: "Instagram", username: str):
    """
    Get user information by username.

    Parameters
    ----------
    username: :class:`str`
      The username of the user to fetch the info.
    
    Returns
    -------
    :class:`InstagramUser`
      An InstagramUser object with the user info.
    """
    data = await self.session.request(
      "GET",
      f"https://i.instagram.com/api/v1/users/{username}/usernameinfo",
      headers=self.headers,
    )

    if not data.user:
      raise Error(f"Can't find an user with the username `{username}`.")

    return InstagramUser(**data.user)

  async def get_story(self: "Instagram", username: str, amount: Optional[int] = None):
    """
    Get the stories of a user by username.

    Parameters
    ----------
    username: :class:`str`
      The username of the user to fetch the stories.
    amount: Optional[:class:`int`]
      The amount of stories to fetch. If the amount is not given all stories will be fetched.
    
    Returns
    -------
    :class:`List[InstagramStory]`
      A list of InstagramStory objects with the user stories.
    """
    user_id = (await self.get_user(username)).pk
    data = (await self.session.request(
      "GET",
      f"https://i.instagram.com/api/v1/feed/user/{user_id}/story/",
      headers=self.headers,
    )).get("reel", {})

    stories = []
    for story in data.get("items", []):
      if "video_versions" in story:
        story.video_url = sorted(
          story.video_versions,
          key=lambda x: x.height * x.width
        )[-1].url
      
      if "image_versions2" in story:
        story.image_url = sorted(
          story.image_versions2.candidates,
          key=lambda x: x.height * x.width,
        )[-1].url

      stories.append(story)

    if amount:
      stories = stories[:amount]

    return [InstagramStory(**s) for s in stories]

  async def get_highlights(self: "Instagram", username: str, amount: Optional[int] = None):
    """
    Get the highlights of a user by username.

    Parameters
    ----------
    username: :class:`str`
      The username of the user to fetch the highlights.
    amount: Optional[:class:`int`]
      The amount of highlights to fetch. If the amount is not given all highlights will be fetched.
    
    Returns
    -------
    :class:`List[InstagramHighlight]`
      A list of InstagramHighlight objects with the user highlights.
    """
    user_id = (await self.get_user(username)).pk
    data = await self.session.request(
      "GET",
      f"https://i.instagram.com/api/v1/highlights/{user_id}/highlights_tray/",
      headers=self.headers,
    )
    highlights = []
    for highlight in data.get("tray", []):
      highlight.id = highlight.id.split(":")[1]
      highlight.cover_media = highlight.cover_media.cropped_image_version.url

      highlights.append(highlight)

    if amount:
      highlights = highlights[:amount]

    return [InstagramHighlight(**h) for h in highlights]

  async def get_post(self: "Instagram", url: str, amount: Optional[int] = None):
    """
    Get the info about a post by url.

    Parameters
    ----------
    url: :class:`str`
      The url of the post to fetch it.
    amount: Optional[:class:`int`]
      The amount of images/videos to fetch. If the amount is not given all will be fetched.
    
    Returns
    -------
    :class:`List[InstagramMedia]`
      A list of InstagramMedia objects with the post images/videos.
    """
    char = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    code = [p for p in (urlparse(url).path).split("/") if p][1]
    media_id = sum(char.index(x) * (len(char) ** i) for i, x in enumerate(reversed(code)))

    data = await self.session.request(
      "GET",
      f"https://i.instagram.com/api/v1/media/{media_id}/info",
      headers=self.headers,
    )

    medias = []
    for media in data.get("items", []):
      if "video_versions" in media:
        media.video_url = sorted(
          media.video_versions,
          key=lambda x: x.height * x.width,
        )[-1].url

      if "image_versions2" in media:
        urls = [media_url.url for media_url in media.image_versions2.candidates]
        if amount:
          urls = urls[:amount]

        media.image_urls = urls
        media.thumbnail_url = sorted(
          media.image_versions2.candidates,
          key=lambda x: x.height * x.width,
        )[-1].url

      medias.append(media)

    return [InstagramMedia(**m) for m in medias]