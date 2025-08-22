from .http import State
from .models import (
  InstagramUser,
  InstagramStory
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
    return InstagramUser(**data.user)

  async def get_story(self: "Instagram", username: str):
    """
    Get the stories of a user by username.

    Parameters
    ----------
    username: :class:`str`
      The username of the user to fetch the stories.
    
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
    return [InstagramStory(**s) for s in stories]