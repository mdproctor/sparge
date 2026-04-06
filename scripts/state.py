"""
Per-post state manager.

State lives in blog-migrator/state.json — one entry per post slug.
Each entry tracks:
  - ingested_at   : when the HTML was first seen
  - html.hash     : sha256[:12] of source HTML — changes trigger MD stale flag
  - html.issues   : list of detected problems with CSS selectors for highlighting
  - assets.total/localised/broken : image localisation counts
  - md.generated_at / md.html_hash : when MD was generated and from which HTML version
  - md.stale      : computed — True when html.hash != md.html_hash
  - md.staged     : True when a SLUG.md.staged file exists pending review
  - md.staged_at  : when the staged version was created
  - md.issues     : validation problems with CSS selectors
  - flagged / user_note / reviewed : manual review state

Staged workflow
---------------
When Generate MD produces a diff against the existing MD, the user can choose
"Stage for review" instead of accepting or rejecting immediately. This writes
the new version to SLUG.md.staged and sets md.staged = True. The current
SLUG.md is untouched. Later the user can Accept (promotes staged → md) or
Reject (deletes staged file) via the diff viewer.
"""
import hashlib
import json
from datetime import datetime
from pathlib import Path

from .config import cfg

# Default path — updated by set_state_file() when a project is activated
_STATE_FILE: Path = (
    Path(__file__).parent.parent / 'projects' / 'kie-mark-proctor' / 'state.json'
)


def set_state_file(path: Path):
    """Switch to a different project's state file."""
    global _STATE_FILE
    _STATE_FILE = path


# ── Internal helpers ───────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now().isoformat(timespec='seconds')


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def _load() -> dict:
    if _STATE_FILE.exists():
        return json.loads(_STATE_FILE.read_text())
    return {}


def _save(state: dict):
    _STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def _is_stale(entry: dict) -> bool:
    """MD is stale if the HTML has changed since MD was generated."""
    html_hash = entry.get('html', {}).get('hash')
    md_hash   = entry.get('md',   {}).get('html_hash')
    generated = entry.get('md',   {}).get('generated_at')
    return bool(generated and html_hash and md_hash and html_hash != md_hash)


def _computed(entry: dict) -> dict:
    """Add computed fields before returning to callers."""
    entry = dict(entry)
    entry['md'] = dict(entry.get('md', {}))
    entry['md']['stale'] = _is_stale(entry)
    return entry


# ── Public API ─────────────────────────────────────────────────────────────────

def get_all() -> list[dict]:
    return [_computed(e) for e in _load().values()]


def get(slug: str) -> dict | None:
    entry = _load().get(slug)
    return _computed(entry) if entry else None


def update(slug: str, patch: dict):
    """Shallow-merge patch into the top-level entry, deep-merge 'html'/'md'/'assets'."""
    state = _load()
    entry = state.setdefault(slug, {'slug': slug})
    for key, val in patch.items():
        if key in ('html', 'md', 'assets') and isinstance(val, dict):
            entry.setdefault(key, {}).update(val)
        else:
            entry[key] = val
    _save(state)


def set_html_issues(slug: str, issues: list[dict]):
    """Replace HTML issue list and refresh hash."""
    posts_dir = cfg['_posts_dir']
    html_path = posts_dir / (slug + '.html')
    h = _hash(html_path) if html_path.exists() else None
    update(slug, {'html': {'issues': issues, 'checked_at': _now(), 'hash': h}})
    # Cascade: if MD exists and was generated from a different hash, mark note
    # (stale is computed dynamically; no extra write needed)


def set_md_issues(slug: str, issues: list[dict]):
    """Replace MD issue list."""
    update(slug, {'md': {'issues': issues, 'validated_at': _now()}})


def mark_md_generated(slug: str):
    """Record that MD was just generated from the current HTML hash."""
    posts_dir = cfg['_posts_dir']
    html_path = posts_dir / (slug + '.html')
    h = _hash(html_path) if html_path.exists() else None
    update(slug, {'md': {
        'generated_at': _now(),
        'html_hash': h,
        'staged': False,
        'staged_at': None,
        'issues': [],
        'validated_at': None,
    }})


def mark_enriched(slug: str, stats: dict):
    """Record enrichment stats for a post."""
    update(slug, {'enriched': {
        'generated_at': _now(),
        'youtube_replaced':   stats.get('youtube_replaced', 0),
        'gists_replaced':     stats.get('gists_replaced', 0),
        'gists_failed':       stats.get('gists_failed', 0),
        'classes_normalised': stats.get('classes_normalised', 0),
        'languages_detected': stats.get('languages_detected', 0),
        'embeds_wrapped':     stats.get('embeds_wrapped', 0),
    }})


# ── Staged workflow ────────────────────────────────────────────────────────────

def stage(slug: str):
    """Mark that a staged version (SLUG.md.staged) now exists for this post."""
    update(slug, {'md': {'staged': True, 'staged_at': _now()}})


def accept_staged(slug: str) -> bool:
    """
    Promote SLUG.md.staged → SLUG.md.
    Clears staged flag, updates generated_at and html_hash to current values.
    Returns False if no staged file exists.
    """
    md_dir     = cfg['_md_dir']
    md_path    = md_dir / (slug + '.md')
    staged_path = md_dir / (slug + '.md.staged')
    if not staged_path.exists():
        return False
    content = staged_path.read_text(encoding='utf-8')
    md_path.write_text(content, encoding='utf-8')
    staged_path.unlink()
    posts_dir = cfg['_posts_dir']
    html_path = posts_dir / (slug + '.html')
    h = _hash(html_path) if html_path.exists() else None
    update(slug, {'md': {
        'staged': False,
        'staged_at': None,
        'generated_at': _now(),
        'html_hash': h,
        'issues': [],
        'validated_at': None,
    }})
    return True


def reject_staged(slug: str) -> bool:
    """
    Delete SLUG.md.staged without touching SLUG.md.
    Clears staged flag. Returns False if no staged file existed.
    """
    md_dir      = cfg['_md_dir']
    staged_path = md_dir / (slug + '.md.staged')
    existed = staged_path.exists()
    if existed:
        staged_path.unlink()
    update(slug, {'md': {'staged': False, 'staged_at': None}})
    return existed


# ── Initialisation ─────────────────────────────────────────────────────────────

def init_from_source() -> int:
    """
    Scan source posts_dir for HTML files not yet in state.json.
    Bootstraps entries for existing content (including already-generated MD).
    Returns number of new entries added.
    """
    posts_dir = cfg['_posts_dir']
    md_dir    = cfg['_md_dir']
    state     = _load()
    added     = 0

    for html_path in sorted(posts_dir.glob('*.html')):
        slug = html_path.stem
        if slug in state:
            # Recompute hash in case the file changed outside the tool
            current_hash = _hash(html_path)
            if state[slug].get('html', {}).get('hash') != current_hash:
                state[slug].setdefault('html', {})['hash'] = current_hash
                # Don't write yet — batch below
            continue

        # Load metadata sidecar
        sidecar = html_path.with_suffix('.json')
        meta    = json.loads(sidecar.read_text()) if sidecar.exists() else {}

        html_hash = _hash(html_path)

        # Check for existing MD output
        md_path    = md_dir / (slug + '.md')
        staged_path = md_dir / (slug + '.md.staged')
        md_info: dict = {
            'generated_at': None, 'html_hash': None, 'issues': [],
            'staged': staged_path.exists(),
            'staged_at': (datetime.fromtimestamp(staged_path.stat().st_mtime)
                         .isoformat(timespec='seconds') if staged_path.exists() else None),
        }
        if md_path.exists():
            # Assume generated from current HTML (best guess for pre-existing files)
            md_info['generated_at'] = datetime.fromtimestamp(
                md_path.stat().st_mtime).isoformat(timespec='seconds')
            md_info['html_hash'] = html_hash

        # Check existing issues sidecar (from old issues_list.py)
        md_issues: list = []
        old_issues_file = md_dir / '.issues.json'
        if old_issues_file.exists():
            try:
                old = json.loads(old_issues_file.read_text())
                match = next((p for p in old if p.get('slug') == slug), None)
                if match:
                    md_issues = [
                        {'check': i.get('check', ''), 'level': i.get('level', 'WARN'),
                         'detail': i.get('detail', ''), 'selector': None}
                        for i in match.get('issues', [])
                    ]
            except Exception:
                pass

        if md_issues:
            md_info['issues'] = md_issues

        state[slug] = {
            'slug':         slug,
            'title':        meta.get('title', slug),
            'date':         (meta.get('date', '') or '')[:10],
            'author':       meta.get('author', cfg.get('filter', {}).get('author', '')),
            'original_url': meta.get('original_url', ''),
            'ingested_at':  _now(),
            'html': {
                'hash':       html_hash,
                'issues':     [],
                'checked_at': None,
            },
            'assets': {
                'total':      0,
                'localised':  0,
                'broken':     0,
                'checked_at': None,
            },
            'md':       md_info,
            'flagged':  False,
            'user_note': '',
            'reviewed': False,
        }
        added += 1

    _save(state)
    return added
