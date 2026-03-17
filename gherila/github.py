from .http import State
from .models import (
  GitHubUser,
  GitHubRepo,
  GitHubCommit
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
    username : :class:`str`
      The username of the investigated user.

    Returns
    -------
    :class:`GitHubUser`
      A GitHubUser object with the user info.
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
    username : :class:`str`
      The username of the repository owner.
    repo_name : :class:`str`
      The name of the repository you want to fetch.

    Returns
    -------
    :class:`GitHubRepo`
      A GitHubRepo object with the repository information.
    """
    data = await self.session.request(
      "GET",
      f"https://api.github.com/repos/{username}/{repo_name}"
    )
    if data.status == "404":
      raise Error(f"Can't find a repository with the name `{repo_name}` for the user `{username}`.")

    return GitHubRepo(**data)

  async def get_repos(self: "GitHub", username: str):
    """
    Get all the repositories for the given username.

    Parameters
    ----------
    username : :class:`str`
      The username of the github account.
    
    Returns
    -------
    :class:`List[GitHubRepo]`
      A list of GitHubRepo objects containing the repository info.
    """
    data = await self.session.request(
      "GET",
      f"https://api.github.com/users/{username}/repos"
    )
    return [GitHubRepo(**repo) for repo in data]

  async def get_commits(self: "GitHub", username: str, repository_name: str):
    """
    Get the commits from a github repo

    Parameters
    ----------
    username : :class:`str`
      The username of the github account containing the repository.
    repository_name : :class:`str`
      The repository name from the github account.
    
    Returns
    -------
    :class:`List[GitHubCommit]`
      A list of GitHubCommit objects containing the commits from a repository.
    """
    data = await self.session.request(
      "GET",
      f"https://api.github.com/repos/{username}/{repository_name}/commits",
    )
    if data.status == '404':
      raise Error(f"There is no repository named `{repository_name}` for the user `{username}`.")

    return [GitHubCommit(**commit) for commit in data]