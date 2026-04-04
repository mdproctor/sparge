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
    """
    Resolve all relative paths against serve_root.

    Supports two config schemas:

    Legacy schema (existing projects pre-source/cleaned split):
        source.posts_dir, source.assets_dir, output.md_dir
        → _posts_dir, _assets_dir, _md_dir

    New schema (projects ingested via Sparge with 3-stage pipeline):
        data.source_dir, data.cleaned_dir, data.assets_dir, data.md_dir
        → _source_dir, _cleaned_dir, _assets_dir, _md_dir
        (also populates _posts_dir alias = _cleaned_dir for compatibility)
    """
    root = Path(raw['serve_root'])
    raw['_root'] = root

    if 'data' in raw:
        # New 3-stage schema
        d = raw['data']
        raw['_source_dir']  = root / d['source_dir']
        raw['_cleaned_dir'] = root / d['cleaned_dir']
        raw['_assets_dir']  = root / d['assets_dir']
        raw['_md_dir']      = root / d['md_dir']
        # Compatibility alias — server code that reads _posts_dir gets cleaned/
        raw['_posts_dir']   = raw['_cleaned_dir']
    else:
        # Legacy schema — no source/cleaned split
        raw['_posts_dir']   = root / raw['source']['posts_dir']
        raw['_assets_dir']  = root / raw['source']['assets_dir']
        raw['_md_dir']      = root / raw['output']['md_dir']
        # New-schema aliases not available in legacy mode
        raw['_source_dir']  = raw['_posts_dir']   # same dir — no separation
        raw['_cleaned_dir'] = raw['_posts_dir']

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
