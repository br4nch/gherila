import asyncio
import json
from unittest.mock import AsyncMock

import pytest
from munch import DefaultMunch

from gherila import Brave, GitHub, Instagram, Reddit, Snapchat, TikTok, Twitter
from gherila.cache import TTLCache
from gherila.exceptions import ParseError


def payload(value):
    return DefaultMunch.fromDict(value)


async def test_github_cache_coalesces_and_returns_independent_models(github_user):
    async with GitHub() as client:
        entered, release = asyncio.Event(), asyncio.Event()

        async def request(*args, **kwargs):
            entered.set()
            await release.wait()
            return payload(github_user)

        client.session.request = AsyncMock(side_effect=request)
        first = asyncio.create_task(client.get_user("Example"))
        second = asyncio.create_task(client.get_user("@example"))
        await entered.wait()
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        release.set()
        user = await second
        assert user.name is None
        assert client.session.request.await_count == 1
        user.login = "changed"
        cached = await client.get_user("example")
        assert cached.login == "example"
        assert cached.model_dump(mode="json")["id"] == "9007199254740993"
    with pytest.raises(RuntimeError):
        await client.get_user("example")


async def test_github_list_and_pagination():
    commit = dict(
        sha="a",
        html_url="https://example.com",
        commit=dict(
            author=dict(name="a", email="a@example.com", date="2025-01-01T00:00:00Z"),
            message="test",
        ),
    )
    async with GitHub() as client:
        client.session.request = AsyncMock(
            side_effect=[
                payload([{**commit, "sha": str(i)} for i in range(100)]),
                payload([commit]),
            ]
        )
        assert len(await client.get_commits("example", "repo")) == 101
        assert client.session.request.call_args.kwargs["params"]["page"] == 2
        client.session.request = AsyncMock(return_value=[])
        assert await client.get_repos("example") == []
        client.session.request.reset_mock()
        assert await client.get_repos("example", limit=0) == []
        client.session.request.assert_not_awaited()


def test_ttl_lru(monkeypatch):
    now = [0]
    monkeypatch.setattr("gherila.cache.monotonic", lambda: now[0])
    cache = TTLCache(2, 10)
    cache["a"], cache["b"] = 1, 2
    assert cache["a"] == 1
    cache["c"] = 3
    assert "b" not in cache
    now[0] = 11
    assert len(cache) == 0
    cache = TTLCache(0, 10)
    cache["a"] = 1
    assert not cache


async def test_instagram_mixed_carousel_and_amount():
    data = payload(
        {
            "items": [
                dict(
                    pk=100,
                    id="100_1",
                    code="B",
                    media_type=8,
                    taken_at=1700000000,
                    like_count=1,
                    comment_count=1,
                    user={"pk": 1},
                    carousel_media=[
                        dict(
                            pk=101,
                            id="101_1",
                            media_type=1,
                            image_versions2={
                                "candidates": [
                                    {
                                        "url": "https://example.com/1.jpg",
                                        "width": 100,
                                        "height": 100,
                                    }
                                ]
                            },
                        ),
                        dict(
                            pk=102,
                            id="102_1",
                            media_type=2,
                            video_versions=[
                                {"url": "https://example.com/2.mp4", "width": 100, "height": 100}
                            ],
                        ),
                    ],
                )
            ]
        }
    )
    async with Instagram("csrf", "session") as client:
        client.session.request = AsyncMock(return_value=data)
        media = await client.get_post("https://www.instagram.com/p/B/")
        assert [m.pk for m in media] == [101, 102]
        assert str(media[0].image_urls[0]) == "https://example.com/1.jpg"
        assert str(media[1].video_url) == "https://example.com/2.mp4"
        assert media[1].image_urls == []
        assert len(await client.get_post("https://instagram.com/p/B/", amount=1)) == 1
        client.session.request.reset_mock()
        assert await client.get_post("https://instagram.com/p/B/", amount=0) == []
        client.session.request.assert_not_awaited()
        with pytest.raises(ValueError):
            await client.get_post("https://instagram.com/p/B/", amount=-1)


async def test_instagram_comments_do_not_fetch_post_and_detect_repeated_cursor():
    comment = dict(
        pk=1,
        text="hello",
        created_at=1700000000,
        user=dict(
            pk=1,
            username="a",
            full_name="A",
            profile_pic_url="https://example.com/a",
            is_private=False,
            is_verified=False,
        ),
    )
    async with Instagram("csrf", "session") as client:
        client.session.request = AsyncMock(
            return_value=payload({"comments": [comment], "next_min_id": "same"})
        )
        with pytest.raises(ParseError, match="repeated"):
            await client.get_comments("https://instagram.com/p/B/")
        assert client.session.request.await_count == 2
        assert "/media/1/comments" in client.session.request.call_args.args[1]


async def test_tiktok_video_returns_model_without_extra_user_request():
    item = dict(
        id="9007199254740993",
        desc="video",
        createTime=1700000000,
        stats=dict(diggCount=1, shareCount=2, commentCount=3, playCount=4, collectCount=5),
        author=dict(
            id="1",
            uniqueId="user",
            nickname="User",
            signature="",
            avatarLarger="https://example.com/a",
            verified=False,
        ),
        authorStats=dict(followingCount=1, followerCount=2, heartCount=3, videoCount=4),
        video={"playAddr": "https://example.com/video.mp4"},
    )
    html = (
        '<script type="application/json" id="__UNIVERSAL_DATA_FOR_REHYDRATION__">\n'
        + json.dumps(
            {"__DEFAULT_SCOPE__": {"webapp.video-detail": {"itemInfo": {"itemStruct": item}}}}
        )
        + "\n</script>"
    )
    async with TikTok("cookie", "token") as client:
        client.session.request = AsyncMock(return_value=html)
        video = await client.get_video("https://www.tiktok.com/@user/video/123")
        assert video.id == 9007199254740993
        assert video.author.username == "user"
        assert client.session.request.await_count == 1
        client.session.download = AsyncMock()
        await client.download_video(video)
        assert "Cookie" not in client.session.download.call_args.kwargs["headers"]
        client.session.request.return_value = "<html>blocked</html>"
        with pytest.raises(ParseError):
            await client.get_video("https://www.tiktok.com/@user/video/123")


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example/https://www.tiktok.com/@a/video/1",
        "https://tiktok.com.evil.example/x",
        "file:///tmp/test",
        "https://user:pass@www.tiktok.com/x",
    ],
)
async def test_tiktok_rejects_wrong_hosts(url):
    async with TikTok("a", "b") as client:
        client.session.request = AsyncMock()
        with pytest.raises(ValueError):
            await client.get_video(url)
        client.session.request.assert_not_awaited()


async def test_snapchat_missing_script_and_empty_story():
    async with Snapchat() as client:
        client.session.request = AsyncMock(return_value="<html>blocked</html>")
        with pytest.raises(ParseError):
            await client.get_user("example")
        client.session.request.return_value = (
            '<script id="__NEXT_DATA__">'
            + json.dumps({"props": {"pageProps": {"pageMetadata": {"title": "user"}}}})
            + "</script>"
        )
        assert (await client.get_story("example")).count == 0


async def test_reddit_query_encoding_and_url_normalization():
    async with Reddit() as client:
        client.session.request = AsyncMock(return_value=payload({"data": {"children": []}}))
        assert await client.search("a&limit=999 # test") == []
        args = client.session.request.call_args
        assert args.kwargs["params"]["q"] == "a&limit=999 # test"
        assert "?" not in args.args[1]
        assert (
            client._post_url("https://www.reddit.com/r/test/comments/id/title/?share=1")
            == "https://www.reddit.com/r/test/comments/id/title.json"
        )
        with pytest.raises(ValueError):
            await client.get_post("http://localhost/private")


async def test_brave_filter_is_by_host():
    async with Brave() as client:
        client.session.request = AsyncMock(
            return_value='<a href="https://brave.com/about">About Brave</a><a href="https://example.com/brave-story">Brave story</a>'
        )
        result = await client.get_search("brave")
        assert [item.url for item in result.results] == ["https://example.com/brave-story"]
        assert not (await client.get_images("x", limit=0)).images


async def test_twitter_missing_tweet_is_parse_error():
    async with Twitter("a", "b", "c", "d") as client:
        client.session.request = AsyncMock(
            return_value=payload(
                {"data": {"threaded_conversation_with_injections_v2": {"instructions": []}}}
            )
        )
        with pytest.raises(ParseError):
            await client.get_tweet("https://x.com/user/status/123")


async def test_model_validation_is_library_error():
    async with GitHub() as client:
        client.session.request = AsyncMock(return_value=payload({"id": 1}))
        with pytest.raises(ParseError):
            await client.get_user("example")


async def test_empty_instagram_story():
    async with Instagram("csrf", "session") as client:
        client.get_user = AsyncMock(return_value=type("User", (), {"pk": 1})())
        client.session.request = AsyncMock(return_value=payload({"reel": None}))
        assert await client.get_story("example") == []


async def test_close_cancels_shared_request(github_user):
    client = GitHub()
    started = asyncio.Event()
    stopped = asyncio.Event()

    async def request(*args, **kwargs):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    client.session.request = AsyncMock(side_effect=request)
    task = asyncio.create_task(client.get_user("example"))
    await started.wait()
    await client.close()
    assert stopped.is_set()
    with pytest.raises(asyncio.CancelledError):
        await task


async def test_instagram_expired_session_is_authentication_error():
    from gherila.exceptions import AuthenticationError

    async with Instagram("csrf", "session") as client:
        client.session.request = AsyncMock(
            return_value=payload({"status": "fail", "message": "login_required"})
        )
        with pytest.raises(AuthenticationError) as error:
            await client.get_user("example")
        assert error.value.status == 401
        assert client.session.request.await_count == 1
