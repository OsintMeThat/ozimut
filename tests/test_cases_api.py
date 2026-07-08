"""Case lifecycle, notes, entities and links through the REST API."""


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_case_lifecycle(client):
    created = client.post("/api/cases", json={"name": "Kharkiv Strike"}).json()
    assert created["id"] == "kharkiv-strike"
    assert created["entities"] == []

    # duplicate name → 409
    assert client.post("/api/cases", json={"name": "Kharkiv Strike"}).status_code == 409

    listed = client.get("/api/cases").json()
    assert [c["id"] for c in listed] == ["kharkiv-strike"]

    client.patch("/api/cases/kharkiv-strike", json={"name": "Kharkiv Strike v2"})
    assert client.get("/api/cases/kharkiv-strike").json()["name"] == "Kharkiv Strike v2"

    assert client.delete("/api/cases/kharkiv-strike").json()["status"] == "deleted"
    assert client.get("/api/cases/kharkiv-strike").status_code == 404


def test_scratch_promote(client):
    scratch = client.post("/api/cases/scratch").json()
    assert scratch["id"].startswith("scratch_")
    assert client.get(f"/api/cases/{scratch['id']}").json()["scratch"] is True

    promoted = client.post(
        f"/api/cases/{scratch['id']}/promote", json={"name": "Real Case"}
    ).json()
    assert promoted["id"] == "real-case"
    assert client.get("/api/cases/real-case").json()["scratch"] is False
    # old scratch id is gone
    assert client.get(f"/api/cases/{scratch['id']}").status_code == 404


def test_notes_roundtrip(client):
    case = client.post("/api/cases", json={"name": "Notes"}).json()
    client.put(f"/api/cases/{case['id']}/notes", json={"text": "# hello\n\nworld"})
    assert client.get(f"/api/cases/{case['id']}/notes").json()["text"] == "# hello\n\nworld"


def test_entities_and_links(client):
    cid = client.post("/api/cases", json={"name": "Graph"}).json()["id"]

    person = client.post(
        f"/api/cases/{cid}/entities", json={"type": "person", "label": "John Doe"}
    ).json()
    account = client.post(
        f"/api/cases/{cid}/entities",
        json={"type": "account", "label": "@johnd", "status": "suggested"},
    ).json()
    assert person["provenance"]["status"] == "confirmed"
    assert account["provenance"]["status"] == "suggested"

    # confirm the suggestion (spec §3.5: analyst decides)
    patched = client.patch(
        f"/api/cases/{cid}/entities/{account['id']}", json={"status": "confirmed"}
    ).json()
    assert patched["provenance"]["status"] == "confirmed"

    link = client.post(
        f"/api/cases/{cid}/links",
        json={"from_id": person["id"], "to_id": account["id"], "type": "owns"},
    ).json()
    assert link["type"] == "owns"

    # unknown entity in a link → 404
    assert (
        client.post(
            f"/api/cases/{cid}/links",
            json={"from_id": person["id"], "to_id": "e_nope", "type": "owns"},
        ).status_code
        == 404
    )

    # deleting an entity cascades to its links
    client.delete(f"/api/cases/{cid}/entities/{account['id']}")
    data = client.get(f"/api/cases/{cid}").json()
    assert len(data["entities"]) == 1
    assert data["links"] == []
