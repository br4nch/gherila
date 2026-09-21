from urllib.parse import quote

from ._utils import script_json
from .cache import coalesce_user
from .client import Client
from .exceptions import NotFoundError, ParseError
from .models import SnapStory, SnapUser


class Snapchat(Client):
    def __init__(self, **options):
        super().__init__(**options)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }

    async def _page(self, username):
        html = await self.session.request(
            "GET",
            f"https://story.snapchat.com/add/{quote(username, safe='')}",
            headers=self.headers,
            response_type="text",
            allowed_hosts={"story.snapchat.com", "www.snapchat.com", "snapchat.com"},
        )
        props = script_json(html, "__NEXT_DATA__").get("props", {}).get("pageProps")
        if not isinstance(props, dict):
            raise ParseError("Snapchat page data are missing")
        if not props.get("pageMetadata"):
            raise NotFoundError("Snapchat user was not found", status=404)
        return props

    @coalesce_user
    async def get_user(self, username: str) -> SnapUser:
        props = await self._page(username)
        if not isinstance(props.get("userProfile"), dict):
            raise ParseError("Snapchat profile data are missing")
        user = SnapUser(
            **{
                **props["userProfile"],
                "username": username,
                "url": f"https://story.snapchat.com/add/{quote(username, safe='')}",
            }
        )
        self._user_cache[username] = user
        return user

    @staticmethod
    def _stories(snaps):
        try:
            videos = [
                {
                    "url": snap["snapUrls"]["mediaUrl"],
                    "snap_id": snap["snapId"]["value"],
                    "preview_url": snap["snapUrls"]["mediaPreviewUrl"]["value"],
                    "media_type": snap["snapMediaType"],
                    "timestamp": snap["timestampInSec"]["value"],
                }
                for snap in snaps
            ]
        except (KeyError, TypeError) as exc:
            raise ParseError("Snapchat story format changed") from exc
        return SnapStory(videos=videos, count=len(videos))

    async def get_story(self, username: str) -> SnapStory:
        props = await self._page(username)
        return self._stories((props.get("story") or {}).get("snapList") or [])

    async def get_highlights(self, username: str) -> SnapStory:
        props = await self._page(username)
        return self._stories(
            [
                snap
                for highlight in props.get("spotlightHighlights") or []
                for snap in highlight.get("snapList") or []
            ]
        )
