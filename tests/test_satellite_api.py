"""Satellite capture API: bearing is honored and persisted with provenance."""

from PIL import Image

from ozimut.engine import tiles


def _fake_tile(client, url):  # offline: every tile is a solid green square
    return Image.new("RGB", (256, 256), (10, 120, 10))


def test_capture_persists_bearing(client, monkeypatch):
    monkeypatch.setattr(tiles, "_default_fetch", _fake_tile)
    cid = client.post("/api/cases", json={"name": "Sat"}).json()["id"]

    result = client.post(
        f"/api/cases/{cid}/satellite/capture",
        json={"lat": 48.8584, "lon": 2.2945, "zoom": 16,
              "width": 640, "height": 480, "bearing": 90},
    ).json()
    assert result["bearing"] == 90.0

    listed = client.get(f"/api/cases/{cid}/satellite").json()
    assert len(listed) == 1
    assert listed[0]["bearing"] == 90.0


def test_capture_defaults_to_north(client, monkeypatch):
    monkeypatch.setattr(tiles, "_default_fetch", _fake_tile)
    cid = client.post("/api/cases", json={"name": "Sat"}).json()["id"]

    result = client.post(
        f"/api/cases/{cid}/satellite/capture",
        json={"lat": 48.8584, "lon": 2.2945, "zoom": 16, "width": 512, "height": 512},
    ).json()
    assert result["bearing"] == 0.0


def _capture(client, cid, lat, lon, zoom=16):
    return client.post(
        f"/api/cases/{cid}/satellite/capture",
        json={"lat": lat, "lon": lon, "zoom": zoom, "width": 512, "height": 512},
    ).json()


def _places(client, cid):
    return [e for e in client.get(f"/api/cases/{cid}").json()["entities"]
            if e["type"] == "place"]


def test_capture_creates_place_entity(client, monkeypatch):
    monkeypatch.setattr(tiles, "_default_fetch", _fake_tile)
    cid = client.post("/api/cases", json={"name": "Sat"}).json()["id"]
    cap = _capture(client, cid, 48.8584, 2.2945)
    places = _places(client, cid)
    assert len(places) == 1
    # the entity is tied to this exact capture by path, titled with its coords
    assert places[0]["attrs"]["coords"] == "48.858400, 2.294500"
    assert places[0]["attrs"]["path"] == cap["path"]
    assert places[0]["label"] == "48.858400, 2.294500"
    # zoom/bearing travel with the place so the sidebar can restore the view
    assert places[0]["attrs"]["zoom"] == 16
    assert places[0]["attrs"]["bearing"] == 0.0
    # capturing files the place straight away — no confirm step
    assert places[0]["provenance"]["status"] == "confirmed"


def test_each_capture_is_its_own_entity(client, monkeypatch):
    monkeypatch.setattr(tiles, "_default_fetch", _fake_tile)
    cid = client.post("/api/cases", json={"name": "Sat"}).json()["id"]
    # two captures at the same coordinates are two independent entities (1:1)
    _capture(client, cid, 48.8584, 2.2945, zoom=16)
    _capture(client, cid, 48.8584, 2.2945, zoom=17)
    assert len(_places(client, cid)) == 2


def test_delete_capture_removes_only_its_place(client, monkeypatch):
    monkeypatch.setattr(tiles, "_default_fetch", _fake_tile)
    cid = client.post("/api/cases", json={"name": "Sat"}).json()["id"]
    first = _capture(client, cid, 48.8584, 2.2945, zoom=16)
    second = _capture(client, cid, 48.8584, 2.2945, zoom=17)

    client.delete(f"/api/cases/{cid}/satellite", params={"path": first["path"]})
    # only the deleted capture's place is gone; the sibling stays intact
    places = _places(client, cid)
    assert len(places) == 1
    assert places[0]["attrs"]["path"] == second["path"]
    remaining = client.get(f"/api/cases/{cid}/satellite").json()
    assert [c["path"] for c in remaining] == [second["path"]]


def test_delete_place_entity_removes_only_its_capture(client, monkeypatch):
    monkeypatch.setattr(tiles, "_default_fetch", _fake_tile)
    cid = client.post("/api/cases", json={"name": "Sat"}).json()["id"]
    first = _capture(client, cid, 48.8584, 2.2945, zoom=16)
    second = _capture(client, cid, 48.8584, 2.2945, zoom=17)
    place = next(p for p in _places(client, cid) if p["attrs"]["path"] == first["path"])

    # deleting the place from the sidebar wipes just its one capture
    client.delete(f"/api/cases/{cid}/entities/{place['id']}")
    assert len(_places(client, cid)) == 1
    remaining = client.get(f"/api/cases/{cid}/satellite").json()
    assert [c["path"] for c in remaining] == [second["path"]]


def test_edit_title_renames_place_entity(client, monkeypatch):
    monkeypatch.setattr(tiles, "_default_fetch", _fake_tile)
    cid = client.post("/api/cases", json={"name": "Sat"}).json()["id"]
    cap = _capture(client, cid, 48.8584, 2.2945)

    updated = client.patch(
        f"/api/cases/{cid}/satellite",
        json={"path": cap["path"], "title": "Eiffel Tower"},
    ).json()
    assert updated["title"] == "Eiffel Tower"
    assert _places(client, cid)[0]["label"] == "Eiffel Tower"

    # listing reflects the stored title
    listed = client.get(f"/api/cases/{cid}/satellite").json()
    assert listed[0]["title"] == "Eiffel Tower"

    # clearing the title falls back to the coordinates on both sides
    client.patch(f"/api/cases/{cid}/satellite", json={"path": cap["path"], "title": "  "})
    assert _places(client, cid)[0]["label"] == "48.858400, 2.294500"
