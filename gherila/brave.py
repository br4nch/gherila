from selectolax.parser import HTMLParser
from itertools import islice
from re import (
  IGNORECASE,
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
URL_PATTERN = compile(r'https?://[^\s]+', IGNORECASE)

class Brave:
  def __init__(self: "Brave"):
    self.session = State()
    self.headers = {
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
  }
  
  async def get_images(
    self: "Brave",
    query: str,
    safe: bool = True,
    limit: int = 25
  ):
    """
    Get images from Brave.

    Parameters
    ----------
    query : :class:`str`
      The query to search for.
    safe : :class:`bool`
      Whether to enable or disable safe search. Default is `True`.
    limit : :class:`int`
      The number of images to return. Default is 10.

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
      },
      headers=self.headers,
    )

    r = []
    for match in IMG_PATTERN.finditer(data):
      src = match.group(1)
      if src.startswith("https://imgs.search.brave.com/") and "32:32" not in src:
        r.append(src)
        if len(r) >= limit:
          break

    if not r:
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

    for r in tree.css('a[href^="http"]'):
      if len(results) >= limit:
        break

      url = r.attributes.get("href")
      if not url or not url.startswith("http"):
        continue

      if url in seen or "brave" in url.lower():
        continue

      title = r.text(strip=True)
      if len(title) < 5:
        continue

      description = ""
      parent = r.parent
      if parent and parent.parent:
        raw_text = parent.parent.text(separator=" ", strip=True)

        text_no_title = raw_text.replace(title, "")
        description = URL_PATTERN.sub("", text_no_title).strip()

      results.append(
        BraveResult(
          url=url,
          title=title,
          description=description
        )
      )
      seen.add(url)

    if not results:
      raise Error(f"No results were found for the query `{query}`.")

    return BraveSearch(
      query=query,
      results=results
    )