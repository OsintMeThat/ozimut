"""REST API for app-wide settings: API keys, usage counters, and the signature.

Keys are the user's own billing identity (docs/IMAGERY_PROVIDERS.md): stored
locally in settings.json, app-wide (never per-case), never written into a case
folder or export bundle. Usage counters are local bookkeeping only. The
signature (the analyst's logo) follows the same rule — one file beside
settings.json, reaching a case only as pixels in a rendered proof PNG.
"""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .. import __version__, config
from ..engine import google_tiles, scrapers, tiles

router = APIRouter(prefix="/api", tags=["settings"])

# the keyed providers the settings tab manages — matching api_keys entries
# light up the built-in basemaps (engine/tiles.py all_providers)
KEYED_PROVIDERS = ("mapbox", "google")

DEFAULT_HOME_VIEW = config.DEFAULT_SETTINGS["home_view"]
DEFAULT_POST_MENTION = config.DEFAULT_SETTINGS["post_mention"]


class KeysIn(BaseModel):
    # None = leave untouched; "" (or whitespace) = remove the stored key
    mapbox: str | None = None
    google: str | None = None


class HomeView(BaseModel):
    """The map view the Satellite tab opens on. Rejected outside the world."""

    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    zoom: int = Field(ge=1, le=21)


class PrefsIn(BaseModel):
    """Keyed-provider and display preferences — None leaves a field untouched."""

    # {"mapbox": bool, "google": bool}: basemap on/off without touching the key
    providers_enabled: dict[str, bool] | None = None
    # {"mapbox": bool, ...}: keep serving past the 90% soft block (billed)
    usage_overrides: dict[str, bool] | None = None
    # swap billed basemaps for free imagery at low zoom (≤ eco_max_zoom)
    eco_zoom_fallback: bool | None = None
    eco_max_zoom: int | None = None  # clamped to a sane zoom range
    # display preferences — presentation only, never touches stored artifacts
    coord_format: str | None = None  # one of config.COORD_FORMATS
    units: str | None = None  # one of config.UNIT_SYSTEMS
    home_view: HomeView | None = None  # where the Satellite tab opens
    post_mention: str | None = None  # handle a new post draft is addressed to


def _prefs(settings: dict[str, Any]) -> dict[str, Any]:
    """The preference block shared by GET /settings and PUT /settings/prefs."""
    return {
        "providers_enabled": settings.get("providers_enabled", {}),
        "usage_overrides": settings.get("usage_overrides", {}),
        "eco_zoom_fallback": bool(settings.get("eco_zoom_fallback", True)),
        "eco_max_zoom": int(settings.get("eco_max_zoom", config.ECO_MAX_ZOOM)),
        "coord_format": settings.get("coord_format", "dd"),
        "units": settings.get("units", "metric"),
        "home_view": settings.get("home_view", DEFAULT_HOME_VIEW),
        "post_mention": settings.get("post_mention", DEFAULT_POST_MENTION),
    }


@router.get("/settings")
def get_settings() -> dict[str, Any]:
    settings = config.load_settings()
    return {
        "api_keys": settings.get("api_keys", {}),
        "usage": settings.get("usage", {}),
        "month": config.month_key(),
        # whether a logo is on disk — the proof composer's signature control is
        # dead until one is, so it needs to know without fetching the pixels
        "signature": config.signature_path().is_file(),
        **_prefs(settings),
        # server-side constants the UI mirrors
        "free_tier": config.FREE_TIER,
        "block_share": config.BLOCK_SHARE,
        # About tab: what this build is, and where it keeps its files
        "version": __version__,
        "workspace_root": str(config.workspace_root()),
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
    if body.coord_format is not None:
        if body.coord_format not in config.COORD_FORMATS:
            raise HTTPException(status_code=422, detail=f"unknown coord_format '{body.coord_format}'")
        settings["coord_format"] = body.coord_format
    if body.units is not None:
        if body.units not in config.UNIT_SYSTEMS:
            raise HTTPException(status_code=422, detail=f"unknown units '{body.units}'")
        settings["units"] = body.units
    if body.home_view is not None:
        settings["home_view"] = body.home_view.model_dump()
    if body.post_mention is not None:
        settings["post_mention"] = body.post_mention.strip()[:64]
    config.save_settings(settings)
    return _prefs(settings)


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


# ---- signature: the analyst's logo, stamped onto proofs they choose to sign ---


@router.get("/settings/signature.png")
def get_signature() -> FileResponse:
    path = config.signature_path()
    if not path.is_file():
        raise HTTPException(status_code=404, detail="no signature saved")
    return FileResponse(path, media_type="image/png")


@router.post("/settings/signature")
async def put_signature(file: UploadFile) -> dict[str, Any]:
    """Replace the stored logo. PNG only, and small — see config.PNG_MAGIC."""
    data = await file.read(config.SIGNATURE_MAX_BYTES + 1)
    if len(data) > config.SIGNATURE_MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"signature must be under {config.SIGNATURE_MAX_BYTES // 1024 // 1024} MB",
        )
    # sniff the bytes rather than trust the filename or the browser's content-type
    if not data.startswith(config.PNG_MAGIC):
        raise HTTPException(status_code=422, detail="signature must be a PNG image")
    path = config.signature_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return {"signature": True}


@router.delete("/settings/signature")
def delete_signature() -> dict[str, Any]:
    config.signature_path().unlink(missing_ok=True)
    return {"signature": False}


# ---- scrapers: the two dependencies that rot on someone else's schedule -------


@router.get("/settings/scrapers")
def get_scrapers(check: bool = False) -> dict[str, Any]:
    """Versions of yt-dlp/gallery-dl in use. ``check=true`` asks PyPI what's newer.

    The check is opt-in and user-triggered: Azimut is local-first, so merely
    opening Settings must never reach the network (engine/scrapers.py status()).
    """
    return {"scrapers": scrapers.status(check_pypi=check)}


@router.post("/settings/scrapers/{dist}/update")
def update_scraper(dist: str) -> dict[str, Any]:
    """Fetch the latest wheel for one scraper into the workspace.

    Never raises on a failed download — the settings tab shows the reason
    inline, the same way the API-key test does. The previous copy stays live.
    """
    if dist not in scrapers.SCRAPERS:
        raise HTTPException(status_code=404, detail=f"unknown scraper '{dist}'")
    try:
        return {"ok": True, **scrapers.update(dist)}
    except Exception as exc:
        return {"ok": False, "dist": dist, "detail": str(exc)}


@router.delete("/settings/scrapers/{dist}")
def reset_scraper(dist: str) -> dict[str, Any]:
    """Discard the updated copy and go back to the version this build shipped."""
    if dist not in scrapers.SCRAPERS:
        raise HTTPException(status_code=404, detail=f"unknown scraper '{dist}'")
    return {"ok": True, **scrapers.reset(dist)}
