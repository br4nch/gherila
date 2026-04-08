from selectolax.parser import HTMLParser
from re import (
  sub,
  compile
)

from .http import State
from .exceptions import Error
from .models import (
  BraveImages,
  BraveResult,
  BraveSearch
)

IMG_PATTERN = compile(r'<img[^>]+src="([^">]+)"')

class Brave:
  def __init__(self: "Brave"):
    self.session = State()
    self.headers = {
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
  }
  
  async def get_images(self: "Brave", query: str, safe: bool = True):
    """
    Get images from Brave.

    Parameters
    ----------
    query : :class:`str`
      The query to search for.
    safe : :class:`bool`
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

    if not (
      r := [
        img for img in IMG_PATTERN.findall(data)
        if img.startswith("https://imgs.search.brave.com/") and "32:32" not in img
      ]
    ):
      raise Error(f"No images were found for the query `{query}`.")

    return BraveImages(
      query=query,
      images=r,
    )

  async def get_search(self: "Brave", query: str, safe: bool = True, limit: int = 10):
    """
    Get web search results from Brave.

    Parameters
    ----------
    query : :class:`str`
      The search query.
    safe : :class:`str`
      Whether to enable safe search. Default is `True`.
    limit : :class:`int`
      Maximum number of results to return. Default is 10.
    
    Returns
    -------
    :class:`BraveSearch`
      A BraveSearch object with the found results.
    """
    data = await self.session.request(
      "GET",
      f"https://search.brave.com/search",
      headers=self.headers,
      params={
        "q": query,
        "safesearch": "strict" if safe else "off"
      }
    )
    tree = HTMLParser(data)
    results = []
    seen = set()

    for r in tree.css("a"):
      url = r.attributes.get("href", "")
      if not url.startswith("http") or "brave" in url.lower() or url in seen:
        continue

      if len(
        (
          title := r.text(strip=True)
        )
      ) < 5:
        continue

      description = ""
      if (
        content := r.parent.parent if r.parent and r.parent.parent else None
      ):
        text = content.text(separator=" ", strip=True)
        description = sub(r"https?://[^\s]+", "", text.replace(title, "")).strip()

      results.append(
        BraveResult(
          url=url,
          title=title,
          description=description
        )
      )
      seen.add(url)

      if len(results) >= limit:
        break

    if not results:
      raise Error(f"No results were found for the query `{query}`.")

    return BraveSearch(
      query=query,
      results=results
    )