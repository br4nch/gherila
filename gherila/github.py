from .http import State
from .models import (
  GitHubUser,
  GitHubRepo
)
from .exceptions import Error

class GitHub:
  def __init__(self: "GitHub"):
    self.session = State()

  async def get_user(self: "GitHub", username: str):
    """
    Get user information by provided username.

    Parameters
    ----------
    username: :class:`str`
      The username of the investigated user.
    """
    data = await self.session.request(
      "GET",
      f"https://api.github.com/users/{username}"
    )
    if data.status == "404":
      raise Error(f"Can't find an user with the username `{username}`.")

    return GitHubUser(**data)
  
  async def get_repo(self: "GitHub", username: str, repo_name: str):
    """
    Get repository information by the provided github username and repository name.

    Parameters
    ----------
    username: :class:`str`
      The username of the repository owner.
    repo_name: :class:`str`
      The name of the repository you want to fetch.
    """
    data = await self.session.request(
      "GET",
      f"https://api.github.com/repos/{username}/{repo_name}"
    )
    if data.status == "404":
      raise Error(f"Can't find a repository with the name `{repo_name}` for the user `{username}`.")
    
    return GitHubRepo(**data)