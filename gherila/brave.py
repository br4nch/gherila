from html.parser import HTMLParser
from urllib.parse import urlsplit

from ._utils import validate_amount
from .client import Client
from .models import BraveImages, BraveResult, BraveSearch


class _Page(HTMLParser):
    """Portable fallback; selectolax optionally adds surrounding descriptions."""

    def __init__(self):
        super().__init__()
        self.images = []
        self.links = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "img" and attrs.get("src"):
            self.images.append(attrs["src"])
        if tag == "a":
            self.current = [attrs.get("href", ""), []]

    def handle_data(self, text):
        if self.current is not None:
            self.current[1].append(text)

    def handle_endtag(self, tag):
        if tag == "a" and self.current is not None:
            self.links.append((self.current[0], " ".join(self.current[1]).strip(), ""))
            self.current = None


class Brave(Client):
    def __init__(self, **options):
        super().__init__(**options)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
        }

    async def _page(self, path, query, safe):
        return await self.session.request(
            "GET",
            f"https://search.brave.com/{path}",
            params={"q": query, "safesearch": "strict" if safe else "off"},
            headers=self.headers,
            response_type="text",
        )

    async def get_images(self, query: str, safe: bool = True, limit: int = 25) -> BraveImages:
        validate_amount(limit)
        if limit == 0:
            return BraveImages(query=query, images=[])
        page = _Page()
        page.feed(await self._page("images", query, safe))
        images = list(
            dict.fromkeys(
                src
                for src in page.images
                if src.startswith("https://imgs.search.brave.com/") and "32:32" not in src
            )
        )
        return BraveImages(query=query, images=images[:limit])

    async def get_search(self, query: str, safe: bool = True, limit: int = 10) -> BraveSearch:
        validate_amount(limit)
        if limit == 0:
            return BraveSearch(query=query, results=[])
        html = await self._page("search", query, safe)
        try:
            from selectolax.parser import HTMLParser as FastParser
        except ImportError:
            page = _Page()
            page.feed(html)
            links = page.links
        else:
            tree = FastParser(html)
            links = []
            for anchor in tree.css('a[href^="http"]'):
                title = anchor.text(strip=True)
                parent = anchor.parent
                description = (
                    parent.parent.text(separator=" ", strip=True).replace(title, "", 1).strip()
                    if parent and parent.parent
                    else ""
                )
                links.append((anchor.attributes.get("href", ""), title, description))
        results, seen = [], set()
        for url, title, description in links:
            try:
                parsed = urlsplit(url)
            except ValueError:
                continue
            host = (parsed.hostname or "").lower()
            if (
                parsed.scheme not in {"http", "https"}
                or not host
                or host == "brave.com"
                or host.endswith(".brave.com")
            ):
                continue
            if url in seen or len(title) < 5:
                continue
            results.append(BraveResult(url=url, title=title, description=description))
            seen.add(url)
            if len(results) >= limit:
                break
        return BraveSearch(query=query, results=results)
