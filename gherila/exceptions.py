"""Stable exceptions shared by the Python clients and optional HTTP API."""


class Error(Exception):
    """Base class for errors raised by gherila."""


class HTTPError(Error):
    def __init__(self, message: str, *, status: int, retry_after: float | None = None):
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after


class AuthenticationError(HTTPError):
    """Credentials are missing, expired, or insufficient."""


class NotFoundError(HTTPError):
    """The requested resource does not exist or is unavailable."""


class RateLimitError(HTTPError):
    """The upstream service is rate limiting requests."""


class TransportError(Error):
    """The network request failed or timed out."""


class ParseError(Error):
    """The upstream response does not match the expected format."""


class ResponseTooLargeError(Error):
    """The response exceeds the configured byte limit."""
