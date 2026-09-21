from asyncio import Semaphore
from random import choice
from re import compile
from typing import Any, List, Optional

from ._utils import validate_amount
from .cache import coalesce_user
from .client import Client
from .exceptions import AuthenticationError, ParseError, RateLimitError
from .models import (
    InstagramComment,
    InstagramFollowerUser,
    InstagramHighlight,
    InstagramMedia,
    InstagramStory,
    InstagramUser,
)

INSTAGRAM_REGEX = compile(
    r"^(?:https?:\/\/)?(?:www\.)?instagram\.com\/(?:p|reel|tv)\/([a-zA-Z0-9_-]+)"
)
BASE64_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
BASE64_MAP = {char: i for i, char in enumerate(BASE64_ALPHABET)}


class Instagram(Client):
    def __init__(
        self: "Instagram",
        csrf: str,
        session_id: str,
        proxy: Optional[List[str]] = None,
        max_concurrent: int = 5,
        **options,
    ):
        super().__init__(**options)
        if max_concurrent <= 0:
            raise ValueError("max_concurrent must be positive")
        self.proxy = [proxy] if isinstance(proxy, str) else (proxy or [])
        self.headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 12_3_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Instagram 105.0.0.11.118 (iPhone11,8; iOS 12_3_1; en_US; en-US; scale=2.00; 828x1792; 165586599)",
            "Cookie": f"csrftoken={csrf}; sessionid={session_id}",
            "X-IG-App-ID": "936619743392459",
            "X-CSRFToken": csrf,
        }
        self.semaphore = Semaphore(max_concurrent)

    def _get_proxy(self: "Instagram"):
        return choice(self.proxy) if self.proxy else None

    async def _request(self, method: str, url: str, **kwargs) -> Any:
        kwargs.setdefault("headers", self.headers)
        kwargs.setdefault("response_type", "json")
        kwargs.setdefault(
            "allowed_hosts", {"i.instagram.com", "www.instagram.com", "instagram.com"}
        )
        if self.proxy:
            kwargs.setdefault("proxy", self._get_proxy())
        async with self.semaphore:
            data = await self.session.request(method, url, **kwargs)
        if isinstance(data, dict):
            message = data.get("message")
            if message == "login_required":
                raise AuthenticationError("Instagram session has expired", status=401)
            if message in {"challenge_required", "checkpoint_required"} or data.get("challenge"):
                raise AuthenticationError("Instagram requires account verification", status=403)
            if data.get("error_type") == "rate_limit_error":
                raise RateLimitError("Instagram rate limit reached", status=429)
        return data

    @coalesce_user
    async def get_user(self: "Instagram", username: str):
        """
        Get user information by username.

        Parameters
        ----------
        username : :class:`str`
          The username of the user to fetch the info.

        Returns
        -------
        :class:`InstagramUser`
          An InstagramUser object with the user info.
        """
        if username in self._user_cache:
            return self._user_cache[username]

        data = await self._request(
            "GET",
            f"https://i.instagram.com/api/v1/users/{username}/usernameinfo",
        )

        if not getattr(data, "user", None):
            raise ParseError("Instagram user data are missing or inaccessible")

        obj = InstagramUser(**data.user)
        self._user_cache[username] = obj
        return obj

    async def get_story(self: "Instagram", username: str, amount: Optional[int] = None):
        """
        Get the stories of a user by username.

        Parameters
        ----------
        username : :class:`str`
          The username of the user to fetch the stories.
        amount : Optional[:class:`int`]
          The amount of stories to fetch. If the amount is not given all stories will be fetched.

        Returns
        -------
        :class:`List[InstagramStory]`
          A list of InstagramStory objects with the user stories.
        """
        validate_amount(amount)
        if amount == 0:
            return []
        user_id = (await self.get_user(username)).pk
        data = (
            await self._request(
                "GET",
                f"https://i.instagram.com/api/v1/feed/user/{user_id}/story/",
            )
        ).get("reel") or {}

        items = data.get("items", [])
        if amount:
            items = items[:amount]

        stories = []
        for story in items:
            if story.get("video_versions"):
                story.video_url = max(story.video_versions, key=lambda x: x.height * x.width).url

            if (story.get("image_versions2") or {}).get("candidates"):
                story.image_url = max(
                    story.image_versions2.candidates,
                    key=lambda x: x.height * x.width,
                ).url

            if "story_bloks_stickers" in story:
                mentions = []
                for sticker in story.story_bloks_stickers:
                    bloks = sticker.get("bloks_sticker", {})
                    if bloks.get("bloks_sticker_type") == "mention":
                        mention = bloks.get("sticker_data", {}).get("ig_mention", {})
                        if mention:
                            mentions.append(
                                {
                                    "user_id": mention.get("account_id"),
                                    "username": mention.get("username"),
                                    "profile_pic_url": mention.get("profile_pic_url"),
                                }
                            )

                if mentions:
                    story.mentions = mentions

            stories.append(story)

        return [InstagramStory(**s) for s in stories]

    async def get_highlights(self: "Instagram", username: str, amount: Optional[int] = None):
        """
        Get the highlights of a user by username.

        Parameters
        ----------
        username : :class:`str`
          The username of the user to fetch the highlights.
        amount : Optional[:class:`int`]
          The amount of highlights to fetch. If the amount is not given all highlights will be fetched.

        Returns
        -------
        :class:`List[InstagramHighlight]`
          A list of InstagramHighlight objects with the user highlights.
        """
        validate_amount(amount)
        if amount == 0:
            return []
        user_id = (await self.get_user(username)).pk
        data = await self._request(
            "GET",
            f"https://i.instagram.com/api/v1/highlights/{user_id}/highlights_tray/",
        )
        tray = data.get("tray", [])
        if amount:
            tray = tray[:amount]

        highlights = []
        for highlight in tray:
            highlight.id = highlight.id.split(":")[1]
            highlight.cover_media = highlight.cover_media.cropped_image_version.url

            highlights.append(highlight)

        return [InstagramHighlight(**h) for h in highlights]

    async def get_post(self: "Instagram", url: str, amount: Optional[int] = None):
        """
        Get the info about a post by url.

        Parameters
        ----------
        url : :class:`str`
          The url of the post to fetch it.
        amount : Optional[:class:`int`]
          The amount of images/videos to fetch. If the amount is not given all will be fetched.

        Returns
        -------
        :class:`List[InstagramMedia]`
          A list of InstagramMedia objects with the post images/videos.
        """
        validate_amount(amount)
        if amount == 0:
            return []
        if not (match := INSTAGRAM_REGEX.match(url)):
            raise ValueError("This is not a valid Instagram post URL")

        shortcode = match.group(1)
        media_id = 0
        for char in shortcode:
            media_id = (media_id * 64) + BASE64_MAP[char]

        data = await self._request(
            "GET",
            f"https://i.instagram.com/api/v1/media/{media_id}/info",
        )

        medias = []
        for parent in data.get("items", []):
            slides = parent.get("carousel_media") or [parent]
            for slide in slides:
                media = dict(parent)
                media.pop("carousel_media", None)
                media.update(slide)
                # The post shortcode and author belong to the parent, IDs to each slide.
                candidates = (slide.get("image_versions2") or {}).get("candidates") or []
                videos = slide.get("video_versions") or []
                best_image = max(
                    candidates,
                    key=lambda x: (x.get("height") or 0) * (x.get("width") or 0),
                    default=None,
                )
                best_video = max(
                    videos,
                    key=lambda x: (x.get("height") or 0) * (x.get("width") or 0),
                    default=None,
                )
                media["image_urls"] = [best_image["url"]] if best_image else []
                media["thumbnail_url"] = best_image["url"] if best_image else None
                media["video_url"] = best_video["url"] if best_video else None
                medias.append(InstagramMedia(**media))
                if amount is not None and len(medias) >= amount:
                    return medias
        return medias

    async def get_comments(self: "Instagram", url: str, amount: Optional[int] = None):
        """
        Get the comments of a post by url.

        Parameters
        ----------
        url : :class:`str`
          The url of the post to fetch the comments from.
        amount : Optional[:class:`int`]
          The amount of comments to fetch. If the amount is not given all will be fetched.

        Returns
        -------
        :class:`List[InstagramComment]`
          A list of InstagramComment object with the post comments.
        """
        validate_amount(amount)
        if amount == 0:
            return []
        if not (match := INSTAGRAM_REGEX.match(url)):
            raise ValueError("This is not a valid Instagram post URL")
        post = 0
        for char in match.group(1):
            post = post * 64 + BASE64_MAP[char]
        comments, min_id = [], ""
        base_url = f"https://www.instagram.com/api/v1/media/{post}/comments"

        seen_cursors = set()
        while True:
            data = await self._request("GET", base_url, params={"min_id": min_id} if min_id else {})
            comment = data.get("comments", [])
            comments.extend(
                [
                    InstagramComment(**f)
                    for f in (comment[: amount - len(comments)] if amount else comment)
                ]
            )
            min_id = data.get("next_min_id", "")
            if min_id and min_id in seen_cursors:
                raise ParseError("Instagram pagination repeated a cursor")
            seen_cursors.add(min_id)

            if not min_id or not comment or (amount and len(comments) >= amount):
                return comments

    async def get_followers(self: "Instagram", username: str, amount: Optional[int] = None):
        """
        Get a user followers by username.

        Parameters
        ----------
        username : :class:`str`
          The username of the user to fetch the followers.
        amount : Optional[:class:`int`]
          The amount of followers to fetch. If the amount is not given all followers will be fetched.

        Returns
        -------
        :class:`List[InstagramFollowerUser]`
          A list of InstagramFollowerUser objects with the user followers.
        """
        validate_amount(amount)
        if amount == 0:
            return []
        user_id = (await self.get_user(username)).pk
        followers, max_id = [], ""
        base_url = f"https://i.instagram.com/api/v1/friendships/{user_id}/followers/"

        seen_cursors = set()
        while True:
            data = await self._request("GET", base_url, params={"max_id": max_id} if max_id else {})
            users = data.get("users", [])
            followers.extend(
                [
                    InstagramFollowerUser(**f)
                    for f in (users[: amount - len(followers)] if amount else users)
                ]
            )
            max_id = data.get("next_max_id", "")
            if max_id and max_id in seen_cursors:
                raise ParseError("Instagram pagination repeated a cursor")
            seen_cursors.add(max_id)

            if not max_id or not users or (amount and len(followers) >= amount):
                return followers

    async def get_following(self: "Instagram", username: str, amount: Optional[int] = None):
        """
        Get a user following by username.

        Parameters
        ----------
        username : :class:`str`
          The username of the user to fetch the following.
        amount : Optional[:class:`int`]
          The amount of following to fetch. If the amount is not given all following will be fetched.

        Returns
        -------
        :class:`List[InstagramFollowerUser]`
          A list of InstagramFollowerUser objects with the user following.
        """
        validate_amount(amount)
        if amount == 0:
            return []
        user_id = (await self.get_user(username)).pk
        following, max_id = [], ""
        base_url = f"https://i.instagram.com/api/v1/friendships/{user_id}/following/"

        seen_cursors = set()
        while True:
            data = await self._request("GET", base_url, params={"max_id": max_id} if max_id else {})
            users = data.get("users", [])
            following.extend(
                [
                    InstagramFollowerUser(**f)
                    for f in (users[: amount - len(following)] if amount else users)
                ]
            )
            max_id = data.get("next_max_id", "")
            if max_id and max_id in seen_cursors:
                raise ParseError("Instagram pagination repeated a cursor")
            seen_cursors.add(max_id)

            if not max_id or not users or (amount and len(following) >= amount):
                return following
