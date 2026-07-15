"""Application configuration and workspace-root resolution.

Everything Azimut persists lives under one root directory (default ``~/Azimut``,
overridable with the ``AZIMUT_HOME`` environment variable):

    ~/Azimut/
    ├── cases/       # named investigations
    ├── scratch/     # one-shot sessions (promotable to cases)
    └── settings.json

No database server — plain files only (spec §4).
"""

from __future__ import annotations

import copy
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_SETTINGS: dict[str, Any] = {
    # Extra XYZ tile providers added by the user (spec §6 v1 notes).
    # Each: {"id", "label", "url" ({x}/{y}/{z} template), "attribution", "max_zoom"}
    "tile_providers": [],
    # Optional user-supplied API keys, keyed by provider id. Never required.
    # Built-in keyed providers (Mapbox, Google) read their token from here:
    # "mapbox": "pk....", "google": "AIza...".
    "api_keys": {},
    # Per-provider monthly tile-request counters: {"<provider_id>": {"YYYY-MM": count}}.
    # Local bookkeeping only, for billed keyed providers (Mapbox, Google).
    "usage": {},
    # Keyed-provider preferences (docs/IMAGERY_PROVIDERS.md):
    # - providers_enabled: {"mapbox": bool, "google": bool} — absent means enabled;
    #   a saved key can be kept while the basemap is hidden from the selector.
    # - usage_overrides: {"mapbox": bool, ...} — serve past the 90% soft block,
    #   accepting the provider's billing. Off by default.
    # - eco_zoom_fallback: at low zoom (≤ eco_max_zoom) the live map swaps a
    #   billed basemap for free imagery; paid detail only matters zoomed in.
    "providers_enabled": {},
    "usage_overrides": {},
    "eco_zoom_fallback": True,
    "eco_max_zoom": 15,
}

# Documented monthly free allowances per meter, in tile requests (verified
# 2026-07: Google 2D Map Tiles 100k then $0.60/1k, and ≤15k/day; Mapbox Static
# Tiles 200k then $0.50/1k). A yardstick, not a guarantee — mirror of
# frontend/src/lib/usage.js FREE_TIER.
FREE_TIER = {"mapbox": 200_000, "google": 100_000}
# Share of the free tier past which metered providers stop serving unless the
# user flips the per-provider override in Settings.
BLOCK_SHARE = 0.9
# Eco mode default: visual zoom at or below which free imagery replaces a
# billed basemap. The live value is the user's settings.json `eco_max_zoom`.
ECO_MAX_ZOOM = 15


def workspace_root() -> Path:
    root = Path(os.environ.get("AZIMUT_HOME", "~/Azimut")).expanduser()
    return root


def cases_dir() -> Path:
    return workspace_root() / "cases"


def scratch_dir() -> Path:
    return workspace_root() / "scratch"


def settings_path() -> Path:
    return workspace_root() / "settings.json"


def ensure_workspace() -> None:
    """Create the workspace skeleton if missing (idempotent)."""
    cases_dir().mkdir(parents=True, exist_ok=True)
    scratch_dir().mkdir(parents=True, exist_ok=True)
    if not settings_path().exists():
        save_settings(DEFAULT_SETTINGS)


def load_settings() -> dict[str, Any]:
    # deep copies: callers mutate nested dicts (usage counters, prefs), and a
    # shallow copy would let that leak into DEFAULT_SETTINGS itself
    try:
        data = json.loads(settings_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return copy.deepcopy(DEFAULT_SETTINGS)
    merged = copy.deepcopy(DEFAULT_SETTINGS)
    merged.update(data)
    return merged


def save_settings(settings: dict[str, Any]) -> None:
    settings_path().parent.mkdir(parents=True, exist_ok=True)
    settings_path().write_text(
        json.dumps(settings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def month_key(when: datetime | None = None) -> str:
    """The usage-counter bucket for a moment in time: "YYYY-MM" (UTC)."""
    return (when or datetime.now(timezone.utc)).strftime("%Y-%m")


_usage_lock = threading.Lock()  # tile proxy bumps the counter from many threads


def record_usage(meter: str, count: int = 1, when: datetime | None = None) -> int:
    """Bump a provider's tile counter for the month; returns the new total.

    Local bookkeeping only (docs/IMAGERY_PROVIDERS.md): billed keyed providers
    (Mapbox, Google) get a per-month tally so the user can watch their quota.
    No telemetry — the counter never leaves settings.json.
    """
    with _usage_lock:
        settings = load_settings()
        per_month = settings.setdefault("usage", {}).setdefault(meter, {})
        bucket = month_key(when)
        per_month[bucket] = int(per_month.get(bucket, 0)) + int(count)
        save_settings(settings)
        return per_month[bucket]


def month_usage(meter: str, settings: dict[str, Any] | None = None) -> int:
    """This month's tile tally for a meter."""
    settings = settings or load_settings()
    return int((settings.get("usage", {}).get(meter) or {}).get(month_key(), 0))


def usage_blocked(meter: str, settings: dict[str, Any] | None = None) -> bool:
    """True when a metered provider passed BLOCK_SHARE of its free tier and the
    user hasn't opted into overage billing for it (docs/IMAGERY_PROVIDERS.md)."""
    free = FREE_TIER.get(meter)
    if not free:
        return False
    settings = settings or load_settings()
    if settings.get("usage_overrides", {}).get(meter):
        return False
    return month_usage(meter, settings) >= free * BLOCK_SHARE
