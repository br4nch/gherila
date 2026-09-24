"""Local, newline-delimited JSON interface to the public async clients."""

import asyncio
import base64
import inspect
import json
import math
import sys

from argparse import ArgumentParser
from collections.abc import Mapping
from datetime import date, datetime
from io import BytesIO
from pathlib import Path

from pydantic import BaseModel, TypeAdapter, ValidationError

from . import Brave, GitHub, Instagram, Reddit, Snapchat, TikTok, Twitter

PLATFORMS = {
  cls.__name__.lower(): cls
  for cls in (Brave, GitHub, Instagram, Reddit, Snapchat, TikTok, Twitter)
}
SAFE_INTEGER = 2 ** 53 - 1
MAX_LINE = 8 * 1024 * 1024


class BridgeError(Exception):
  def __init__(self, code: str, message: str):
    self.code = code
    super().__init__(message)


def encode(value):
  """Preserve model fields, binary data and integer precision across languages."""
  if isinstance(value, BaseModel):
    return encode(value.model_dump(mode="json"))
  if isinstance(value, BytesIO):
    value = value.getvalue()
  if isinstance(value, (bytes, bytearray)):
    return {"$gherila": "bytes", "value": base64.b64encode(value).decode("ascii")}
  if isinstance(value, int) and not isinstance(value, bool) and abs(value) > SAFE_INTEGER:
    return {"$gherila": "int", "value": str(value)}
  if isinstance(value, (datetime, date)):
    return value.isoformat()
  if isinstance(value, Path):
    return str(value)
  if isinstance(value, Mapping):
    return {str(key): encode(item) for key, item in value.items()}
  if isinstance(value, (list, tuple)):
    return [encode(item) for item in value]
  if value is None or isinstance(value, (str, bool, int)):
    return value
  if isinstance(value, float) and math.isfinite(value):
    return value
  raise TypeError(f"Unsupported result type: {type(value).__name__}")


def decode(value):
  if isinstance(value, list):
    return [decode(item) for item in value]
  if isinstance(value, dict):
    if set(value) == {"$gherila", "value"}:
      if value["$gherila"] == "int" and isinstance(value["value"], str):
        return int(value["value"])
      if value["$gherila"] == "bytes" and isinstance(value["value"], str):
        return base64.b64decode(value["value"], validate=True)
    return {key: decode(item) for key, item in value.items()}
  return value


def bind(function, args, kwargs):
  if not isinstance(args, list) or not isinstance(kwargs, dict):
    raise BridgeError("invalid_params", "args must be an array and kwargs/options an object.")
  try:
    signature = inspect.signature(function)
    bound = signature.bind(*decode(args), **decode(kwargs))
    for name, value in bound.arguments.items():
      annotation = signature.parameters[name].annotation
      if annotation is not inspect.Parameter.empty:
        bound.arguments[name] = TypeAdapter(annotation).validate_python(value)
    return bound
  except (TypeError, ValueError, ValidationError):
    # Validation errors can include input values such as credentials.
    raise BridgeError("invalid_params", "Arguments do not match the method signature. See describe.") from None


def methods(cls):
  return {
    name: function
    for name, function in inspect.getmembers(cls, inspect.iscoroutinefunction)
    if not name.startswith("_")
  }


def parameters(function):
  result = []
  for name, param in inspect.signature(function).parameters.items():
    if name == "self":
      continue
    item = {"name": name, "required": param.default is inspect.Parameter.empty}
    if not item["required"]:
      item["default"] = encode(param.default)
    if param.annotation is not inspect.Parameter.empty:
      item["schema"] = TypeAdapter(param.annotation).json_schema()
    result.append(item)
  return result


def describe():
  return {
    "protocol": 1,
    "platforms": {
      name: {
        "options": parameters(cls),
        "methods": {method: parameters(function) for method, function in methods(cls).items()},
      }
      for name, cls in PLATFORMS.items()
    },
  }


class Bridge:
  def __init__(self, timeout: float = 60):
    self.clients = {}
    self.timeout = timeout

  def create(self, request):
    platform = request.get("platform")
    if not isinstance(platform, str) or platform not in PLATFORMS:
      raise BridgeError("unknown_platform", "Unknown platform. See describe.")
    cls = PLATFORMS[platform]
    bound = bind(cls, [], request.get("options", {}))
    return cls(*bound.args, **bound.kwargs)

  async def dispatch(self, request):
    op = request.get("op", "call")
    if op == "describe":
      return describe()
    client_id = request.get("client")
    if client_id is not None and (not isinstance(client_id, str) or not client_id or len(client_id) > 128):
      raise BridgeError("invalid_request", "client must be a nonempty string of at most 128 characters.")
    if op == "create":
      if client_id is None:
        raise BridgeError("invalid_request", "create requires a client name.")
      if client_id in self.clients:
        raise BridgeError("client_exists", "This client already exists; close it first.")
      self.clients[client_id] = self.create(request)
      return {"client": client_id}
    if op not in ("call", "close"):
      raise BridgeError("invalid_request", "Unknown operation. Use describe, create, call or close.")
    if client_id is not None:
      if "platform" in request or "options" in request:
        raise BridgeError("invalid_request", "A named client already has its platform and options.")
      if client_id not in self.clients:
        raise BridgeError("unknown_client", "Create this client before using it.")
      client = self.clients[client_id]
    elif op == "call":
      client = self.create(request)
    else:
      raise BridgeError("invalid_request", "close requires a client name.")
    if op == "close":
      del self.clients[client_id]
      return None
    method = request.get("method")
    if not isinstance(method, str) or method not in methods(type(client)):
      raise BridgeError("unknown_method", "Only public async provider methods can be called. See describe.")
    function = getattr(client, method)
    bound = bind(function, request.get("args", []), request.get("kwargs", {}))
    return await asyncio.wait_for(function(*bound.args, **bound.kwargs), self.timeout)

  async def handle(self, request):
    response = {"version": 1, "id": None}
    try:
      if not isinstance(request, dict):
        raise BridgeError("invalid_request", "A request must be a JSON object.")
      request_id = request.get("id")
      if not (request_id is None or isinstance(request_id, str) or
              type(request_id) is int and abs(request_id) <= SAFE_INTEGER):
        raise BridgeError("invalid_request", "id must be a string, a safe integer or null.")
      response["id"] = request_id
      if type(request.get("version", 1)) is not int or request.get("version", 1) != 1:
        raise BridgeError("invalid_request", "Only protocol version 1 is supported.")
      response["result"] = encode(await self.dispatch(request))
    except BridgeError as exc:
      response["error"] = {"code": exc.code, "message": str(exc)}
    except asyncio.TimeoutError:
      response["error"] = {"code": "timeout", "message": "The provider call timed out."}
    except Exception as exc:
      # Upstream exceptions can contain cookies, proxy passwords or response bodies.
      response["error"] = {
        "code": "provider_error", "type": type(exc).__name__,
        "message": "The provider call failed. Check credentials, parameters and platform availability.",
      }
    return response


def parse(line):
  def reject_constant(value):
    raise ValueError("Non-finite JSON numbers are not supported.")
  return json.loads(line, parse_constant=reject_constant)


async def run(input_stream, output_stream, *, concurrency=8, timeout=60, max_line=MAX_LINE):
  bridge = Bridge(timeout)
  pending = set()
  output_lock = asyncio.Lock()

  async def write(response):
    data = (json.dumps(response, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n").encode("utf-8")
    async with output_lock:
      await asyncio.to_thread(output_stream.write, data)
      await asyncio.to_thread(output_stream.flush)

  async def respond(request):
    await write(await bridge.handle(request))

  try:
    while True:
      # Threads support ordinary redirected files and Windows pipes as well as Unix pipes.
      line = await asyncio.to_thread(input_stream.readline, max_line + 1)
      if not line:
        break
      if len(line) > max_line:
        while line and not line.endswith(b"\n"):
          line = await asyncio.to_thread(input_stream.readline, max_line + 1)
        await write({"version": 1, "id": None, "error": {
          "code": "request_too_large", "message": "Request exceeds the line size limit.",
        }})
        continue
      try:
        request = parse(line)
      except (ValueError, UnicodeError, RecursionError):
        await write({"version": 1, "id": None, "error": {
          "code": "invalid_json", "message": "Expected one UTF-8 JSON object per line.",
        }})
        continue
      if not isinstance(request, dict) or request.get("op", "call") != "call":
        # Lifecycle operations are barriers, so create/call/close can be pipelined safely.
        if pending:
          await asyncio.gather(*pending)
          pending.clear()
        await respond(request)
      else:
        if len(pending) >= concurrency:
          done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
          for task in done:
            task.result()
        pending.add(asyncio.create_task(respond(request)))
    if pending:
      await asyncio.gather(*pending)
  finally:
    for task in pending:
      if not task.done():
        task.cancel()
    await asyncio.gather(*pending, return_exceptions=True)
    bridge.clients.clear()


def main():
  parser = ArgumentParser(description=__doc__)
  parser.add_argument("command", nargs="?", choices=["install"],
    help="After launcher setup, print the ready runtime as JSON and exit without reading stdin.")
  parser.add_argument("--describe", action="store_true", help="Print the available providers and method signatures, then exit.")
  parser.add_argument("--concurrency", type=int, default=8, help="Maximum simultaneous calls (default: 8).")
  parser.add_argument("--timeout", type=float, default=60, help="Timeout per provider call in seconds (default: 60).")
  args = parser.parse_args()
  if args.concurrency < 1 or not math.isfinite(args.timeout) or args.timeout <= 0:
    parser.error("concurrency and timeout must be positive finite numbers")
  output = sys.stdout.buffer
  if args.command == "install":
    # The OS launcher provisions Python and dependencies before reaching here.
    # One shared report keeps every language's installer contract identical.
    output.write((json.dumps({"python": sys.executable,
      "args": ["-I", "-X", "utf8", "-u", "-m", "gherila"], "protocol": 1},
      ensure_ascii=False) + "\n").encode("utf-8"))
    output.flush()
    return
  if args.describe:
    output.write((json.dumps(describe(), ensure_ascii=False) + "\n").encode("utf-8"))
    output.flush()
    return
  # Reserve stdout for protocol frames, including if a provider prints diagnostics.
  sys.stdout = sys.stderr
  try:
    asyncio.run(run(sys.stdin.buffer, output, concurrency=args.concurrency, timeout=args.timeout))
  except (BrokenPipeError, KeyboardInterrupt):
    pass


if __name__ == "__main__":
  main()
