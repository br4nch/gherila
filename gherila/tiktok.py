from io import BytesIO
from pathlib import Path
from urllib.parse import quote

from ._utils import script_json, validate_url
from .cache import coalesce_user
from .client import Client
from .exceptions import NotFoundError, ParseError
from .models import TikTokUser, TikTokVideo

TIKTOK_HOSTS = {"tiktok.com", "www.tiktok.com", "m.tiktok.com", "vm.tiktok.com", "vt.tiktok.com"}


class TikTok(Client):
    def __init__(self, ttwid: str, msToken: str, **options):
        super().__init__(**options)
        self.headers = {
            "Cookie": f"ttwid={ttwid}; msToken={msToken}",
            "Referer": "https://www.tiktok.com/",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }

    async def _detail(self, url, key):
        html = await self.session.request(
            "GET",
            validate_url(url, TIKTOK_HOSTS),
            headers=self.headers,
            response_type="text",
            allowed_hosts=TIKTOK_HOSTS,
        )
        scope = script_json(html, "__UNIVERSAL_DATA_FOR_REHYDRATION__").get("__DEFAULT_SCOPE__", {})
        detail = scope.get(key)
        if not isinstance(detail, dict):
            raise ParseError(f"TikTok page is missing {key}")
        if detail.get("statusCode") == 10221:
            raise NotFoundError("TikTok resource was not found", status=404)
        if detail.get("statusCode", 0) != 0:
            raise ParseError("TikTok returned an unavailable or restricted resource")
        return detail

    @coalesce_user
    async def get_user(self, username: str) -> TikTokUser:
        detail = await self._detail(
            f"https://www.tiktok.com/@{quote(username, safe='')}", "webapp.user-detail"
        )
        info = detail.get("userInfo") or {}
        if not info.get("user") or not isinstance(info.get("stats"), dict):
            raise ParseError("TikTok user data or statistics are missing")
        user = TikTokUser(**{**info["user"], "stats": info["stats"]})
        self._user_cache[username] = user
        return user

    async def get_video(self, url: str) -> TikTokVideo:
        """Return video metadata from the page's video-detail payload."""
        detail = await self._detail(url, "webapp.video-detail")
        item = (detail.get("itemInfo") or {}).get("itemStruct")
        if not isinstance(item, dict):
            raise ParseError("TikTok video data are missing")
        media_url = (item.get("video") or {}).get("playAddr")
        if not isinstance(media_url, str) or not media_url:
            raise ParseError("TikTok post has no playable video")
        author = item.get("author") or {}
        if item.get("authorStats"):
            user = TikTokUser(**{**author, "stats": item["authorStats"]})
        elif author.get("uniqueId"):
            user = await self.get_user(author["uniqueId"])
        else:
            raise ParseError("TikTok video author is missing")
        return TikTokVideo(**{**item, "author": user, "url": media_url})

    async def download_video(
        self, video: TikTokVideo, path: str | Path | None = None
    ) -> Path | BytesIO:
        """Stream to disk or return bounded in-memory bytes; never send account cookies to a CDN."""
        return await self.session.download(
            validate_url(video.url),
            path,
            headers={
                "User-Agent": self.headers["User-Agent"],
                "Referer": "https://www.tiktok.com/",
            },
        )
