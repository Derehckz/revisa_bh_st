# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

import utils


def test_backup_file_writes_under_dot_backups(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    backup_dir = repo / ".backups" / "files"
    backup_dir.mkdir(parents=True)
    target = repo / "BD-DOCENTES.xlsx"
    target.write_bytes(b"PK\x03\x04fake")

    monkeypatch.setattr(utils, "_file_backup_dir", lambda: str(backup_dir))

    dest = utils.backup_file(str(target), keep=5)
    assert dest is not None
    dest_path = Path(dest)
    assert dest_path.parent == backup_dir
    assert dest_path.name.startswith("BD-DOCENTES_backup_")
    assert dest_path.is_file()
    # No debe dejar ZIP al lado del Excel
    assert not list(repo.glob("BD-DOCENTES_backup_*.zip"))


def test_backup_file_prunes_old(tmp_path, monkeypatch):
    backup_dir = tmp_path / ".backups" / "files"
    backup_dir.mkdir(parents=True)
    monkeypatch.setattr(utils, "_file_backup_dir", lambda: str(backup_dir))

    src = tmp_path / "Solicitud.xlsx"
    src.write_bytes(b"xlsx")

    for _ in range(4):
        p = utils.backup_file(str(src), keep=2)
        assert p is not None

    kept = list(backup_dir.glob("Solicitud_backup_*.zip"))
    assert len(kept) == 2
