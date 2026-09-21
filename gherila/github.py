from urllib.parse import quote

from ._utils import validate_amount
from .cache import coalesce_user
from .client import Client
from .exceptions import ParseError
from .models import GitHubCommit, GitHubRepo, GitHubUser


class GitHub(Client):
    def __init__(self, token: str | None = None, **options):
        super().__init__(**options)
        self.headers = {"Accept": "application/vnd.github+json", "User-Agent": "gherila"}
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    async def _request(self, path, **kwargs):
        return await self.session.request(
            "GET",
            f"https://api.github.com/{path}",
            headers=self.headers,
            response_type="json",
            **kwargs,
        )

    @coalesce_user
    async def get_user(self, username: str) -> GitHubUser:
        """Get a user; repeated lookups use a bounded TTL cache."""
        data = await self._request(f"users/{quote(username, safe='')}")
        user = GitHubUser(**data)
        self._user_cache[username] = user
        return user

    async def get_repo(self, username: str, repo_name: str) -> GitHubRepo:
        """Get a repository by owner and name."""
        data = await self._request(f"repos/{quote(username, safe='')}/{quote(repo_name, safe='')}")
        return GitHubRepo(**data)

    async def _pages(self, path, model, limit):
        validate_amount(limit)
        count, page = 0, 1
        previous = None
        while limit is None or count < limit:
            data = await self._request(path, params={"per_page": 100, "page": page})
            if not isinstance(data, list):
                raise ParseError("Expected a GitHub list response")
            if not data:
                return
            marker = tuple(item.get("id", item.get("sha")) for item in data)
            if marker == previous:
                raise ParseError("GitHub pagination repeated a page")
            previous = marker
            for item in data:
                yield model(**item)
                count += 1
                if limit is not None and count >= limit:
                    return
            if len(data) < 100:
                return
            page += 1

    async def iter_repos(self, username: str, limit: int | None = None):
        """Yield repositories across pages without buffering the full collection."""
        async for repo in self._pages(f"users/{quote(username, safe='')}/repos", GitHubRepo, limit):
            yield repo

    async def get_repos(self, username: str, limit: int | None = None) -> list[GitHubRepo]:
        """Get repositories across pages, optionally bounded by limit."""
        return [repo async for repo in self.iter_repos(username, limit)]

    async def iter_commits(self, username: str, repository_name: str, limit: int | None = None):
        path = f"repos/{quote(username, safe='')}/{quote(repository_name, safe='')}/commits"
        async for commit in self._pages(path, GitHubCommit, limit):
            yield commit

    async def get_commits(
        self, username: str, repository_name: str, limit: int | None = None
    ) -> list[GitHubCommit]:
        """Get commits across pages, optionally bounded by limit."""
        return [commit async for commit in self.iter_commits(username, repository_name, limit)]
