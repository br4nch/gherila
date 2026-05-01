from .http import State
from .exceptions import Error
from .models import (
  SubReddit,
  RedditUser,
  RedditPost,
  RedditSearch,
  RedditComment
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

  async def get_subreddit_posts(
    self: "Reddit",
    name: str,
    sort: str = "new",
    limit: int = 10
  ):
    """
    Get a subreddit's posts by name.

    Parameters
    ----------
    name : :class:`str`
      The name of the subreddit to fetch the posts.
    sort : :class:`str`
      The sorting method for the posts. Can be "new", "hot" or "top". Default is "new".
    limit : :class:`int`
      The number of posts to fetch. Default is 10.

    Returns
    -------
    :class:`RedditPost`
      A list of RedditPost objects with the subreddit posts..
    """
    data = await self.session.request(
      "GET",
      f"https://www.reddit.com/r/{name}/{sort}.json?limit={limit}&raw_json=1",
      headers=self.headers,
    )

    if data.error == 404:
      raise Error(f"No subreddit founded for the name `{name}`.")
    
    return [RedditPost(**c.data) for c in data.data.children]

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
  
  async def search(
    self: "Reddit",
    query: str,
    sort: str = "relevance",
    limit: int = 10
  ):
    """
    Search for posts matching a query.

    Parameters
    ----------
    query : :class:`str`
      The search query to look for.
    sort : :class:`str`
      The sorting method for the search results. Can be "relevance", "hot", "top" or "new". Default is "relevance".
    limit : :class:`int`
      The number of searches results to fetch. Default is 10.

    Returns
    -------
    List[:class:`RedditSearch`]
      A list of RedditSearch objects matching the query.
    """
    data = await self.session.request(
      "GET",
      f"https://www.reddit.com/search.json?q={query}&sort={sort}&limit={limit}&raw_json=1",
      headers=self.headers,
    )

    if not data.data.children:
      raise Error(f"No results found for the query `{query}`.")

    return [RedditSearch(**c.data) for c in data.data.children]

  async def get_comments(self: "Reddit", url: str):
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

    comments = []
    for c in data[1].data.children:
      if c.kind == "t1":
        comments.append(RedditComment(**c.data))

    return comments