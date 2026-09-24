import asyncio
import inspect
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from gherila import GitHub, TikTok
from gherila.bridge import Bridge, PLATFORMS, decode, describe, encode, methods, run
from gherila.http import State
from gherila.models import TikTokVideo
from fixture_worker import MEDIA, STATS, USER, VIDEO, request

ROOT = Path(__file__).resolve().parents[1]
OPTIONS = {
  "instagram": {"csrf": "test", "session_id": "test"},
  "tiktok": {"ttwid": "test", "msToken": "test"},
  "twitter": {"auth_token": "test", "ct0": "test", "crsf": "test", "authorization": "test"},
}


def video():
  return TikTokVideo(**{
    **VIDEO, "url": "https://example.com/video.mp4",
    "author": {**USER, "stats": STATS},
  })


class BridgeTests(unittest.IsolatedAsyncioTestCase):
  async def asyncSetUp(self):
    self.bridge = Bridge(timeout=1)

  async def test_all_public_provider_methods_are_callable(self):
    self.assertEqual(set(describe()["platforms"]), {
      "brave", "github", "instagram", "reddit", "snapchat", "tiktok", "twitter",
    })
    count = 0
    for platform, cls in PLATFORMS.items():
      created = await self.bridge.handle({"op": "create", "client": platform,
        "platform": platform, "options": OPTIONS.get(platform, {})})
      self.assertNotIn("error", created)
      for name, original in methods(cls).items():
        with self.subTest(platform=platform, method=name):
          kwargs = {}
          for param in inspect.signature(original).parameters.values():
            if param.name == "self" or param.default is not inspect.Parameter.empty:
              continue
            kwargs[param.name] = encode(video()) if param.name == "video" else None if param.name == "path" else "test"
          calls = []
          async def mocked(self, *args, **values):
            calls.append(inspect.signature(original).bind(self, *args, **values).arguments)
            return {"platform": platform, "method": name}
          mocked.__signature__ = inspect.signature(original)
          with patch.object(cls, name, mocked):
            result = await self.bridge.handle({"id": str(count), "client": platform,
              "method": name, "kwargs": kwargs})
          self.assertEqual(result["result"], {"platform": platform, "method": name})
          self.assertEqual(result["id"], str(count))
          self.assertEqual(len(calls), 1)
          if name == "download_video":
            self.assertIsInstance(calls[0]["video"], TikTokVideo)
          count += 1
    self.assertEqual(count, 28)

  async def test_provider_results_match_direct_python(self):
    with patch.object(State, "request", request):
      direct = await GitHub().get_user("demo")
      response = await self.bridge.handle({"platform": "github", "method": "get_user", "args": ["demo"]})
    self.assertEqual(response["result"], encode(direct))
    self.assertEqual(response["result"]["id"]["value"], "9223372036854775807")

  async def test_model_roundtrip_binary_and_file_download(self):
    with patch.object(State, "request", request):
      response = await self.bridge.handle({"platform": "tiktok", "options": OPTIONS["tiktok"],
        "method": "get_video", "kwargs": {"url": "https://www.tiktok.com/@demo/video/123"}})
      self.assertNotIn("error", response)
      result = await self.bridge.handle({"platform": "tiktok", "options": OPTIONS["tiktok"],
        "method": "download_video", "kwargs": {"video": response["result"], "path": None}})
      self.assertEqual(decode(result["result"]), MEDIA)
      with tempfile.TemporaryDirectory() as directory:
        path = str(Path(directory) / "video.mp4")
        result = await self.bridge.handle({"platform": "tiktok", "options": OPTIONS["tiktok"],
          "method": "download_video", "kwargs": {"video": response["result"], "path": path}})
        self.assertEqual(result["result"], path)
        self.assertEqual(Path(path).read_bytes(), MEDIA)

  async def test_clients_preserve_instance_and_separate_credentials(self):
    for client in ("one", "two"):
      await self.bridge.handle({"op": "create", "client": client, "platform": "instagram",
        "options": {"csrf": client, "session_id": client}})
    first = self.bridge.clients["one"]
    first._user_cache["test"] = {"cached": True}
    response = await self.bridge.handle({"client": "one", "method": "get_user", "args": ["test"]})
    self.assertEqual(response["result"], {"cached": True})
    self.assertNotEqual(first.headers["Cookie"], self.bridge.clients["two"].headers["Cookie"])
    self.assertEqual((await self.bridge.handle({"op": "create", "client": "one", "platform": "github"}))["error"]["code"], "client_exists")
    await self.bridge.handle({"op": "close", "client": "one"})
    self.assertNotIn("one", self.bridge.clients)
    self.assertIn("two", self.bridge.clients)

  async def test_invalid_requests_and_private_methods(self):
    cases = [
      ([], "invalid_request"),
      ({"version": True, "op": "describe"}, "invalid_request"),
      ({"version": 2}, "invalid_request"),
      ({"id": 2**63}, "invalid_request"),
      ({"id": False}, "invalid_request"),
      ({"client": []}, "invalid_request"),
      ({"client": "missing"}, "unknown_client"),
      ({"platform": "os", "method": "system"}, "unknown_platform"),
      ({"platform": "github", "method": "__init__"}, "unknown_method"),
      ({"platform": "github", "method": "session"}, "unknown_method"),
      ({"platform": "instagram", "options": OPTIONS["instagram"], "method": "_request"}, "unknown_method"),
      ({"platform": "github", "method": "get_user", "kwargs": {"invalid": "x"}}, "invalid_params"),
      ({"platform": "github", "method": "get_user", "args": "wrong"}, "invalid_params"),
      ({"platform": "github", "method": "get_user", "args": [{"$gherila": "int", "value": "bad"}]}, "invalid_params"),
      ({"platform": "instagram", "options": {"session_id": "secret"}}, "invalid_params"),
      ({"platform": "github", "method": "get_user", "kwargs": {"username": {}}}, "invalid_params"),
      ({"op": "close"}, "invalid_request"),
      ({"op": "invalid"}, "invalid_request"),
    ]
    for payload, code in cases:
      with self.subTest(payload=payload):
        self.assertEqual((await self.bridge.handle(payload))["error"]["code"], code)

  async def test_timeout_and_errors_do_not_leak_credentials(self):
    with patch.object(State, "request", request):
      failure = await self.bridge.handle({"platform": "github", "method": "get_user", "args": ["failure"]})
      timeout = await Bridge(timeout=0.01).handle({"platform": "github", "method": "get_user", "args": ["slow"]})
    self.assertNotIn("secret-cookie", json.dumps(failure))
    self.assertEqual(failure["error"]["type"], "RuntimeError")
    self.assertEqual(timeout["error"]["code"], "timeout")

  async def test_framing_errors_and_eof(self):
    source = io.BytesIO(b'bad\n\xff\n{"id":"bad","args":[NaN]}\n{"id":"ok","op":"describe"}')
    target = io.BytesIO()
    await run(source, target)
    results = [json.loads(line) for line in target.getvalue().splitlines()]
    self.assertEqual([result["error"]["code"] for result in results[:3]], ["invalid_json"] * 3)
    self.assertEqual(results[-1]["id"], "ok")
    source = io.BytesIO(b'x' * 101 + b'\n{"op":"describe"}\n')
    target = io.BytesIO()
    await run(source, target, max_line=100)
    results = [json.loads(line) for line in target.getvalue().splitlines()]
    self.assertEqual(results[0]["error"]["code"], "request_too_large")
    self.assertIn("result", results[1])

  async def test_concurrency_and_lifecycle_barriers(self):
    source = io.BytesIO(b'\n'.join(json.dumps(item).encode() for item in [
      {"id": "create", "op": "create", "client": "gh", "platform": "github"},
      {"id": "slow", "client": "gh", "method": "get_user", "args": ["slow"]},
      {"id": "fast", "client": "gh", "method": "get_user", "args": ["demo"]},
      {"id": "close", "op": "close", "client": "gh"},
      {"id": "after", "client": "gh", "method": "get_user", "args": ["demo"]},
    ]))
    target = io.BytesIO()
    with patch.object(State, "request", request):
      await run(source, target, concurrency=2)
    results = [json.loads(line) for line in target.getvalue().splitlines()]
    self.assertEqual([item["id"] for item in results], ["create", "fast", "slow", "close", "after"])
    self.assertEqual(results[-1]["error"]["code"], "unknown_client")

  async def test_concurrency_is_bounded(self):
    active = peak = 0
    started = asyncio.Event()
    release = asyncio.Event()
    async def mocked(self, username: str):
      nonlocal active, peak
      active += 1
      peak = max(peak, active)
      if active == 3:
        started.set()
      await release.wait()
      active -= 1
      return username
    source = io.BytesIO(b'\n'.join(json.dumps({"id": i, "platform": "github",
      "method": "get_user", "args": ["test"]}).encode() for i in range(12)))
    target = io.BytesIO()
    with patch.object(GitHub, "get_user", mocked):
      task = asyncio.create_task(run(source, target, concurrency=3))
      try:
        await asyncio.wait_for(started.wait(), 5)
      finally:
        release.set()
        await task
    self.assertEqual(peak, 3)
    self.assertEqual(len(target.getvalue().splitlines()), 12)


class ProcessTests(unittest.TestCase):
  def test_real_process_utf8_stderr_and_eof(self):
    requests = '\n'.join(json.dumps({"id": name, "platform": "github", "method": "get_user",
      "args": [name]}) for name in ["demo", "print", "slow"]).encode()
    result = subprocess.run([sys.executable, str(ROOT / "tests/fixture_worker.py")], input=requests,
      capture_output=True, timeout=10, env={**os.environ, "PYTHONIOENCODING": "ascii"})
    self.assertEqual(result.returncode, 0, result.stderr)
    responses = [json.loads(line) for line in result.stdout.splitlines()]
    self.assertEqual(len(responses), 3)
    self.assertEqual(responses[0]["result"]["name"], "Ștefan 日本語")
    self.assertIn(b"provider diagnostic", result.stderr)

  def test_module_describe_and_invalid_options(self):
    result = subprocess.run([sys.executable, "-m", "gherila", "--describe"],
      capture_output=True, timeout=10)
    self.assertEqual(result.returncode, 0, result.stderr)
    self.assertEqual(len(json.loads(result.stdout)["platforms"]), 7)
    result = subprocess.run([sys.executable, "-m", "gherila", "--timeout", "nan"],
      capture_output=True, timeout=10)
    self.assertNotEqual(result.returncode, 0)

  def test_serialization(self):
    value = {"id": 2**63, "negative": -(2**63), "binary": io.BytesIO(MEDIA),
      "time": datetime(2020, 1, 1, tzinfo=timezone.utc), "path": Path("video.mp4"),
      "nested": [{"bool": True, "nothing": None}]}
    encoded = encode(value)
    self.assertEqual(decode(encoded)["id"], 2**63)
    self.assertEqual(decode(encoded)["negative"], -(2**63))
    self.assertEqual(decode(encoded)["binary"], MEDIA)
    self.assertEqual(encoded["time"], "2020-01-01T00:00:00+00:00")
    self.assertEqual(encoded["path"], "video.mp4")
    self.assertEqual(encoded["nested"], value["nested"])
    with self.assertRaises(TypeError):
      encode(object())
    with self.assertRaises(TypeError):
      encode(float("inf"))


if __name__ == "__main__":
  unittest.main()
