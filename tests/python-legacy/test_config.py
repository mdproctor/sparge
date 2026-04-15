"""Tests for config.py additions."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from config import _resolve


def _make_cfg(extra=None):
    tmp = tempfile.mkdtemp()
    d = {
        'project_name': 'Test',
        'serve_root': tmp,
        'source': {'posts_dir': 'posts', 'assets_dir': 'assets'},
        'output': {'md_dir': 'md'},
        'server': {'port': 9000},
    }
    if extra:
        d.update(extra)
    return d


def test_github_token_defaults_to_empty():
    cfg = _resolve(_make_cfg())
    assert cfg.get('github_token', '') == ''


def test_github_token_preserved():
    cfg = _resolve(_make_cfg({'github_token': 'ghp_abc123'}))
    assert cfg['github_token'] == 'ghp_abc123'
