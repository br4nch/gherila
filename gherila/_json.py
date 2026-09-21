"""Optional acceleration; the base package never requires a Rust toolchain."""

try:
    from orjson import loads
except ImportError:
    from json import loads

__all__ = ["loads"]
