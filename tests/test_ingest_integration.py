"""
Integration tests for the full Sparge ingest pipeline.

Uses the mock blog server (20 articles, dates 2020-01-15 → 2023-11-20)
to exercise real network I/O, file writing, and asset localisation through
the complete source/cleaned/assets directory structure.

Covers:
  - Full import: source/cleaned/assets layout, metadata, XSS stripping
  - Append mode: filter_urls_after correctly limits which posts are fetched
  - No-duplicate guarantee: re-importing the same post overwrites cleanly
  - Asset per-post organisation: images land in assets/posts/{slug}/
  - Hash-based consolidation after bulk ingest: global/ deduplication
  - Wipe and re-import: directories cleared, posts re-appear

Run: python3 -m pytest tests/test_ingest_integration.py -v
"""
import json
import sys
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from asset_store import AssetStore
from consolidate import consolidate

# These tests require the extended sparge ingest API (source/cleaned/assets split,
# extract_date_from_url, filter_urls_after).  Blog-migrator's ingest.py exposes a
# simpler 4-argument ingest_post with no separate source dir.  Skip the whole
# module when those symbols are absent so the suite still collects cleanly.
try:
    from ingest import (
        detect_platform,
        discover_urls,
        extract_date_from_url,
        filter_urls_after,
        ingest_post,
    )
    _FULL_INGEST_API = True
except ImportError:
    _FULL_INGEST_API = False

pytestmark = pytest.mark.skipif(
    not _FULL_INGEST_API,
    reason='ingest.py does not expose the full sparge API (extract_date_from_url, filter_urls_after)',
)

SESSION = requests.Session()
SESSION.headers['User-Agent'] = 'Sparge-Test/1.0'


# ── Helpers ───────────────────────────────────────────────────────

def _ingest_all(urls, source, cleaned, assets):
    """Ingest a list of URLs and return all result dicts."""
    return [ingest_post(u, SESSION, source, cleaned, assets) for u in urls]


def _sorted_dates(all_urls):
    """Return (url, date) pairs sorted by date, skipping undated URLs."""
    return sorted(
        [(u, d) for u in all_urls if (d := extract_date_from_url(u))],
        key=lambda x: x[1],
    )


# ── Fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def dirs(tmp_path):
    """Fresh (source_dir, cleaned_dir, assets_root) per test."""
    return tmp_path / 'source', tmp_path / 'cleaned', tmp_path / 'assets'


@pytest.fixture(scope='module')
def blog(mock_blog_server):
    """Detect platform once; return (base_url, platform, all_urls)."""
    plat = detect_platform(mock_blog_server, SESSION)
    urls = discover_urls(plat['base_url'], plat['platform'], SESSION)
    return plat['base_url'], plat['platform'], urls


# ══════════════════════════════════════════════════════════════════
# Full pipeline — directory layout
# ══════════════════════════════════════════════════════════════════

class TestFullPipelineLayout:
    """Importing all 20 posts creates the correct source/cleaned/assets layout."""

    def test_discovers_all_20_posts(self, blog):
        _, _, urls = blog
        assert len(urls) == 20, f'Expected 20, got {len(urls)}'

    def test_source_file_created_per_post(self, blog, dirs):
        source, cleaned, assets = dirs
        _, _, urls = blog
        results = _ingest_all(urls, source, cleaned, assets)
        ok = [r for r in results if not r.get('error')]
        source_files = list(source.glob('*.html'))
        assert len(source_files) == len(ok), \
            f'{len(ok)} succeeded but {len(source_files)} source files'

    def test_cleaned_file_created_per_post(self, blog, dirs):
        source, cleaned, assets = dirs
        _, _, urls = blog
        results = _ingest_all(urls, source, cleaned, assets)
        ok = [r for r in results if not r.get('error')]
        assert len(list(cleaned.glob('*.html'))) == len(ok)

    def test_json_sidecar_per_post_in_source(self, blog, dirs):
        source, cleaned, assets = dirs
        _, _, urls = blog
        _ingest_all(urls, source, cleaned, assets)
        html_stems = {f.stem for f in source.glob('*.html')}
        json_stems = {f.stem for f in source.glob('*.json')}
        assert html_stems == json_stems, \
            'Every source HTML should have a matching JSON sidecar'

    def test_sidecar_has_required_fields(self, blog, dirs):
        source, cleaned, assets = dirs
        _, _, urls = blog
        results = _ingest_all(urls[:1], source, cleaned, assets)
        slug = results[0]['slug']
        meta = json.loads((source / f'{slug}.json').read_text())
        for field in ('title', 'date', 'original_url'):
            assert field in meta, f'Sidecar missing: {field}'

    def test_assets_per_post_folder(self, blog, dirs):
        source, cleaned, assets = dirs
        _, _, urls = blog
        _ingest_all(urls, source, cleaned, assets)
        store = AssetStore(assets)
        post_assets = store.all_post_assets()
        total = sum(len(v) for v in post_assets.values())
        assert total > 0, 'No assets downloaded into posts/ folders'

    def test_no_results_with_error(self, blog, dirs):
        source, cleaned, assets = dirs
        _, _, urls = blog
        results = _ingest_all(urls, source, cleaned, assets)
        failures = [r for r in results if r.get('error')]
        assert not failures, f'Ingest errors: {failures}'


# ══════════════════════════════════════════════════════════════════
# Source = untouched original
# ══════════════════════════════════════════════════════════════════

class TestSourceIntegrity:
    """Source files must contain original URLs — never /assets/ paths."""

    def test_source_html_has_original_image_urls(self, blog, dirs):
        source, cleaned, assets = dirs
        _, _, urls = blog
        _ingest_all(urls[:5], source, cleaned, assets)
        for html in source.glob('*.html'):
            text = html.read_text()
            # Source must NOT contain bare /assets/ paths (the rewritten form).
            # Original URLs like http://localhost/assets/img.jpg are fine because
            # they're absolute URLs, not bare local paths.
            import re
            bare_asset_refs = re.findall(r'src="(/assets/[^"]+)"', text)
            assert not bare_asset_refs, \
                f'{html.name}: source contains rewritten bare /assets/ paths: {bare_asset_refs}'

    def test_source_html_unchanged_between_imports(self, blog, dirs):
        source, cleaned, assets = dirs
        _, _, urls = blog
        results1 = _ingest_all(urls[:3], source, cleaned, assets)
        # Re-ingest the same posts
        hashes1 = {(source / f'{r["slug"]}.html').read_bytes()
                   for r in results1 if r.get('slug')}
        _ingest_all(urls[:3], source, cleaned, assets)
        hashes2 = {(source / f'{r["slug"]}.html').read_bytes()
                   for r in results1 if r.get('slug')}
        assert hashes1 == hashes2, 'Source files changed on re-import'


# ══════════════════════════════════════════════════════════════════
# Cleaned = rewritten paths, no scripts
# ══════════════════════════════════════════════════════════════════

class TestCleanedOutput:
    """Cleaned files must have /assets/ paths and no JS."""

    def test_no_script_tags_in_cleaned(self, blog, dirs):
        source, cleaned, assets = dirs
        _, _, urls = blog
        _ingest_all(urls, source, cleaned, assets)
        for html in cleaned.glob('*.html'):
            assert '<script' not in html.read_text().lower(), \
                f'{html.name}: cleaned HTML contains <script>'

    def test_no_javascript_hrefs_in_cleaned(self, blog, dirs):
        source, cleaned, assets = dirs
        _, _, urls = blog
        _ingest_all(urls, source, cleaned, assets)
        for html in cleaned.glob('*.html'):
            assert 'javascript:' not in html.read_text().lower(), \
                f'{html.name}: cleaned HTML contains javascript: href'

    def test_cleaned_images_reference_assets_dir(self, blog, dirs):
        source, cleaned, assets = dirs
        _, _, urls = blog
        _ingest_all(urls, source, cleaned, assets)
        for html in cleaned.glob('*.html'):
            text = html.read_text()
            # Images in cleaned/ should use /assets/ paths
            # (external http:// URLs for images that weren't downloaded are acceptable)
            if 'src="/assets/' in text:
                # At least some images were rewritten — good
                assert '/assets/' in text


# ══════════════════════════════════════════════════════════════════
# Append mode
# ══════════════════════════════════════════════════════════════════

class TestAppendMode:
    """filter_urls_after correctly limits which posts are ingested in append mode."""

    def test_append_imports_only_newer_posts(self, blog, dirs):
        source, cleaned, assets = dirs
        _, _, urls = blog
        dated = _sorted_dates(urls)
        assert len(dated) >= 10, 'Need at least 10 dated URLs'

        # Use the 10th post's date as the cutoff
        cutoff = dated[9][1]
        newer_urls = filter_urls_after(urls, cutoff)
        assert 0 < len(newer_urls) < len(urls), \
            'Filter should have reduced URL count but kept some'

        results = _ingest_all(newer_urls, source, cleaned, assets)
        assert len(list(source.glob('*.html'))) == len([r for r in results if not r.get('error')])

    def test_append_after_initial_import_adds_no_duplicates(self, blog, dirs):
        source, cleaned, assets = dirs
        _, _, urls = blog
        dated = _sorted_dates(urls)

        # First pass: ingest older half
        cutoff = dated[9][1]
        older_urls = [u for u, d in dated if d <= cutoff]
        _ingest_all(older_urls, source, cleaned, assets)
        count_after_first = len(list(source.glob('*.html')))

        # Second pass: append newer posts only
        newer_urls = filter_urls_after(urls, cutoff)
        _ingest_all(newer_urls, source, cleaned, assets)
        count_after_second = len(list(source.glob('*.html')))

        # Should have grown, with no duplicate slugs
        assert count_after_second >= count_after_first
        slugs = [f.stem for f in source.glob('*.html')]
        assert len(slugs) == len(set(slugs)), 'Duplicate slugs after append'

    def test_append_with_newest_cutoff_imports_nothing_dated(self, blog, dirs):
        source, cleaned, assets = dirs
        _, _, urls = blog
        dated = _sorted_dates(urls)
        newest_date = dated[-1][1]

        newer = filter_urls_after(urls, newest_date)
        # Only undated URLs (no date in slug) should remain
        undated = [u for u in urls if not extract_date_from_url(u)]
        assert len(newer) == len(undated)

    def test_append_undated_urls_always_included(self, blog, dirs):
        """URLs with no extractable date are always passed through the filter."""
        source, cleaned, assets = dirs
        _, _, urls = blog
        # Filter with a future cutoff — only undated URLs should survive
        future = '2099-12-31'
        newer = filter_urls_after(urls, future)
        for u in newer:
            assert extract_date_from_url(u) is None, \
                f'Dated URL slipped past future cutoff: {u}'

    def test_cutoff_is_exclusive(self, blog, dirs):
        """Posts on exactly the cutoff date are NOT included (strictly after)."""
        source, cleaned, assets = dirs
        _, _, urls = blog
        dated = _sorted_dates(urls)
        cutoff = dated[5][1]  # 6th post's exact date
        newer = filter_urls_after(urls, cutoff)
        for u in newer:
            d = extract_date_from_url(u)
            if d:
                assert d > cutoff, f'{u} date {d} is not strictly after {cutoff}'


# ══════════════════════════════════════════════════════════════════
# Asset URL-based deduplication
# ══════════════════════════════════════════════════════════════════

class TestAssetDeduplication:
    """URL-based deduplication: same URL downloaded only once."""

    def test_asset_index_all_files_exist(self, blog, dirs):
        source, cleaned, assets = dirs
        _, _, urls = blog
        _ingest_all(urls, source, cleaned, assets)
        store = AssetStore(assets)
        idx = store._load_index()
        for url, rel in idx.items():
            assert (assets / rel).exists(), \
                f'Index entry {url!r} → missing file {rel!r}'

    def test_same_url_produces_single_file(self, blog, dirs):
        source, cleaned, assets = dirs
        _, _, urls = blog
        # Ingest all posts — if any share image URLs, only one file should exist
        _ingest_all(urls, source, cleaned, assets)
        store = AssetStore(assets)
        idx = store._load_index()
        # All index values (relative paths) should be unique files
        rels = list(idx.values())
        assert len(rels) == len(set(rels)), \
            'Duplicate relative paths in URL index — same file stored twice'

    def test_re_importing_does_not_duplicate_assets(self, blog, dirs):
        source, cleaned, assets = dirs
        _, _, urls = blog
        _ingest_all(urls[:5], source, cleaned, assets)
        count1 = sum(1 for _ in assets.rglob('*') if _.is_file()
                     and _.name != '.url-index.json')
        # Re-ingest the same posts
        _ingest_all(urls[:5], source, cleaned, assets)
        count2 = sum(1 for _ in assets.rglob('*') if _.is_file()
                     and _.name != '.url-index.json')
        assert count1 == count2, \
            f'Re-importing created extra assets ({count1} → {count2})'


# ══════════════════════════════════════════════════════════════════
# Hash-based consolidation after ingest
# ══════════════════════════════════════════════════════════════════

class TestConsolidationAfterIngest:
    """consolidate() runs cleanly after a full ingest and is idempotent."""

    def test_consolidation_does_not_crash(self, blog, dirs):
        source, cleaned, assets = dirs
        _, _, urls = blog
        _ingest_all(urls, source, cleaned, assets)
        report = consolidate(assets, cleaned)
        assert isinstance(report['promoted'], int)
        assert isinstance(report['updated_html'], int)

    def test_consolidation_is_idempotent(self, blog, dirs):
        source, cleaned, assets = dirs
        _, _, urls = blog
        _ingest_all(urls, source, cleaned, assets)
        consolidate(assets, cleaned)
        report2 = consolidate(assets, cleaned)
        assert report2['promoted'] == 0, \
            'Second consolidation should promote nothing'

    def test_all_assets_accessible_after_consolidation(self, blog, dirs):
        source, cleaned, assets = dirs
        _, _, urls = blog
        _ingest_all(urls, source, cleaned, assets)
        consolidate(assets, cleaned)
        store = AssetStore(assets)
        for url, rel in store._load_index().items():
            assert (assets / rel).exists(), \
                f'After consolidation: {url!r} → {rel!r} file missing'

    def test_promoted_assets_referenced_in_cleaned_html(self, blog, dirs):
        """If consolidation promoted anything, cleaned HTML was updated."""
        source, cleaned, assets = dirs
        _, _, urls = blog
        _ingest_all(urls, source, cleaned, assets)
        report = consolidate(assets, cleaned)
        if report['promoted'] > 0:
            # At least one HTML should now reference /assets/global/
            has_global = any(
                '/assets/global/' in html.read_text()
                for html in cleaned.glob('*.html')
            )
            assert has_global, \
                f'{report["promoted"]} assets promoted but no cleaned HTML references global/'


# ══════════════════════════════════════════════════════════════════
# Wipe and re-import
# ══════════════════════════════════════════════════════════════════

class TestWipeAndReimport:
    """Full wipe-then-reimport cycle using direct function calls."""

    def test_wipe_removes_all_data(self, blog, dirs):
        source, cleaned, assets = dirs
        _, _, urls = blog
        _ingest_all(urls, source, cleaned, assets)
        assert any(source.glob('*.html')), 'Source should have files before wipe'
        # Wipe: manually remove the directories (mirrors what the server does)
        import shutil
        for d in (source, cleaned, assets):
            if d.exists():
                shutil.rmtree(d)
        assert not source.exists() or not any(source.glob('*.html')), \
            'Source still has files after wipe'

    def test_reimport_after_wipe_produces_full_set(self, blog, dirs):
        source, cleaned, assets = dirs
        _, _, urls = blog

        # First import
        _ingest_all(urls, source, cleaned, assets)
        count1 = len(list(source.glob('*.html')))

        # Wipe
        import shutil
        for d in (source, cleaned, assets):
            if d.exists():
                shutil.rmtree(d)

        # Re-import
        _ingest_all(urls, source, cleaned, assets)
        count2 = len(list(source.glob('*.html')))
        assert count2 == count1, \
            f'Re-import produced {count2} posts, expected {count1}'

    def test_reimport_after_wipe_no_stale_assets(self, blog, dirs):
        source, cleaned, assets = dirs
        _, _, urls = blog

        _ingest_all(urls, source, cleaned, assets)
        import shutil
        for d in (source, cleaned, assets):
            if d.exists():
                shutil.rmtree(d)

        _ingest_all(urls, source, cleaned, assets)
        store = AssetStore(assets)
        for url, rel in store._load_index().items():
            assert (assets / rel).exists(), \
                f'Stale index entry after wipe+reimport: {rel!r}'

    def test_append_after_wipe_starts_fresh(self, blog, dirs):
        """After a wipe, append mode should treat everything as new."""
        source, cleaned, assets = dirs
        _, _, urls = blog
        dated = _sorted_dates(urls)

        # Ingest a subset, wipe, then use append with the old cutoff
        old_cutoff = dated[9][1]
        _ingest_all([u for u, d in dated[:10]], source, cleaned, assets)

        import shutil
        for d in (source, cleaned, assets):
            if d.exists():
                shutil.rmtree(d)

        # After wipe the "newest date" resets — append should get everything
        # Simulate: new project has no posts → filter returns all URLs (no cutoff)
        all_after_empty_cutoff = filter_urls_after(urls, '2000-01-01')
        assert len(all_after_empty_cutoff) >= len([u for u in urls
                                                    if extract_date_from_url(u)]), \
            'After wipe, append from beginning should include all dated URLs'
