"""Async platform clients. Optional adapters are imported only when requested."""

from importlib import import_module

__version__ = "1.4.0"
__all__ = ["Brave", "GitHub", "Instagram", "Reddit", "Snapchat", "TikTok", "Twitter"]
_MODULES = {name: name.lower() for name in __all__}


def __getattr__(name):
    if name not in _MODULES:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(f".{_MODULES[name]}", __name__), name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(__all__))
