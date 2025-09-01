from datetime import datetime

from typing import (
  Optional,
  List
)
from pydantic import (
  BaseModel,
  HttpUrl
)

class BraveImages(BaseModel):
  query: str
  images: List[HttpUrl]

class TikTokBioLinks(BaseModel):
  link: str

class TikTokStats(BaseModel):
  followingCount: int
  followerCount: int
  heartCount: int
  videoCount: int

class TikTokUser(BaseModel):
  id: int
  uniqueId: str
  nickname: str
  signature: str
  avatarMedium: HttpUrl
  verified: bool
  privateAccount: bool
  stats: TikTokStats

class BioLinks(BaseModel):
  link_id: int
  url: str
  title: Optional[str] = None
  is_pinned: Optional[bool] = None

class InstagramUser(BaseModel):
  pk: int
  username: str
  full_name: str
  is_private: bool
  is_verified: bool
  media_count: int
  follower_count: int
  following_count: int
  is_business: bool
  profile_pic_url: HttpUrl
  biography: Optional[str] = None
  account_type: Optional[int] = None
  external_url: Optional[str] = None
  bio_links: List[BioLinks] = []

class InstagramStoryUser(BaseModel):
  pk: int
  username: Optional[str] = None
  full_name: Optional[str] = None
  profile_pic_url: Optional[HttpUrl] = None
  is_private: Optional[bool] = None

class InstagramStory(BaseModel):
  id: int
  media_type: int
  taken_at: datetime
  user: InstagramStoryUser
  image_url: Optional[HttpUrl] = None
  video_url: Optional[HttpUrl] = None
  video_duration: Optional[float] = 0.0
  thumnail_url: Optional[HttpUrl] = None

class InstagramHighlight(BaseModel):
  id: int
  title: str
  created_at: datetime
  is_pinned_highlight: bool
  media_count: int
  cover_media: str
  user: InstagramStoryUser