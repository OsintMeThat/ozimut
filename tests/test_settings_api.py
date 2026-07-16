"""Settings API: API keys management, key tests, usage counters (all offline)."""

import httpx

from azimut import config
from azimut.engine import google_tiles, scrapers


def test_get_settings_defaults(client):
    body = client.get("/api/settings").json()
    assert body["api_keys"] == {}
    assert body["usage"] == {}
    assert body["month"] == config.month_key()


def test_put_keys_lights_up_keyed_providers(client):
    saved = client.put("/api/settings/keys", json={"mapbox": "pk.abc"}).json()
    assert saved["api_keys"] == {"mapbox": "pk.abc"}
    ids = {p["id"] for p in client.get("/api/satellite/providers").json()}
    assert "mapbox-satellite" in ids
    assert "google-satellite" not in ids  # no google key yet

    client.put("/api/settings/keys", json={"google": "AIza.x"})
    providers = {p["id"]: p for p in client.get("/api/satellite/providers").json()}
    assert "mapbox-satellite" in providers  # untouched key survives a partial PUT
    google = providers["google-satellite"]
    assert google["capturable"] is True
    assert google["cacheable"] is False
    assert google["session"] == "google"
    assert google["meter"] == "google"


def test_put_empty_key_removes_it(client):
    client.put("/api/settings/keys", json={"mapbox": "pk.abc"})
    saved = client.put("/api/settings/keys", json={"mapbox": "  "}).json()
    assert saved["api_keys"] == {}
    ids = {p["id"] for p in client.get("/api/satellite/providers").json()}
    assert "mapbox-satellite" not in ids


def test_keys_never_reach_a_case_folder(client, monkeypatch):
    """Principle 7: keys live in settings.json only — nothing under cases/."""
    from PIL import Image

    from azimut.engine import tiles

    monkeypatch.setattr(
        tiles, "_default_fetch", lambda c, u: Image.new("RGB", (256, 256), (9, 9, 9))
    )
    client.put("/api/settings/keys", json={"mapbox": "pk.SECRET"})
    cid = client.post("/api/cases", json={"name": "K"}).json()["id"]
    client.post(
        f"/api/cases/{cid}/satellite/capture",
        json={"lat": 48.85, "lon": 2.29, "zoom": 15, "width": 512, "height": 512,
              "provider": "mapbox-satellite"},
    )
    case_dir = config.cases_dir() / cid
    hits = [
        p for p in case_dir.rglob("*")
        if p.is_file() and p.suffix in (".json", ".md") and "pk.SECRET" in p.read_text()
    ]
    assert hits == []


def _upstream(status=200, content=b"JPEGDATA", headers=None):
    def get(url, **kwargs):
        get.urls.append(url)
        return httpx.Response(
            status, content=content,
            headers={"content-type": "image/jpeg", **(headers or {})},
            request=httpx.Request("GET", url),
        )

    get.urls = []
    return get


def test_tile_proxy_serves_and_counts_exactly(client, monkeypatch):
    client.put("/api/settings/keys", json={"mapbox": "pk.abc"})
    upstream = _upstream(headers={"cache-control": "max-age=43200"})
    monkeypatch.setattr(httpx, "get", upstream)

    r = client.get("/api/tiles/mapbox-satellite/14/8298/5639")
    assert r.status_code == 200
    assert r.content == b"JPEGDATA"
    assert r.headers["content-type"] == "image/jpeg"
    # provider cache policy passed through so the browser caches (and a cached
    # tile never re-hits the proxy — the counter can't over-count)
    assert r.headers["cache-control"] == "max-age=43200"
    assert "access_token=pk.abc" in upstream.urls[0]
    assert "/tiles/512/14/8298/5639" in upstream.urls[0]

    client.get("/api/tiles/mapbox-satellite/14/8298/5640")
    body = client.get("/api/settings").json()
    assert body["usage"]["mapbox"][body["month"]] == 2  # one bump per served tile


def test_tile_proxy_does_not_count_errors(client, monkeypatch):
    client.put("/api/settings/keys", json={"mapbox": "pk.abc"})
    monkeypatch.setattr(httpx, "get", _upstream(status=404, content=b""))
    r = client.get("/api/tiles/mapbox-satellite/14/0/0")
    assert r.status_code == 404
    assert client.get("/api/settings").json()["usage"] == {}


def test_tile_proxy_unknown_provider_404(client):
    assert client.get("/api/tiles/nope/14/0/0").status_code == 404


def test_tile_proxy_google_remints_session_on_403(client, monkeypatch):
    client.put("/api/settings/keys", json={"google": "AIza.x"})
    tokens = iter(["tok-stale", "tok-fresh"])
    monkeypatch.setattr(
        google_tiles, "resolve_template", lambda url, **kw: url.replace("{session}", next(tokens))
    )
    invalidated = []
    monkeypatch.setattr(google_tiles, "invalidate", invalidated.append)

    def get(url, **kwargs):
        status = 403 if "session=tok-stale" in url else 200
        return httpx.Response(
            status, content=b"TILE", headers={"content-type": "image/jpeg"},
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "get", get)
    r = client.get("/api/tiles/google-satellite/15/16597/11278")
    assert r.status_code == 200
    assert r.content == b"TILE"
    assert invalidated == ["AIza.x"]
    body = client.get("/api/settings").json()
    assert body["usage"]["google"][body["month"]] == 1  # the retry isn't double-counted


def test_get_settings_exposes_prefs_and_free_tier(client):
    body = client.get("/api/settings").json()
    assert body["free_tier"] == config.FREE_TIER
    assert body["block_share"] == config.BLOCK_SHARE
    assert body["eco_max_zoom"] == config.ECO_MAX_ZOOM
    assert body["eco_zoom_fallback"] is True
    assert body["providers_enabled"] == {}
    assert body["usage_overrides"] == {}


def test_put_prefs_roundtrips_and_filters_unknown_providers(client):
    saved = client.put(
        "/api/settings/prefs",
        json={
            "providers_enabled": {"mapbox": False, "bogus": False},
            "usage_overrides": {"google": True},
            "eco_zoom_fallback": False,
        },
    ).json()
    assert saved["providers_enabled"] == {"mapbox": False}  # unknown ids dropped
    assert saved["usage_overrides"] == {"google": True}
    assert saved["eco_zoom_fallback"] is False
    # partial PUT leaves other prefs untouched
    saved = client.put("/api/settings/prefs", json={"eco_zoom_fallback": True}).json()
    assert saved["providers_enabled"] == {"mapbox": False}
    assert saved["eco_zoom_fallback"] is True


def test_disabled_provider_hidden_but_key_kept(client):
    client.put("/api/settings/keys", json={"mapbox": "pk.abc"})
    client.put("/api/settings/prefs", json={"providers_enabled": {"mapbox": False}})
    ids = {p["id"] for p in client.get("/api/satellite/providers").json()}
    assert "mapbox-satellite" not in ids
    assert client.get("/api/settings").json()["api_keys"] == {"mapbox": "pk.abc"}
    client.put("/api/settings/prefs", json={"providers_enabled": {"mapbox": True}})
    ids = {p["id"] for p in client.get("/api/satellite/providers").json()}
    assert "mapbox-satellite" in ids


def test_tile_proxy_blocks_at_soft_limit_and_override_lifts(client, monkeypatch):
    client.put("/api/settings/keys", json={"mapbox": "pk.abc"})
    monkeypatch.setattr(httpx, "get", _upstream())
    config.record_usage("mapbox", int(config.FREE_TIER["mapbox"] * config.BLOCK_SHARE))

    r = client.get("/api/tiles/mapbox-satellite/14/8298/5639")
    assert r.status_code == 429
    assert "Settings" in r.json()["detail"]

    client.put("/api/settings/prefs", json={"usage_overrides": {"mapbox": True}})
    assert client.get("/api/tiles/mapbox-satellite/14/8298/5639").status_code == 200


def test_tile_proxy_disk_cache_serves_repeats_without_rebilling(client, monkeypatch):
    client.put("/api/settings/keys", json={"mapbox": "pk.abc"})
    upstream = _upstream()
    monkeypatch.setattr(httpx, "get", upstream)

    assert client.get("/api/tiles/mapbox-satellite/14/8298/5639").status_code == 200
    r = client.get("/api/tiles/mapbox-satellite/14/8298/5639")
    assert r.status_code == 200
    assert r.content == b"JPEGDATA"
    assert len(upstream.urls) == 1  # second hit came from the disk cache
    body = client.get("/api/settings").json()
    assert body["usage"]["mapbox"][body["month"]] == 1  # cache hits aren't billed


def test_tile_proxy_never_caches_google(client, monkeypatch):
    client.put("/api/settings/keys", json={"google": "AIza.x"})
    monkeypatch.setattr(
        google_tiles, "resolve_template", lambda url, **kw: url.replace("{session}", "tok")
    )
    upstream = _upstream()
    monkeypatch.setattr(httpx, "get", upstream)

    client.get("/api/tiles/google-satellite/15/16597/11278")
    client.get("/api/tiles/google-satellite/15/16597/11278")
    assert len(upstream.urls) == 2  # terms forbid a disk cache — always upstream
    assert not (config.workspace_root() / "tile-cache" / "google-satellite").exists()
    body = client.get("/api/settings").json()
    assert body["usage"]["google"][body["month"]] == 2


def _png_tile(size=256, colour=(30, 90, 200)):
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (size, size), colour).save(buf, format="PNG")
    return buf.getvalue()


def test_tile_proxy_overzoom_fills_coverage_gaps(client, monkeypatch):
    parent_png = _png_tile()

    def get(url, **kwargs):
        get.urls.append(url)
        # imagery ends at z18: deeper levels 404, the parent level serves
        if "/tile/19/" in url:
            return httpx.Response(404, content=b"", request=httpx.Request("GET", url))
        return httpx.Response(
            200, content=parent_png, headers={"content-type": "image/png"},
            request=httpx.Request("GET", url),
        )

    get.urls = []
    monkeypatch.setattr(httpx, "get", get)

    r = client.get("/api/tiles/esri-world-imagery/19/155000/400000")
    assert r.status_code == 200
    assert r.headers["x-azimut-overzoom"] == "1"
    assert r.headers["content-type"] == "image/png"
    # served tile is a full-size upscale of the parent quadrant
    import io

    from PIL import Image

    img = Image.open(io.BytesIO(r.content))
    assert img.size == (256, 256)


def test_tile_proxy_placeholder_tile_triggers_overzoom(client, monkeypatch):
    import hashlib

    from azimut.engine import tiles

    placeholder = b"esri-map-data-not-yet-available"
    monkeypatch.setattr(
        tiles, "PLACEHOLDER_TILE_SHA256", frozenset({hashlib.sha256(placeholder).hexdigest()})
    )
    parent_png = _png_tile(colour=(120, 40, 40))

    def get(url, **kwargs):
        body, ctype = (
            (placeholder, "image/jpeg") if "/tile/19/" in url else (parent_png, "image/png")
        )
        return httpx.Response(
            200, content=body, headers={"content-type": ctype},
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "get", get)
    r = client.get("/api/tiles/esri-world-imagery/19/155000/400000")
    assert r.status_code == 200
    assert r.headers["x-azimut-overzoom"] == "1"


def test_test_key_without_saved_key_is_404(client):
    assert client.post("/api/settings/keys/mapbox/test").status_code == 404
    assert client.post("/api/settings/keys/unknown/test").status_code == 404


def test_test_key_mapbox_ok_and_failure(client, monkeypatch):
    client.put("/api/settings/keys", json={"mapbox": "pk.abc"})

    def ok(url, **kwargs):
        assert "access_token=pk.abc" in url
        return httpx.Response(200, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", ok)
    assert client.post("/api/settings/keys/mapbox/test").json()["ok"] is True

    def unauthorized(url, **kwargs):
        return httpx.Response(401, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", unauthorized)
    result = client.post("/api/settings/keys/mapbox/test").json()
    assert result["ok"] is False
    assert result["detail"]


def test_test_key_google_mints_a_session(client, monkeypatch):
    client.put("/api/settings/keys", json={"google": "AIza.x"})
    minted = []

    def fake_token(key, **kwargs):
        minted.append(key)
        return "tok"

    monkeypatch.setattr(google_tiles, "session_token", fake_token)
    assert client.post("/api/settings/keys/google/test").json()["ok"] is True
    assert minted == ["AIza.x"]


def test_providers_expose_tile_size(client):
    client.put("/api/settings/keys", json={"mapbox": "pk.abc", "google": "AIza.x"})
    providers = {p["id"]: p for p in client.get("/api/satellite/providers").json()}
    assert providers["esri-world-imagery"]["tile_size"] == 256
    assert providers["esri-world-imagery"]["oversample"] == 1
    assert providers["mapbox-satellite"]["tile_size"] == 512  # 4× cheaper, same m/px
    assert providers["mapbox-satellite"]["oversample"] == 1  # its @2x is upsampled — no gain
    assert providers["google-satellite"]["tile_size"] == 1024  # hi-DPI 4x session
    # the live map shows Google one zoom deeper (mid-zoom mosaics are soft)
    assert providers["google-satellite"]["oversample"] == 2


def test_put_prefs_eco_max_zoom_clamped(client):
    saved = client.put("/api/settings/prefs", json={"eco_max_zoom": 15}).json()
    assert saved["eco_max_zoom"] == 15
    assert client.get("/api/settings").json()["eco_max_zoom"] == 15
    assert client.put("/api/settings/prefs", json={"eco_max_zoom": 99}).json()["eco_max_zoom"] == 21
    assert client.put("/api/settings/prefs", json={"eco_max_zoom": -3}).json()["eco_max_zoom"] == 1


def test_display_prefs_default_and_round_trip(client):
    body = client.get("/api/settings").json()
    assert body["coord_format"] == "dd"
    assert body["units"] == "metric"

    saved = client.put("/api/settings/prefs", json={"coord_format": "mgrs", "units": "imperial"})
    assert saved.json()["coord_format"] == "mgrs"
    assert saved.json()["units"] == "imperial"
    reloaded = client.get("/api/settings").json()
    assert reloaded["coord_format"] == "mgrs"
    assert reloaded["units"] == "imperial"


def test_display_prefs_reject_unknown_values(client):
    assert client.put("/api/settings/prefs", json={"coord_format": "utm"}).status_code == 422
    assert client.put("/api/settings/prefs", json={"units": "furlongs"}).status_code == 422
    # a rejected value leaves the stored preference alone
    assert client.get("/api/settings").json()["coord_format"] == "dd"


def test_partial_prefs_put_leaves_other_fields_untouched(client):
    client.put("/api/settings/prefs", json={"coord_format": "dms", "units": "imperial"})
    saved = client.put("/api/settings/prefs", json={"eco_max_zoom": 12}).json()
    assert saved["coord_format"] == "dms"  # untouched by an unrelated PUT
    assert saved["units"] == "imperial"


def test_home_view_default_and_round_trip(client):
    assert client.get("/api/settings").json()["home_view"] == config.DEFAULT_SETTINGS["home_view"]

    view = {"lat": -33.8568, "lon": 151.2153, "zoom": 18}
    assert client.put("/api/settings/prefs", json={"home_view": view}).json()["home_view"] == view
    assert client.get("/api/settings").json()["home_view"] == view


def test_home_view_rejects_points_off_the_globe(client):
    bad = [
        {"lat": 91, "lon": 0, "zoom": 16},
        {"lat": 0, "lon": -181, "zoom": 16},
        {"lat": 0, "lon": 0, "zoom": 0},
        {"lat": 0, "lon": 0, "zoom": 30},
    ]
    for view in bad:
        assert client.put("/api/settings/prefs", json={"home_view": view}).status_code == 422
    assert client.get("/api/settings").json()["home_view"] == config.DEFAULT_SETTINGS["home_view"]


def test_about_facts_are_served(client):
    body = client.get("/api/settings").json()
    assert body["version"]
    assert body["workspace_root"] == str(config.workspace_root())


# ---- signature: the analyst's logo, app-wide and never inside a case ---------

# the smallest thing that is genuinely a PNG: the 8-byte magic is what the
# upload sniffs, so a body starting with it is accepted and nothing else is
PNG = config.PNG_MAGIC + b"\x00 fake body, never decoded"


def test_signature_absent_by_default(client):
    assert client.get("/api/settings").json()["signature"] is False
    assert client.get("/api/settings/signature.png").status_code == 404


def test_signature_upload_serve_and_delete(client):
    saved = client.post("/api/settings/signature", files={"file": ("logo.png", PNG, "image/png")})
    assert saved.status_code == 200
    assert saved.json() == {"signature": True}
    assert client.get("/api/settings").json()["signature"] is True

    served = client.get("/api/settings/signature.png")
    assert served.status_code == 200
    assert served.content == PNG
    assert served.headers["content-type"] == "image/png"

    assert client.delete("/api/settings/signature").json() == {"signature": False}
    assert client.get("/api/settings").json()["signature"] is False
    assert client.get("/api/settings/signature.png").status_code == 404


def test_signature_replace_overwrites_in_place(client):
    client.post("/api/settings/signature", files={"file": ("a.png", PNG, "image/png")})
    other = config.PNG_MAGIC + b"\x00 second logo"
    client.post("/api/settings/signature", files={"file": ("b.png", other, "image/png")})
    assert client.get("/api/settings/signature.png").content == other


def test_signature_delete_is_idempotent(client):
    assert client.delete("/api/settings/signature").json() == {"signature": False}


def test_signature_rejects_non_png(client):
    # the bytes are what count, not the name or the content-type the browser sent
    body = client.post("/api/settings/signature", files={"file": ("logo.png", b"GIF89a...", "image/png")})
    assert body.status_code == 422
    assert "PNG" in body.json()["detail"]
    assert client.get("/api/settings").json()["signature"] is False


def test_signature_rejects_oversized(client):
    huge = config.PNG_MAGIC + b"\x00" * config.SIGNATURE_MAX_BYTES
    body = client.post("/api/settings/signature", files={"file": ("logo.png", huge, "image/png")})
    assert body.status_code == 413
    assert client.get("/api/settings").json()["signature"] is False


def test_signature_never_lands_in_a_case(client):
    """It is workspace-level, like the API keys — a case folder never sees it."""
    client.post("/api/settings/signature", files={"file": ("logo.png", PNG, "image/png")})
    assert config.signature_path().is_file()
    assert config.signature_path().parent == config.workspace_root()
    case_id = client.post("/api/cases", json={"name": "Signed"}).json()["id"]
    case_dir = config.cases_dir() / case_id
    assert not list(case_dir.rglob("signature.png"))


# ---- scrapers: version reporting and the update button ----------------------


def test_get_scrapers_reports_both_offline(client, monkeypatch):
    """Opening Settings must not reach the network — local-first."""

    def explode(*a, **k):
        raise AssertionError("GET /settings/scrapers phoned home without check=true")

    monkeypatch.setattr(scrapers.httpx, "get", explode)
    body = client.get("/api/settings/scrapers").json()["scrapers"]
    assert {e["dist"] for e in body} == {"yt-dlp", "gallery-dl"}
    assert all(e["source"] == "bundled" and e["version"] for e in body)


def test_get_scrapers_check_reports_what_is_newer(client, monkeypatch):
    monkeypatch.setattr(scrapers, "latest_version", lambda dist: "9999.1.1")
    body = client.get("/api/settings/scrapers", params={"check": True}).json()["scrapers"]
    assert all(e["latest"] == "9999.1.1" and e["outdated"] is True for e in body)


def test_check_reports_up_to_date_when_it_matches(client, monkeypatch):
    current = scrapers.active_version("yt-dlp")[0]
    monkeypatch.setattr(scrapers, "latest_version", lambda dist: current)
    entry = next(
        e
        for e in client.get("/api/settings/scrapers", params={"check": True}).json()["scrapers"]
        if e["dist"] == "yt-dlp"
    )
    assert entry["outdated"] is False


def test_update_unknown_scraper_is_404(client):
    assert client.post("/api/settings/scrapers/pip/update").status_code == 404
    assert client.delete("/api/settings/scrapers/pip").status_code == 404


def test_update_reports_failure_inline_rather_than_500(client, monkeypatch):
    """A download that fails is a message in the tab, not a broken app."""

    def offline(*a, **k):
        raise OSError("no route to host")

    monkeypatch.setattr(scrapers.httpx, "get", offline)
    body = client.post("/api/settings/scrapers/yt-dlp/update").json()
    assert body["ok"] is False
    assert "no route to host" in body["detail"]


def test_update_then_reset_round_trip(client, monkeypatch):
    monkeypatch.setattr(
        scrapers,
        "update",
        lambda dist: {
            "dist": dist,
            "updated": True,
            "version": "3.2.1",
            "previous": "1.0.0",
            "restart_required": True,
            "detail": "updated to 3.2.1 — restart Azimut to use it",
        },
    )
    body = client.post("/api/settings/scrapers/yt-dlp/update").json()
    assert body["ok"] is True and body["restart_required"] is True

    reset = client.delete("/api/settings/scrapers/yt-dlp").json()
    assert reset["ok"] is True and reset["removed"] is False


def test_scrapers_live_in_the_workspace_not_the_install(client):
    """The runtime dir has to be somewhere writable — the binary's own dir isn't."""
    assert config.runtime_dir().parent == config.workspace_root()
