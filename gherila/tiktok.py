import aiofiles

from pathlib import Path
from io import BytesIO
from re import search, compile
from orjson import loads
from munch import munchify

from .http import State
from .exceptions import Error
from .models import (
  TikTokUser,
  TikTokStats,
  TikTokVideo
)

TIKTOK_CONTENT = r"^.*https:\/\/(?:m|www|vm)?\.?tiktok\.com\/((?:.*\b(?:(?:v|embed|photo|video|t)\/|\?shareId=|\&item_id=)(\d+))|\w+)"
TIKTOK_REGEX = compile(TIKTOK_CONTENT)

class TikTok:
  def __init__(self: "TikTok"):
    self.session = State()
    self.headers = {
      "Cookie": "ttwid=1%7C4jtfZIORfW9Nma3caSwVPQKeOIPeikQC-cptB9SFtRE%7C1752327502%7C904a70c"
                    "5b47b777141ce0610b027cdc06a7e8072728680fd3ebac63835e2a14c; tt_chain_token=oD2" 
                    "L/9Ze+RjY0FOHasXjBQ==; msToken=KyyIxtpF2qUUWINhGmEz_s7aNRRJCz9p9G4dtzumDTOW6R" 
                    "ikevqzSIcvv31WVjsKAk5_bWRq_RInwctnMO4uNkbAHPNW0AxbCK2a5qEoYfMvtT-Ms0y8--bN5mqw" 
                    "N8DSwclub7i7s56GqoqxfYFkGg==; odin_tt=33649e9b6a18d8297dbf1158c376a47a61ddc1bf"
                    "9f476a49a4e9d6f32613904c4a1845084307f849afa808328f02ddff3f67c8cca6c262ce5d8088"
                    "bd1c7ad9cdfd7e8cc62c6feb06af87cf87597087b8; "
                    "cookie-consent={%22optional%22:true%2C%22ga%22:true%2C%22af%22:true%2C%22fbp"
                    "%22:true%2C%22lip%22:true%2C%22bing%22:true%2C%22ttads%22:true%2C%22reddit%22"
                    ":true%2C%22hubspot%22:true%2C%22version%22:%22v10%22}; passport_csrf_token="
                    "7c6732ea13325a8530707a417a62722f; passport_csrf_token_default=7c6732ea13325a85"
                    "30707a417a62722f; tt_csrf_token=TIHqbHIW-GMVGwOTyyL294UceCXs-vrmm5vE; s_v_web_"
                    "id=verify_md0akixj_dSCvFkWD_vFBj_4bzi_B1zz_KPTQzHHfoAAt",
      "Referer": "https://www.tiktok.com/",
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
  
  async def get_user(self: "TikTok", username: str):
    """
    Get use information by username.

    Parameters
    ----------
    username : :class:`str`
      The username of the user to fetch the info.

    Returns
    -------
    :class:`TikTokUser`
      A TikTokUser object with the user information.
    """

    data = await self.session.request(
      "GET",
      f"https://www.tiktok.com/@{username}",
      headers=self.headers,
    )
    result = search(r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>', data)
    raw = loads(result.group(1))["__DEFAULT_SCOPE__"]["webapp.user-detail"]
    loaded = munchify(raw)

    if loaded.statusCode == 10221:
      raise Error(f"Can't find an user with the username `@{username}`.")

    stats = TikTokStats(**loaded.userInfo.stats)
    loaded.userInfo.user.stats = stats
    return TikTokUser(**loaded.userInfo.user)

  async def get_video(self: "TikTok", url: str):
    """
    Get video data based on the given url.

    Parameters
    ----------
    url : :class:`str`
      The tiktok video url.

    Returns
    -------
    :class:`TikTokVideo`
      A TikTokVideo object containing the video information.
    """
    if not TIKTOK_REGEX.match(url):
      raise Error("This is not a valid tiktok url.")

    data = await self.session.request(
      "GET",
      url,
      headers=self.headers,
    )
    result = search(r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>', data)
    loaded = munchify(loads(result.group(1))["__DEFAULT_SCOPE__"]["webapp.video-detail"])

    r = loaded.itemInfo.itemStruct
    user = await self.get_user(r.author.uniqueId)
    r.author = user
    r.url = r.video.playAddr
    return TikTokVideo(**r)
  
  async def download_video(self: "TikTok", video: TikTokVideo, path: str | Path | None) -> Path | BytesIO:
    """
    Download a tiktok video.

    Parameters
    ----------
    video : :class:`TikTokVideo`
      The TikTokVideo object to download.
    path : :class:`str` | :class:`Path` | None
      The path to save the video. If None, it will return a BytesIO object.

    Returns
    -------
    :class:`Path` | :class:`BytesIO`
      The path to the downloaded video or a BytesIO object if path is None.
    """
    video_data = await self.session.request(
      "GET",
      video.url,
      headers=self.headers,
    )

    if path:
      save_path = Path(path)
        
      async with aiofiles.open(save_path, "wb") as f:
          await f.write(video_data)
          
      return save_path
    else:
      return BytesIO(video_data)