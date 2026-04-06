"""
Sparge home directory management.

Reads ~/.sparge/config.json to find where project data lives.
Creates the config with defaults on first use.

Public API
----------
get_projects_dir() -> Path   resolved path to the projects directory
"""
from __future__ import annotations

import json
import os
from pathlib import Path


_SPARGE_HOME = Path.home() / '.sparge'
_SPARGE_CFG  = _SPARGE_HOME / 'config.json'
_DEFAULT_PROJECTS_DIR = Path.home() / 'sparge-projects'


def get_projects_dir() -> Path:
    """
    Return the resolved projects directory path.
    Creates ~/.sparge/config.json with defaults if absent.
    """
    _SPARGE_HOME.mkdir(exist_ok=True)
    if not _SPARGE_CFG.exists():
        _SPARGE_CFG.write_text(json.dumps(
            {'projects_dir': str(_DEFAULT_PROJECTS_DIR)},
            indent=2,
        ))
    try:
        data = json.loads(_SPARGE_CFG.read_text())
        raw = data.get('projects_dir', str(_DEFAULT_PROJECTS_DIR))
    except Exception:
        raw = str(_DEFAULT_PROJECTS_DIR)
    return Path(os.path.expanduser(raw))
