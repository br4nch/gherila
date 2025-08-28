from re import (
  findall,
  match
)

from .http import State
from .exceptions import Error
from .models import BraveImages

class Brave:
  def __init__(self: "Brave"):
    self.session = State()
  
  async def get_images(self: "Brave", query: str, safe: bool = True):
    """
    Get images from Brave.

    Parameters
    ----------
    query: :class:`str`
      The query to search for.
    safe: :class:`bool`
      Whether to enable or disable safe search. Default is `True`.
    
    Returns
    -------
    :class:`BraveImages`
      A BraveImages object with the search results.
    """
    data = await self.session.request(
      "GET",
      "https://search.brave.com/images",
      params={
        "q": query,
        "safesearch": "strict" if safe else "off",
      }
    )
    imgs = findall(r'<img[^>]+src="([^">]+)"', data)
    if not (
      r := list(
        filter(
          lambda img: match(r"^https://imgs.search.brave.com/", img) and
          '32:32' not in img, imgs
        )
      )
    ):
      raise Error(f"No images were found for the query `{query}`.")

    return BraveImages(
      query=query,
      images=r,
    )