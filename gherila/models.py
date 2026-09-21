from datetime import datetime
from typing import Any, List

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_serializer,
    field_validator,
    model_validator,
)


class SocialsModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    @field_serializer("id", "pk", "user_id", check_fields=False, when_used="json")
    def serialize_identifier(self, value) -> str:
        return str(value)


class RedditComment(SocialsModel):
    id: str
    author: str
    body: str
    ups: int
    created_utc: datetime
    permalink: str
    is_submitter: bool
    replies: List["RedditComment"]

    @field_validator("replies", mode="before")
    @classmethod
    def parse_replies(cls, v: Any) -> List["RedditComment"]:
        if isinstance(v, str) or not v:
            return []

        children = v.get("data", {}).get("children", [])
        return [cls(**c["data"]) for c in children if c.get("kind") == "t1"]


RedditComment.model_rebuild()


class SubReddit(SocialsModel):
    id: str
    display_name: str
    title: str
    public_description: str
    subscribers: int
    created_utc: datetime
    over18: bool
    community_icon: str | None = None
    banner_background_image: str | None = None
    wiki_enabled: bool | None = None


class _RedditPost(SocialsModel):
    id: str
    author: str
    title: str
    selftext: str
    url: str
    permalink: str
    ups: int
    upvote_ratio: float
    num_comments: int
    over_18: bool
    is_video: bool
    is_self: bool
    created_utc: datetime


class RedditSearch(_RedditPost):
    post_hint: str | None = None
    is_gallery: bool = False
    gallery_data: dict | None = None
    media: dict | None = None


class RedditUser(SocialsModel):
    id: str
    name: str
    created: datetime
    link_karma: int
    comment_karma: int
    total_karma: int
    is_mod: bool
    verified: bool
    is_gold: bool
    icon_img: HttpUrl


class RedditPost(_RedditPost):
    stickied: bool
    spoiler: bool
    thumbnail: str | None = None
    link_flair_text: str | None = None
    domain: str
    category: str | None = None
    total_awards_received: int = 0


class TwitterUserBiolinks(SocialsModel):
    display_url: str
    expanded_url: str
    url: str


class TwitterUser(SocialsModel):
    username: str
    id: int
    avatar: str
    banner: str | None = None
    bio: str
    display_name: str | None = None
    location: str
    verified: bool
    verified_type: str | None = None
    created_at: str
    followers: int
    following: int
    posts: int
    liked_posts: int
    tweets: int
    pinned_tweets: List[str] | None = None
    biolinks: List[TwitterUserBiolinks]
    url: str


class TwitterMedia(SocialsModel):
    type: str
    video_url: str | None = None
    image_url: str | None = None


class TwitterTweet(SocialsModel):
    id: int
    text: str | None = None
    author: TwitterUser
    lang: str
    likes: int
    replies: int
    retweets: int
    quote: int
    retweeted: bool
    created_at: str
    views: int
    bookmarks: int
    is_quote: bool
    quote_url: str | None = None
    hashtags: List[str] | None = None
    mentions: List[str] | None = None
    media: List[TwitterMedia]


class CommitAuthor(SocialsModel):
    name: str
    email: str
    date: datetime


class CommitDetail(SocialsModel):
    author: CommitAuthor
    message: str


class GitHubCommit(SocialsModel):
    sha: str
    html_url: str
    commit: CommitDetail


class GitHubUser(SocialsModel):
    id: int
    login: str
    avatar_url: HttpUrl
    url: str
    name: str | None = None
    type: str
    company: str | None = None
    location: str | None = None
    email: str | None = None
    bio: str | None = None
    public_repos: int
    followers: int
    following: int
    created_at: datetime


class GitHubRepoOwner(SocialsModel):
    login: str
    id: int
    avatar_url: HttpUrl
    html_url: HttpUrl
    type: str


class GitHubRepo(SocialsModel):
    id: int
    name: str
    private: bool
    owner: GitHubRepoOwner
    description: str | None = None
    fork: bool
    url: str
    created_at: datetime
    updated_at: datetime
    stargazers_count: int
    watchers_count: int
    language: str | None = None
    archived: bool
    topics: List[str] = Field(default_factory=list)
    forks: int


class BraveResult(SocialsModel):
    url: str
    title: str
    description: str


class BraveSearch(SocialsModel):
    query: str
    results: List[BraveResult]


class BraveImages(SocialsModel):
    query: str
    images: List[HttpUrl]


class TikTokBioLinks(SocialsModel):
    link: str


class TikTokStats(SocialsModel):
    following: int = Field(alias="followingCount")
    followers: int = Field(alias="followerCount")
    likes: int = Field(alias="heartCount")
    videos: int = Field(alias="videoCount")


class TikTokUser(SocialsModel):
    id: int
    username: str = Field(alias="uniqueId")
    nickname: str
    description: str = Field(alias="signature")
    avatar: HttpUrl = Field(alias="avatarLarger")
    is_verified: bool = Field(alias="verified")
    is_private: bool = Field(default=False, alias="privateAccount")
    stats: TikTokStats


class TikTokVideoStats(SocialsModel):
    likes: int = Field(alias="diggCount")
    shares: int = Field(alias="shareCount")
    comments: int = Field(alias="commentCount")
    plays: int = Field(alias="playCount")
    saves: int = Field(alias="collectCount")


class TikTokVideo(SocialsModel):
    id: int
    description: str = Field(alias="desc")
    created: datetime = Field(alias="createTime")
    stats: TikTokVideoStats
    author: TikTokUser
    url: str


class BioLinks(SocialsModel):
    link_id: int
    url: str
    title: str | None = None
    is_pinned: bool | None = None


class InstagramUser(SocialsModel):
    pk: int
    username: str
    full_name: str
    is_private: bool
    is_verified: bool
    media_count: int
    followers: int = Field(alias="follower_count")
    following: int = Field(alias="following_count")
    is_business: bool
    avatar: HttpUrl | None = Field(default=None, alias="profile_pic_url")
    biography: str | None = None
    account_type: int | None = None
    external_url: str | None = None
    bio_links: List[BioLinks] = Field(default_factory=list)


class InstagramStoryUser(SocialsModel):
    pk: int
    username: str | None = None
    full_name: str | None = None
    avatar: HttpUrl | None = Field(default=None, alias="profile_pic_url")
    is_private: bool | None = None


class StoryMention(SocialsModel):
    user_id: int
    username: str
    avatar: HttpUrl | None = Field(default=None, alias="profile_pic_url")


class InstagramStory(SocialsModel):
    id: str
    media_type: int
    taken_at: datetime
    user: InstagramStoryUser
    image_url: HttpUrl | None = None
    video_url: HttpUrl | None = None
    video_duration: float | None = 0.0
    thumbnail_url: HttpUrl | None = None
    expiring_at: datetime | None = None
    mentions: List[StoryMention] | None = None
    has_liked: bool | None = False


class InstagramHighlight(SocialsModel):
    id: int
    title: str
    created_at: datetime
    is_pinned_highlight: bool
    media_count: int
    cover_media: str
    user: InstagramStoryUser


class InstagramCommentUser(SocialsModel):
    pk: int
    username: str
    full_name: str
    avatar: HttpUrl = Field(alias="profile_pic_url")
    is_private: bool
    is_verified: bool


class InstagramComment(SocialsModel):
    pk: int
    text: str
    created_at: datetime
    user: InstagramCommentUser


class InstagramMedia(SocialsModel):
    pk: int
    id: str
    code: str
    media_type: int
    taken_at: datetime
    like_count: int
    comment_count: int
    play_count: int | None = None
    title: str | None = None
    user: InstagramStoryUser
    image_urls: List[HttpUrl] | None = None
    thumbnail_url: HttpUrl | None = None
    video_url: HttpUrl | None = None
    video_duration: float | None = 0.0


class InstagramFollowerUser(SocialsModel):
    pk: int
    username: str
    full_name: str
    is_private: bool
    is_verified: bool
    avatar: HttpUrl | None = Field(default=None, alias="profile_pic_url")


class SnapUser(SocialsModel):
    display_name: str
    avatar: HttpUrl | None = None
    username: str
    snapcode: HttpUrl
    bio: str | None = None
    url: HttpUrl
    subscriber_count: int = 0
    spotlight_videos: List[HttpUrl] = Field(default_factory=list)
    banner: HttpUrl | None = Field(default=None, alias="hero_image")

    @model_validator(mode="before")
    @classmethod
    def map_response(cls, data: Any):
        if not isinstance(data, dict) or "$case" not in data:
            return data

        case = data["$case"]
        mapped = data.copy()

        if case == "userInfo":
            user = data.get("userInfo", {})
            mapped.update(
                {
                    "display_name": user.get("displayName"),
                    "bio": None,
                    "avatar": user.get("bitmoji3d", {}).get("avatarImage", {}).get("fallbackUrl"),
                    "snapcode": user.get("snapcodeImageUrl", "").replace("&type=SVG", "&type=PNG"),
                }
            )

        elif case == "publicProfileInfo":
            user = data.get("publicProfileInfo", {})
            sub_count = str(user.get("subscriberCount", "0"))

            mapped.update(
                {
                    "display_name": user.get("title"),
                    "bio": user.get("bio"),
                    "avatar": user.get("profilePictureUrl"),
                    "snapcode": user.get("snapcodeImageUrl", "").replace("&type=SVG", "&type=PNG"),
                    "hero_image": user.get("squareHeroImageUrl") or None,
                    "subscriber_count": int(sub_count) if sub_count.isdigit() else 0,
                }
            )

            mapped["spotlight_videos"] = [
                url
                for h in data.get("spotlightHighlights", [])
                if (snaps := h.get("snapList"))
                and (url := snaps[0].get("snapUrls", {}).get("mediaUrl"))
            ]

        return mapped


class SnapStoryList(SocialsModel):
    url: HttpUrl
    snap_id: str
    preview_url: str
    media_type: int
    timestamp: int


class SnapStory(SocialsModel):
    videos: list[SnapStoryList]
    count: int
