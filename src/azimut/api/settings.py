"""REST API for app-wide settings: API keys and per-provider usage counters.

Keys are the user's own billing identity (docs/IMAGERY_PROVIDERS.md): stored
locally in settings.json, app-wide (never per-case), never written into a case
folder or export bundle. Usage counters are local bookkeeping only.
"""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import config
from ..engine import google_tiles, tiles

router = APIRouter(prefix="/api", tags=["settings"])

# the keyed providers the settings tab manages — matching api_keys entries
# light up the built-in basemaps (engine/tiles.py all_providers)
KEYED_PROVIDERS = ("mapbox", "google")


class KeysIn(BaseModel):
    # None = leave untouched; "" (or whitespace) = remove the stored key
    mapbox: str | None = None
    google: str | None = None


class PrefsIn(BaseModel):
    """Keyed-provider preferences — None leaves a field untouched."""

    # {"mapbox": bool, "google": bool}: basemap on/off without touching the key
    providers_enabled: dict[str, bool] | None = None
    # {"mapbox": bool, ...}: keep serving past the 90% soft block (billed)
    usage_overrides: dict[str, bool] | None = None
    # swap billed basemaps for free imagery at low zoom (≤ eco_max_zoom)
    eco_zoom_fallback: bool | None = None
    eco_max_zoom: int | None = None  # clamped to a sane zoom range


@router.get("/settings")
def get_settings() -> dict[str, Any]:
    settings = config.load_settings()
    return {
        "api_keys": settings.get("api_keys", {}),
        "usage": settings.get("usage", {}),
        "month": config.month_key(),
        "providers_enabled": settings.get("providers_enabled", {}),
        "usage_overrides": settings.get("usage_overrides", {}),
        "eco_zoom_fallback": bool(settings.get("eco_zoom_fallback", True)),
        "eco_max_zoom": int(settings.get("eco_max_zoom", config.ECO_MAX_ZOOM)),
        # server-side constants the UI mirrors
        "free_tier": config.FREE_TIER,
        "block_share": config.BLOCK_SHARE,
    }


@router.put("/settings/prefs")
def put_prefs(body: PrefsIn) -> dict[str, Any]:
    settings = config.load_settings()
    if body.providers_enabled is not None:
        merged = dict(settings.get("providers_enabled", {}))
        merged.update({k: bool(v) for k, v in body.providers_enabled.items() if k in KEYED_PROVIDERS})
        settings["providers_enabled"] = merged
    if body.usage_overrides is not None:
        merged = dict(settings.get("usage_overrides", {}))
        merged.update({k: bool(v) for k, v in body.usage_overrides.items() if k in KEYED_PROVIDERS})
        settings["usage_overrides"] = merged
    if body.eco_zoom_fallback is not None:
        settings["eco_zoom_fallback"] = bool(body.eco_zoom_fallback)
    if body.eco_max_zoom is not None:
        settings["eco_max_zoom"] = max(1, min(21, int(body.eco_max_zoom)))
    config.save_settings(settings)
    return {
        "providers_enabled": settings.get("providers_enabled", {}),
        "usage_overrides": settings.get("usage_overrides", {}),
        "eco_zoom_fallback": bool(settings.get("eco_zoom_fallback", True)),
        "eco_max_zoom": int(settings.get("eco_max_zoom", config.ECO_MAX_ZOOM)),
    }


@router.put("/settings/keys")
def put_keys(body: KeysIn) -> dict[str, Any]:
    settings = config.load_settings()
    keys = settings.setdefault("api_keys", {})
    for name in KEYED_PROVIDERS:
        value = getattr(body, name)
        if value is None:
            continue
        value = value.strip()
        if value:
            keys[name] = value
        else:
            keys.pop(name, None)
    config.save_settings(settings)
    return {"api_keys": keys}


@router.post("/settings/keys/{provider}/test")
def test_key(provider: str) -> dict[str, Any]:
    """Exercise the saved key against the real service — never raises on a bad
    key, so the settings tab can show the provider's error message inline."""
    key = (config.load_settings().get("api_keys") or {}).get(provider)
    if not key:
        raise HTTPException(status_code=404, detail=f"no {provider} key saved")
    if provider == "google":
        try:
            google_tiles.invalidate(key)  # force a fresh mint — that's the test
            google_tiles.session_token(key)
            return {"ok": True, "detail": "session token created"}
        except Exception as exc:
            return {"ok": False, "detail": str(exc)}
    if provider == "mapbox":
        url = tiles.MAPBOX_SATELLITE_URL.replace("{key}", key).format(z=0, x=0, y=0)
        try:
            response = httpx.get(url, headers={"User-Agent": tiles.USER_AGENT}, timeout=10)
            response.raise_for_status()
            return {"ok": True, "detail": "tile fetched"}
        except Exception as exc:
            return {"ok": False, "detail": str(exc)}
    raise HTTPException(status_code=404, detail=f"unknown keyed provider '{provider}'")
