"""
Load and expose the active project's config.json.

cfg is a mutable dict — updated in-place when projects switch so that
existing `from scripts.config import cfg` bindings stay valid.
All paths resolved to absolute under _root (serve_root).
"""
import json
from pathlib import Path

# Default path — overridden by set_config_path() when a project is activated
_cfg_path: Path = Path(__file__).parent.parent / 'projects' / 'kie-mark-proctor' / 'config.json'


def _resolve(raw: dict) -> dict:
    """Resolve relative source/output paths against serve_root."""
    root = Path(raw['serve_root'])
    raw['_root']       = root
    raw['_posts_dir']  = root / raw['source']['posts_dir']
    raw['_assets_dir'] = root / raw['source']['assets_dir']
    raw['_md_dir']     = root / raw['output']['md_dir']
    return raw


def load() -> dict:
    return _resolve(json.loads(_cfg_path.read_text()))


def save(c: dict):
    clean = {k: v for k, v in c.items() if not k.startswith('_')}
    _cfg_path.write_text(json.dumps(clean, indent=2))


def set_config_path(path: Path):
    """Switch to a different project config. Updates cfg in-place."""
    global _cfg_path
    _cfg_path = path
    new = load()
    cfg.clear()
    cfg.update(new)


# Module-level singleton — mutated in-place on project switch
cfg: dict = load()
