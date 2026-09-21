from html.parser import HTMLParser
from urllib.parse import urlsplit, urlunsplit

from ._json import loads
from .exceptions import ParseError


def validate_url(url: str, hosts: set[str] | None = None) -> str:
    parts = urlsplit(url.strip())
    if (
        parts.scheme not in {"http", "https"}
        or not parts.hostname
        or parts.username is not None
        or parts.password is not None
    ):
        raise ValueError("Expected an HTTP(S) URL without embedded credentials")
    if hosts is not None and (
        parts.hostname.lower() not in hosts or parts.port not in {None, 80, 443}
    ):
        raise ValueError("URL is not on a supported platform host")
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))


def validate_amount(amount: int | None) -> None:
    if amount is not None and (
        isinstance(amount, bool) or not isinstance(amount, int) or amount < 0
    ):
        raise ValueError("amount/limit must be a non-negative integer or None")


class _ScriptParser(HTMLParser):
    def __init__(self, script_id: str):
        super().__init__(convert_charrefs=False)
        self.script_id = script_id
        self.active = False
        self.found = False
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "script" and dict(attrs).get("id") == self.script_id:
            self.active = self.found = True

    def handle_endtag(self, tag):
        if tag == "script":
            self.active = False

    def handle_data(self, data):
        if self.active:
            self.parts.append(data)


def script_json(html: str, script_id: str) -> dict:
    if not isinstance(html, str):
        raise ParseError("Expected an HTML page")
    parser = _ScriptParser(script_id)
    parser.feed(html)
    if not parser.found:
        raise ParseError(f"Page is missing {script_id}; it may be a login/challenge page")
    try:
        value = loads("".join(parser.parts))
    except (ValueError, TypeError) as exc:
        raise ParseError(f"Invalid JSON in {script_id}") from exc
    if not isinstance(value, dict):
        raise ParseError(f"Expected an object in {script_id}")
    return value
