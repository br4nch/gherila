from .http import State
from .models import (
  SubReddit,
  RedditUser
)

class Reddit:
  def __init__(self: "Reddit"):
    self.session = State()
    self.headers = {
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
  
  async def get_subreddit(self: "Reddit", url: str):
    """
    Get subreddit information by url.

    Parameters
    ----------
    url : :class:`str`
      The url of the subreddit post to fetch the information.
    
    Returns
    -------
    :class:`SubReddit`
      A SubReddit object with the subreddit information.
    """
    clean = url.strip().rstrip("/")
    data = await self.session.request(
      "GET",
      clean + ".json?raw_json=1",
      headers=self.headers,
    )
    return SubReddit(**data[0].data.children[0].data)
  
  async def get_user(self: "Reddit", username: str):
    """
    Get user information by username.

    Parameters
    ----------
    username : :class:`str`
      The username of the user to fetch the information.
    
    Returns
    -------
    :class:`RedditUser`
      A RedditUser object with the user information.
    """
    data = await self.session.request(
      "GET",
      f"https://www.reddit.com/user/{username}/about.json?raw_json=1",
      headers=self.headers,
    )
    return RedditUser(**data.data)