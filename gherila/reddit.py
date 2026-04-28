from .http import State
from .exceptions import Error
from .models import (
  SubReddit,
  RedditUser,
  RedditPost,
  RedditSearch
)

class Reddit:
  def __init__(self: "Reddit"):
    self.session = State()
    self.headers = {
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }

  async def get_subreddit(self: "Reddit", name: str):
    """
    Get a subreddit information by name.

    Parameters
    ----------
    name : :class:`str`
      The name of the subreddit to fetch the information.

    Returns
    -------
    :class:`SubReddit`
      A SubReddit object with the subreddit information.
    """
    data = await self.session.request(
      "GET",
      f"https://www.reddit.com/r/{name}/about.json?raw_json=1",
      headers=self.headers,
    )

    if data.error == 404:
      raise Error(f"No subreddit founded for the name `{name}`.")

    return SubReddit(**data.data)

  async def get_post(self: "Reddit", url: str):
    """
    Get a post information by url.

    Parameters
    ----------
    url : :class:`str`
      The url of the post to fetch the information.

    Returns
    -------
    :class:`RedditPost`
      A RedditPost object with the post information.
    """
    clean = url.strip().rstrip("/")
    data = await self.session.request(
      "GET",
      clean + ".json?raw_json=1",
      headers=self.headers,
    )

    if getattr(data, "error", None) == 404:
      raise Error(f"No post founded for the url `{url}`.")

    return RedditPost(**data[0].data.children[0].data)
  
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

    if data.error == 404:
      raise Error(f"No user founded for the username `{username}`.")

    return RedditUser(**data.data)
  
  async def search(self: "Reddit", query: str):
    """
    Search for posts matching a query.

    Parameters
    ----------
    query : :class:`str`
      The search query to look for.

    Returns
    -------
    List[:class:`RedditSearch`]
      A list of RedditSearch objects matching the query.
    """
    data = await self.session.request(
      "GET",
      f"https://www.reddit.com/search.json?q={query}&raw_json=1",
      headers=self.headers,
    )

    if not data.data.children:
      raise Error(f"No results found for the query `{query}`.")

    return [RedditSearch(**c.data) for c in data.data.children]