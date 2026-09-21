from urllib.parse import quote, urlsplit, urlunsplit

from ._utils import validate_amount, validate_url
from .cache import coalesce_user
from .client import Client
from .exceptions import ParseError
from .models import RedditComment, RedditPost, RedditSearch, RedditUser, SubReddit

REDDIT_HOSTS = {"reddit.com", "www.reddit.com", "old.reddit.com", "new.reddit.com", "m.reddit.com"}


class Reddit(Client):
    def __init__(self, **options):
        super().__init__(**options)
        self.headers = {"User-Agent": "gherila/1.4 (async Python client)"}

    async def _request(self, path, **params):
        url = (
            path
            if path.startswith("https://") or path.startswith("http://")
            else f"https://www.reddit.com/{path}"
        )
        return await self.session.request(
            "GET",
            url,
            headers=self.headers,
            params={"raw_json": 1, **params},
            response_type="json",
            allowed_hosts=REDDIT_HOSTS,
        )

    @staticmethod
    def _post_url(url):
        parts = urlsplit(validate_url(url, REDDIT_HOSTS))
        path = parts.path.rstrip("/")
        if not path.endswith(".json"):
            path += ".json"
        return urlunsplit((parts.scheme, parts.netloc, path, "", ""))

    async def get_subreddit(self, name: str) -> SubReddit:
        data = await self._request(f"r/{quote(name, safe='')}/about.json")
        return SubReddit(**data.data)

    async def _listing(self, path, model, limit, **params):
        validate_amount(limit)
        results, cursor, seen = [], None, set()
        while len(results) < limit:
            data = await self._request(
                path, limit=min(100, limit - len(results)), after=cursor or "", **params
            )
            listing = data.get("data") or {}
            children = listing.get("children") or []
            results.extend(model(**item["data"]) for item in children[: limit - len(results)])
            cursor = listing.get("after")
            if not cursor or not children or len(results) >= limit:
                break
            if cursor in seen:
                raise ParseError("Reddit pagination repeated a cursor")
            seen.add(cursor)
        return results

    async def get_subreddit_posts(
        self, name: str, sort: str = "new", limit: int = 10
    ) -> list[RedditPost]:
        if sort not in {"new", "hot", "top", "rising", "controversial"}:
            raise ValueError("Unsupported subreddit sort")
        return await self._listing(f"r/{quote(name, safe='')}/{sort}.json", RedditPost, limit)

    async def get_post(self, url: str) -> RedditPost:
        data = await self._request(self._post_url(url))
        try:
            return RedditPost(**data[0]["data"]["children"][0]["data"])
        except (IndexError, KeyError, TypeError) as exc:
            raise ParseError("Reddit post data are missing") from exc

    @coalesce_user
    async def get_user(self, username: str) -> RedditUser:
        data = await self._request(f"user/{quote(username, safe='')}/about.json")
        user = RedditUser(**data.data)
        self._user_cache[username] = user
        return user

    async def search(
        self, query: str, sort: str = "relevance", limit: int = 10
    ) -> list[RedditSearch]:
        if sort not in {"relevance", "hot", "top", "new", "comments"}:
            raise ValueError("Unsupported search sort")
        return await self._listing("search.json", RedditSearch, limit, q=query, sort=sort)

    async def get_comments(self, url: str) -> list[RedditComment]:
        """Return comments included in the response; Reddit 'more' placeholders are not expanded."""
        data = await self._request(self._post_url(url))
        try:
            children = data[1]["data"]["children"]
            return [RedditComment(**item["data"]) for item in children if item.get("kind") == "t1"]
        except (IndexError, KeyError, TypeError) as exc:
            raise ParseError("Reddit comment data are missing") from exc
