"""Unit tests for sparge_home.py — ~/.sparge config reading."""
import json
import sys
from pathlib import Path

import pytest

MIGRATOR = Path(__file__).parent.parent
sys.path.insert(0, str(MIGRATOR / 'scripts'))


def test_default_projects_dir_when_no_config(tmp_path, monkeypatch):
    """When ~/.sparge/config.json absent, defaults to ~/sparge-projects."""
    monkeypatch.setenv('HOME', str(tmp_path))
    import importlib, sparge_home
    importlib.reload(sparge_home)
    result = sparge_home.get_projects_dir()
    assert result == tmp_path / 'sparge-projects'


def test_reads_projects_dir_from_config(tmp_path, monkeypatch):
    """When config exists, returns configured path."""
    monkeypatch.setenv('HOME', str(tmp_path))
    custom = tmp_path / 'my-projects'
    sparge_cfg = tmp_path / '.sparge'
    sparge_cfg.mkdir()
    (sparge_cfg / 'config.json').write_text(
        json.dumps({'projects_dir': str(custom)})
    )
    import importlib, sparge_home
    importlib.reload(sparge_home)
    result = sparge_home.get_projects_dir()
    assert result == custom


def test_tilde_expansion_in_projects_dir(tmp_path, monkeypatch):
    """~/path in config.json is expanded relative to HOME."""
    monkeypatch.setenv('HOME', str(tmp_path))
    sparge_cfg = tmp_path / '.sparge'
    sparge_cfg.mkdir()
    (sparge_cfg / 'config.json').write_text(
        json.dumps({'projects_dir': '~/custom-projects'})
    )
    import importlib, sparge_home
    importlib.reload(sparge_home)
    result = sparge_home.get_projects_dir()
    assert result == tmp_path / 'custom-projects'


def test_creates_sparge_dir_and_default_config(tmp_path, monkeypatch):
    """First call creates ~/.sparge/config.json with defaults."""
    monkeypatch.setenv('HOME', str(tmp_path))
    import importlib, sparge_home
    importlib.reload(sparge_home)
    sparge_home.get_projects_dir()
    cfg_path = tmp_path / '.sparge' / 'config.json'
    assert cfg_path.exists()
    data = json.loads(cfg_path.read_text())
    assert 'projects_dir' in data
