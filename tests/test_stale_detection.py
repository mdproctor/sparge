"""
Stale detection invariant tests.

The STALE flag (md.stale = html.hash != md.html_hash) must correctly reflect
whether the HTML has changed since the MD was last generated.

Design rule: both html.hash and md.html_hash must track the SAME file —
whichever file generate-md actually reads (enriched copy if it exists, else
original). Currently they both use the original, which is inconsistent with
generate-md preferring the enriched copy.

Four invariants:

1. generate-md clears STALE: if a post is stale, running generate-md must
   produce stale=False in the returned state.

2. save-html then scan shows STALE: editing the enriched copy (save-html)
   followed by a scan must produce stale=True — the HTML changed since
   the last generate-md.

3. md.html_hash tracks the enriched copy: after generate-md, the recorded
   md.html_hash must equal the hash of the file generate-md actually read
   (enriched if it exists, else original). Currently mark_md_generated always
   hashes the original — bug.

4. html.hash tracks the enriched copy: after scan, html.hash must equal the
   hash of the enriched copy (if it exists). Currently set_html_issues always
   hashes the original — bug.

Tests 2, 3, 4 will FAIL with current code and drive the fix.

Requires server running on localhost:9000.
"""
import hashlib
import json
import time
from pathlib import Path
import sys

import pytest
import requests

MIGRATOR_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(MIGRATOR_ROOT / 'scripts'))

SERVER  = 'http://localhost:9000'
API     = SERVER + '/api'
SESSION = requests.Session()

TEST_SLUG = '2006-05-31-what-is-a-rule-engine'
STALE_MARKER = '<!-- stale-detection-test -->'


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def _get_paths():
    try:
        import sparge_home as sh
        proj_dir = sh.get_projects_dir() / 'kie-mark-proctor'
    except Exception:
        pytest.skip('Cannot locate project directory')
    cfg = json.loads((proj_dir / 'config.json').read_text())
    serve_root   = Path(cfg['serve_root'])
    original_path = serve_root / cfg['source']['posts_dir'] / (TEST_SLUG + '.html')
    enriched_path = proj_dir / 'enriched' / (TEST_SLUG + '.html')
    if not original_path.exists():
        pytest.skip(f'Original not found: {original_path}')
    return original_path, enriched_path


@pytest.fixture(scope='module')
def server():
    try:
        requests.get(f'{API}/projects', timeout=3).raise_for_status()
    except Exception:
        pytest.skip('Server not running on localhost:9000')


@pytest.fixture(scope='module')
def paths(server):
    return _get_paths()


# ── Helper: force stale state by patching state.json directly ─────────────────

def _force_stale(slug: str, proj_dir: Path):
    """Patch state.json so md.html_hash differs from html.hash → stale=True."""
    state_path = proj_dir / 'state.json'
    state = json.loads(state_path.read_text())
    entry = state.get(slug, {})
    # Give md.html_hash a bogus value that can't match any real hash
    entry.setdefault('md', {})['html_hash'] = 'badhash000000'
    entry.setdefault('md', {})['generated_at'] = '2020-01-01T00:00:00'
    state[slug] = entry
    state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def _get_proj_dir() -> Path:
    try:
        import sparge_home as sh
        return sh.get_projects_dir() / 'kie-mark-proctor'
    except Exception:
        pytest.skip('Cannot locate project directory')


# ── 1. generate-md clears STALE ───────────────────────────────────────────────

class TestGenerateMdClearsStale:
    """Running generate-md on a stale post must produce stale=False.

    This is the user-visible invariant: clicking Generate on a STALE post
    must make the badge disappear.
    """

    def test_generate_md_clears_stale_flag(self, server, paths):
        proj_dir = _get_proj_dir()
        _force_stale(TEST_SLUG, proj_dir)

        # Verify the post is now stale
        post = next(
            (p for p in SESSION.get(f'{API}/posts').json() if p['slug'] == TEST_SLUG),
            None,
        )
        assert post and post.get('md', {}).get('stale'), (
            'Could not force stale state — test setup failed'
        )

        # Run generate-md
        r = SESSION.post(f'{API}/posts/{TEST_SLUG}/generate-md')
        assert r.status_code == 200, f'generate-md failed: {r.status_code}'
        returned = r.json()

        assert not returned.get('md', {}).get('stale'), (
            'generate-md did not clear the stale flag. '
            'After a successful generate-md, md.html_hash must equal html.hash '
            'so _is_stale() returns False. '
            'mark_md_generated() must record the hash of the file generate-md '
            'actually read — not a fixed fallback that may differ.'
        )

    def test_generate_md_stale_cleared_in_post_list(self, server, paths):
        """After generate-md, the post list must also show stale=False."""
        proj_dir = _get_proj_dir()
        _force_stale(TEST_SLUG, proj_dir)

        SESSION.post(f'{API}/posts/{TEST_SLUG}/generate-md')

        post = next(
            (p for p in SESSION.get(f'{API}/posts').json() if p['slug'] == TEST_SLUG),
            None,
        )
        assert post is not None, 'Post not found in list'
        assert not post.get('md', {}).get('stale'), (
            'Post still shows stale=True in /api/posts after generate-md. '
            'The post list must reflect the updated state.'
        )


# ── 2. save-html + scan shows STALE ───────────────────────────────────────────

class TestSaveHtmlThenScanShowsStale:
    """Editing the enriched HTML (save-html) and then scanning must mark
    the post as stale — the source HTML has changed since MD was last generated.

    Bug: set_html_issues() hashes the original file (POSTS_DIR/slug.html),
    not the enriched copy. So editing the enriched copy via save-html has no
    effect on html.hash — the stale flag never fires even though the HTML
    that generate-md will use has changed.

    Fix: set_html_issues() must hash the enriched copy when it exists, so
    that html.hash tracks the file that generate-md actually reads.
    """

    def test_save_html_then_scan_shows_stale(self, server, paths):
        original_path, enriched_path = paths

        # First: generate MD so the post starts as not-stale
        SESSION.post(f'{API}/posts/{TEST_SLUG}/generate-md')
        post = next(
            (p for p in SESSION.get(f'{API}/posts').json() if p['slug'] == TEST_SLUG),
            None,
        )
        assert post and not post.get('md', {}).get('stale'), (
            'Test setup: post should not be stale before the edit'
        )

        # Edit the enriched copy via save-html
        current = SESSION.get(f'{API}/posts/{TEST_SLUG}/html').text
        marked = current + f'\n{STALE_MARKER}'
        r = SESSION.post(
            f'{API}/posts/{TEST_SLUG}/save-html',
            data=marked.encode('utf-8'),
            headers={'Content-Type': 'text/html; charset=utf-8'},
        )
        assert r.status_code == 200

        try:
            # Scan — must detect that the enriched HTML changed
            SESSION.post(f'{API}/posts/{TEST_SLUG}/scan')

            post = next(
                (p for p in SESSION.get(f'{API}/posts').json() if p['slug'] == TEST_SLUG),
                None,
            )
            stale = post.get('md', {}).get('stale') if post else False
        finally:
            # Restore
            SESSION.post(
                f'{API}/posts/{TEST_SLUG}/save-html',
                data=current.encode('utf-8'),
                headers={'Content-Type': 'text/html; charset=utf-8'},
            )
            SESSION.post(f'{API}/posts/{TEST_SLUG}/generate-md')

        assert stale, (
            'After editing enriched HTML (save-html) and scanning, stale must be True. '
            'The enriched copy is what generate-md reads — if it changes, the MD is '
            'out of date. '
            'Bug: set_html_issues() hashes POSTS_DIR/slug.html (original) instead of '
            'the enriched copy, so html.hash does not change when enriched is edited. '
            'Fix: in set_html_issues(), prefer the enriched path when it exists: '
            'html_path = enriched_path if enriched_path.exists() else original_path'
        )


# ── 3. md.html_hash tracks the enriched copy ──────────────────────────────────

class TestMdHtmlHashTracksEnrichedCopy:
    """After generate-md, md.html_hash must equal the hash of the file
    generate-md actually read — the enriched copy (if it exists).

    Bug: mark_md_generated() always hashes POSTS_DIR/slug.html (original).
    If the enriched copy differs from the original (e.g. after a save-html
    edit followed by generate-md), md.html_hash will not match the enriched
    copy's hash. Any subsequent scan that correctly hashes the enriched copy
    will produce html.hash != md.html_hash → spurious STALE.

    Fix: mark_md_generated() must hash the enriched copy when it exists.
    """

    def test_md_html_hash_matches_enriched_after_generate(self, server, paths):
        original_path, enriched_path = paths
        if not enriched_path.exists():
            pytest.skip('No enriched copy — cannot test enriched hash tracking')

        # Edit the enriched copy so it differs from the original
        current = SESSION.get(f'{API}/posts/{TEST_SLUG}/html').text
        marked = current + f'\n{STALE_MARKER}'
        SESSION.post(
            f'{API}/posts/{TEST_SLUG}/save-html',
            data=marked.encode('utf-8'),
            headers={'Content-Type': 'text/html; charset=utf-8'},
        )

        try:
            # Generate MD from the (now-edited) enriched copy
            r = SESSION.post(f'{API}/posts/{TEST_SLUG}/generate-md')
            assert r.status_code == 200
            returned = r.json()
            md_html_hash = returned.get('md', {}).get('html_hash')

            # The enriched copy has been written back by convert_post — re-hash it
            enriched_hash_after = _hash_file(enriched_path)
            original_hash = _hash_file(original_path)
        finally:
            SESSION.post(
                f'{API}/posts/{TEST_SLUG}/save-html',
                data=current.encode('utf-8'),
                headers={'Content-Type': 'text/html; charset=utf-8'},
            )
            SESSION.post(f'{API}/posts/{TEST_SLUG}/generate-md')

        assert md_html_hash == enriched_hash_after, (
            f'md.html_hash ({md_html_hash!r}) does not match the enriched copy '
            f'hash ({enriched_hash_after!r}) after generate-md. '
            f'Original hash: {original_hash!r}. '
            f'generate-md reads from the enriched copy but mark_md_generated() '
            f'always hashes the original — if they differ, the recorded hash is wrong. '
            f'Fix: in mark_md_generated(), use the enriched path when it exists: '
            f'html_path = enriched_path if enriched_path.exists() else original_path'
        )


# ── 4. html.hash tracks the enriched copy ─────────────────────────────────────

class TestHtmlHashTracksEnrichedCopy:
    """After scan, html.hash must equal the hash of the enriched copy
    (when it exists), since that is the file generate-md reads.

    Bug: set_html_issues() always hashes POSTS_DIR/slug.html (original).
    If the enriched copy differs (user edited it), html.hash reflects the
    original — stale detection is blind to enriched-copy changes.

    Fix: set_html_issues() must hash the enriched copy when it exists.
    """

    def test_scan_html_hash_matches_enriched_copy(self, server, paths):
        original_path, enriched_path = paths
        if not enriched_path.exists():
            pytest.skip('No enriched copy — cannot test enriched hash tracking')

        # Edit the enriched copy so it has a different hash from the original
        current = SESSION.get(f'{API}/posts/{TEST_SLUG}/html').text
        marked = current + f'\n{STALE_MARKER}'
        SESSION.post(
            f'{API}/posts/{TEST_SLUG}/save-html',
            data=marked.encode('utf-8'),
            headers={'Content-Type': 'text/html; charset=utf-8'},
        )

        try:
            # Scan
            SESSION.post(f'{API}/posts/{TEST_SLUG}/scan')

            post = next(
                (p for p in SESSION.get(f'{API}/posts').json() if p['slug'] == TEST_SLUG),
                None,
            )
            html_hash_in_state = post.get('html', {}).get('hash') if post else None
            enriched_hash = _hash_file(enriched_path)
            original_hash = _hash_file(original_path)
        finally:
            SESSION.post(
                f'{API}/posts/{TEST_SLUG}/save-html',
                data=current.encode('utf-8'),
                headers={'Content-Type': 'text/html; charset=utf-8'},
            )
            SESSION.post(f'{API}/posts/{TEST_SLUG}/generate-md')

        assert html_hash_in_state == enriched_hash, (
            f'After scan, html.hash ({html_hash_in_state!r}) does not match '
            f'the enriched copy hash ({enriched_hash!r}). '
            f'Original hash: {original_hash!r}. '
            f'set_html_issues() hashes the original file, making html.hash blind '
            f'to changes in the enriched copy. '
            f'Fix: in set_html_issues(), prefer the enriched path when it exists.'
        )
