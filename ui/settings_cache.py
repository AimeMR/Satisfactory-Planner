"""
ui/settings_cache.py
In-memory cache for UI settings to avoid DB reads on every paint() call.

The cache is populated at startup and refreshed only when a setting is toggled.
"""

from __future__ import annotations

_cache: dict[str, str] = {}
_initialized = False


def _init_cache() -> None:
    """Load all display-related settings from the DB once."""
    global _cache, _initialized
    from database.crud import get_setting
    _cache = {
        "show_power":  get_setting("show_power",  "true") or "true",
        "show_inputs": get_setting("show_inputs", "true") or "true",
        "show_output": get_setting("show_output", "true") or "true",
        "show_belts":  get_setting("show_belts",  "true") or "true",
    }
    _initialized = True


def get_cached_setting(key: str) -> str:
    """Return a cached setting value. Initialises the cache on first call."""
    if not _initialized:
        _init_cache()
    return _cache.get(key, "true")


def set_cached_setting(key: str, value: str) -> None:
    """Update both the DB and the in-memory cache."""
    from database.crud import set_setting
    set_setting(key, value)
    _cache[key] = value
