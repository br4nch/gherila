"""Optional HTTP interface. Install with: pip install 'gherila[api]'."""

import argparse
import asyncio
import inspect
import os
import secrets
from contextlib import AsyncExitStack, asynccontextmanager
from typing import get_type_hints

try:
    from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
    from fastapi.responses import JSONResponse
except ImportError as exc:
    raise ImportError("Install the HTTP API with: pip install 'gherila[api]'") from exc

from . import Brave, GitHub, Instagram, Reddit, Snapchat, TikTok, Twitter, __version__, models
from .exceptions import Error, HTTPError, NotFoundError, RateLimitError

# Explicit allowlist: no arbitrary methods, downloads, or filesystem paths.
OPERATIONS = {
    "github": (
        GitHub,
        {
            "get_user": models.GitHubUser,
            "get_repo": models.GitHubRepo,
            "get_repos": list[models.GitHubRepo],
            "get_commits": list[models.GitHubCommit],
        },
    ),
    "instagram": (
        Instagram,
        {
            "get_user": models.InstagramUser,
            "get_story": list[models.InstagramStory],
            "get_highlights": list[models.InstagramHighlight],
            "get_post": list[models.InstagramMedia],
            "get_comments": list[models.InstagramComment],
            "get_followers": list[models.InstagramFollowerUser],
            "get_following": list[models.InstagramFollowerUser],
        },
    ),
    "tiktok": (TikTok, {"get_user": models.TikTokUser, "get_video": models.TikTokVideo}),
    "twitter": (
        Twitter,
        {
            "get_user": models.TwitterUser,
            "get_tweet": models.TwitterTweet,
            "get_user_tweets": list[models.TwitterTweet],
        },
    ),
    "reddit": (
        Reddit,
        {
            "get_user": models.RedditUser,
            "get_subreddit": models.SubReddit,
            "get_subreddit_posts": list[models.RedditPost],
            "get_post": models.RedditPost,
            "search": list[models.RedditSearch],
            "get_comments": list[models.RedditComment],
        },
    ),
    "snapchat": (
        Snapchat,
        {
            "get_user": models.SnapUser,
            "get_story": models.SnapStory,
            "get_highlights": models.SnapStory,
        },
    ),
    "brave": (Brave, {"get_images": models.BraveImages, "get_search": models.BraveSearch}),
}


def _environment_clients():
    clients = {
        "github": GitHub(token=os.getenv("GITHUB_TOKEN")),
        "reddit": Reddit(),
        "snapchat": Snapchat(),
        "brave": Brave(),
    }
    configurations = [
        ("instagram", Instagram, ["INSTAGRAM_CSRF", "INSTAGRAM_SESSION_ID"]),
        ("tiktok", TikTok, ["TIKTOK_TTWID", "TIKTOK_MS_TOKEN"]),
        (
            "twitter",
            Twitter,
            ["TWITTER_AUTH_TOKEN", "TWITTER_CT0", "TWITTER_CSRF", "TWITTER_AUTHORIZATION"],
        ),
    ]
    for name, cls, variables in configurations:
        values = [os.getenv(variable) for variable in variables]
        if all(values):
            clients[name] = cls(*values)
    return clients


def _endpoint(platform, operation, cls, result_model):
    async def endpoint(request: Request, **kwargs):
        client = request.app.state.clients.get(platform)
        if client is None:
            raise HTTPException(503, detail=f"{platform} credentials are not configured")

        async def call():
            async with request.app.state.capacity:
                return await getattr(client, operation)(**kwargs)

        try:
            return await asyncio.wait_for(call(), timeout=request.app.state.request_timeout)
        except asyncio.TimeoutError:
            raise HTTPException(504, detail="Upstream request timed out") from None
        except ValueError:
            raise HTTPException(422, detail="Invalid platform parameter or URL") from None

    method = inspect.unwrap(getattr(cls, operation))
    hints = get_type_hints(method)
    params = [
        inspect.Parameter("request", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=Request)
    ]
    for param in inspect.signature(method).parameters.values():
        if param.name == "self":
            continue
        annotation = hints.get(param.name, str)
        default = param.default
        if param.name in {"amount", "limit"}:
            annotation = int
            default = Query(default=50 if default is None else default, ge=0, le=500)
        elif annotation is str:
            default = Query(
                default=... if default is inspect.Parameter.empty else default,
                min_length=1,
                max_length=2048,
            )
        params.append(param.replace(annotation=annotation, default=default))
    endpoint.__name__ = f"{platform}_{operation}"
    endpoint.__doc__ = f"{operation.replace('_', ' ').capitalize()} using the {platform} client."
    endpoint.__signature__ = inspect.Signature(params, return_annotation=result_model)
    return endpoint


def create_app(
    *,
    clients=None,
    api_key: str | None = None,
    request_timeout: float = 60,
    max_concurrent: int = 32,
) -> FastAPI:
    """Create an app. Supplied clients are owned and closed by its lifespan."""
    if request_timeout <= 0 or max_concurrent <= 0:
        raise ValueError("Request timeout and concurrency must be positive")
    key = api_key if api_key is not None else os.getenv("GHERILA_API_KEY")

    @asynccontextmanager
    async def lifespan(app):
        async with AsyncExitStack() as stack:
            active = _environment_clients() if clients is None else clients
            app.state.clients = {}
            app.state.capacity = asyncio.Semaphore(max_concurrent)
            app.state.request_timeout = request_timeout
            for name, client in active.items():
                app.state.clients[name] = await stack.enter_async_context(client)
            yield

    async def authorize(x_api_key: str | None = Header(default=None)):
        if key and (
            x_api_key is None or not secrets.compare_digest(x_api_key.encode(), key.encode())
        ):
            raise HTTPException(401, detail="Invalid or missing API key")

    app = FastAPI(
        title="gherila",
        version=__version__,
        lifespan=lifespan,
        description="Language-neutral async platform clients. JSON identifiers are strings.",
    )

    @app.get("/health", tags=["service"])
    async def health():
        return {"status": "ok", "version": __version__}

    @app.exception_handler(Error)
    async def platform_error(request, exc):
        status = 502
        if isinstance(exc, NotFoundError):
            status = 404
        elif isinstance(exc, RateLimitError):
            status = 429
        headers = {}
        if isinstance(exc, HTTPError) and exc.retry_after is not None:
            import math

            headers["Retry-After"] = str(math.ceil(exc.retry_after))
        messages = {
            404: "Upstream resource not found",
            429: "Upstream rate limit reached",
            502: "Upstream service failed or returned an unsupported response",
        }
        return JSONResponse(
            status_code=status,
            headers=headers,
            content={"error": {"type": type(exc).__name__, "message": messages[status]}},
        )

    for platform, (cls, operations) in OPERATIONS.items():
        for operation, result_model in operations.items():
            app.add_api_route(
                f"/v1/{platform}/{operation}",
                _endpoint(platform, operation, cls, result_model),
                methods=["GET"],
                response_model=result_model,
                dependencies=[Depends(authorize)],
                tags=[platform],
                responses={
                    401: {"description": "Invalid API key"},
                    404: {"description": "Resource not found"},
                    429: {"description": "Upstream rate limit"},
                    502: {"description": "Upstream failure"},
                    503: {"description": "Platform not configured"},
                    504: {"description": "Request timeout"},
                },
            )
    return app


def main():
    import uvicorn

    parser = argparse.ArgumentParser(description="Run the gherila HTTP API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost", "::1"} and not os.getenv("GHERILA_API_KEY"):
        parser.error("Set GHERILA_API_KEY before binding to a non-loopback interface")
    uvicorn.run(create_app(), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
