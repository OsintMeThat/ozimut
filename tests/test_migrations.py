"""Forward compatibility (spec §7): an older case.json / settings.json is
migrated up to the running schema on open, a newer one is refused rather than
mangled. The chains are empty today, so these tests register throwaway
migrations to prove the runners, and pin the "same schema doesn't rewrite" and
"newer is refused" invariants that hold with zero migrations."""

import json

import pytest

from azimut import config, workspace
from azimut.workspace import Case, CaseError


# -- case.json ------------------------------------------------------------


def test_open_current_schema_does_not_rewrite(tmp_workspace):
    """The common path: a case at the running schema is returned untouched, no
    backup file appears, updated_at is left alone."""
    case = Case.create("Investigation")
    before = case.read()["updated_at"]

    reopened = Case.open(case.id)

    assert reopened.read()["updated_at"] == before
    backups = list(case.path.glob("case.pre-migrate*.json"))
    assert backups == []


def test_open_newer_schema_is_refused(tmp_workspace):
    case = Case.create("From the future")
    data = case.read()
    data["azimut"]["schema"] = workspace.CASE_SCHEMA + 5
    case._write_json(data)

    with pytest.raises(CaseError, match="newer Azimut"):
        Case.open(case.id)


def test_open_older_schema_migrates_and_backs_up(tmp_workspace, monkeypatch):
    case = Case.create("Legacy")  # written at schema 1

    def to_v2(data):
        data.setdefault("attrs", {})["migrated"] = True
        return data

    monkeypatch.setattr(workspace, "CASE_SCHEMA", 2)
    monkeypatch.setattr(workspace, "CASE_MIGRATIONS", {1: to_v2})

    migrated = Case.open(case.id).read()

    assert migrated["azimut"]["schema"] == 2
    assert migrated["attrs"]["migrated"] is True
    backup = case.path / "case.pre-migrate-v1.json"
    assert backup.exists()
    assert json.loads(backup.read_text())["azimut"]["schema"] == 1


def test_migration_backup_is_not_overwritten(tmp_workspace, monkeypatch):
    """A second migration run keeps the first pre-migration copy."""
    case = Case.create("Legacy")
    monkeypatch.setattr(workspace, "CASE_SCHEMA", 2)
    monkeypatch.setattr(workspace, "CASE_MIGRATIONS", {1: lambda d: d})

    Case.open(case.id)
    backup = case.path / "case.pre-migrate-v1.json"
    first = backup.read_text()

    # Force another migration pass from the same starting schema.
    data = case.read()
    data["azimut"]["schema"] = 1
    case._write_json(data)
    Case.open(case.id)

    assert backup.read_text() == first


# -- settings.json --------------------------------------------------------


def test_migrate_settings_newer_is_left_alone():
    data = {"schema": config.SETTINGS_SCHEMA + 3, "unknown_future_key": 1}
    assert config.migrate_settings(dict(data)) == data


def test_load_settings_untagged_file_is_first_schema(monkeypatch, tmp_path):
    monkeypatch.setenv("AZIMUT_HOME", str(tmp_path))
    config.settings_path().parent.mkdir(parents=True, exist_ok=True)
    config.settings_path().write_text(json.dumps({"api_keys": {}}), encoding="utf-8")

    assert config.load_settings()["schema"] == 1


def test_ensure_workspace_upgrades_settings_in_place(monkeypatch, tmp_path):
    monkeypatch.setenv("AZIMUT_HOME", str(tmp_path))
    config.settings_path().parent.mkdir(parents=True, exist_ok=True)
    config.settings_path().write_text(
        json.dumps({"schema": 1, "post_mention": "@old"}), encoding="utf-8"
    )

    def to_v2(data):
        data["post_mention"] = "@new"
        return data

    monkeypatch.setattr(config, "SETTINGS_SCHEMA", 2)
    monkeypatch.setattr(config, "SETTINGS_MIGRATIONS", {1: to_v2})

    config.ensure_workspace()

    saved = json.loads(config.settings_path().read_text(encoding="utf-8"))
    assert saved["schema"] == 2
    assert saved["post_mention"] == "@new"
