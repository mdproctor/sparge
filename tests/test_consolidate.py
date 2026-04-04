"""
Tests for scripts/consolidate.py

Run: python3 -m pytest tests/test_consolidate.py -v
"""
from pathlib import Path

import pytest

from asset_store import AssetStore
from consolidate import consolidate


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def project(tmp_path):
    """Return (assets_root, cleaned_dir) as a fresh project structure."""
    assets  = tmp_path / 'assets'
    cleaned = tmp_path / 'cleaned'
    cleaned.mkdir()
    return assets, cleaned


def _plant(assets_root: Path, slug: str, filename: str,
           content: bytes, url: str) -> Path:
    """Write an asset file and record it in the AssetStore index."""
    store = AssetStore(assets_root)
    dest  = assets_root / 'posts' / slug / filename
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content)
    store.record(url, dest)
    return dest


def _html(cleaned_dir: Path, slug: str, body: str) -> Path:
    """Write a minimal cleaned HTML file for a post."""
    f = cleaned_dir / f'{slug}.html'
    f.write_text(f'<html><body>{body}</body></html>', encoding='utf-8')
    return f


# ══════════════════════════════════════════════════════════════════════════════
# Core consolidation behaviour
# ══════════════════════════════════════════════════════════════════════════════

class TestConsolidateBasic:
    def test_unique_images_stay_in_post_folders(self, project):
        assets, cleaned = project
        _plant(assets, 'post-a', 'unique-a.png', b'aaa', 'https://a.com/unique-a.png')
        _plant(assets, 'post-b', 'unique-b.png', b'bbb', 'https://b.com/unique-b.png')
        report = consolidate(assets, cleaned)
        assert report['promoted'] == 0
        assert (assets / 'posts' / 'post-a' / 'unique-a.png').exists()
        assert (assets / 'posts' / 'post-b' / 'unique-b.png').exists()

    def test_shared_image_promoted_to_global(self, project):
        assets, cleaned = project
        shared = b'shared image content'
        _plant(assets, 'post-a', 'logo.png', shared, 'https://a.com/logo.png')
        _plant(assets, 'post-b', 'logo.png', shared, 'https://b.com/logo.png')
        report = consolidate(assets, cleaned)
        assert report['promoted'] == 1
        assert (assets / 'global').exists()
        global_files = list((assets / 'global').iterdir())
        assert len(global_files) == 1

    def test_duplicate_file_removed_from_post_folder(self, project):
        assets, cleaned = project
        shared = b'shared content'
        path_a = _plant(assets, 'post-a', 'img.png', shared, 'https://a.com/img.png')
        path_b = _plant(assets, 'post-b', 'img.png', shared, 'https://b.com/img.png')
        consolidate(assets, cleaned)
        # One of the two should be gone, the other promoted to global
        in_a = path_a.exists()
        in_b = path_b.exists()
        assert not (in_a and in_b), 'Both copies still exist — should have deduplicated'

    def test_three_posts_share_image_one_global_copy(self, project):
        assets, cleaned = project
        shared = b'header image'
        for slug in ['post-a', 'post-b', 'post-c']:
            _plant(assets, slug, 'header.jpg', shared, f'https://{slug}.com/header.jpg')
        report = consolidate(assets, cleaned)
        assert report['promoted'] == 1
        global_files = list((assets / 'global').iterdir())
        assert len(global_files) == 1

    def test_report_contains_duplicate_info(self, project):
        assets, cleaned = project
        shared = b'shared'
        _plant(assets, 'post-a', 'img.png', shared, 'https://a.com/img.png')
        _plant(assets, 'post-b', 'img.png', shared, 'https://b.com/img.png')
        report = consolidate(assets, cleaned)
        assert len(report['duplicates']) == 1
        dup = report['duplicates'][0]
        assert 'hash' in dup
        assert 'global_path' in dup
        assert len(dup['files']) == 2

    def test_different_content_same_filename_not_consolidated(self, project):
        assets, cleaned = project
        _plant(assets, 'post-a', 'img.png', b'content-a', 'https://a.com/img.png')
        _plant(assets, 'post-b', 'img.png', b'content-b', 'https://b.com/img.png')
        report = consolidate(assets, cleaned)
        assert report['promoted'] == 0
        # Both files still exist in their post folders
        assert (assets / 'posts' / 'post-a' / 'img.png').exists()
        assert (assets / 'posts' / 'post-b' / 'img.png').exists()


# ══════════════════════════════════════════════════════════════════════════════
# HTML reference rewriting
# ══════════════════════════════════════════════════════════════════════════════

class TestHtmlRewriting:
    def test_html_reference_updated_to_global(self, project):
        assets, cleaned = project
        shared = b'shared img'
        _plant(assets, 'post-a', 'logo.png', shared, 'https://a.com/logo.png')
        _plant(assets, 'post-b', 'logo.png', shared, 'https://b.com/logo.png')
        _html(cleaned, 'post-a', '<img src="/assets/posts/post-a/logo.png">')
        _html(cleaned, 'post-b', '<img src="/assets/posts/post-b/logo.png">')
        consolidate(assets, cleaned)
        for slug in ['post-a', 'post-b']:
            text = (cleaned / f'{slug}.html').read_text()
            assert '/assets/global/' in text, f'{slug}.html not updated to global/'
            assert '/assets/posts/' not in text, f'{slug}.html still has post-specific path'

    def test_html_unique_images_not_rewritten(self, project):
        assets, cleaned = project
        _plant(assets, 'post-a', 'unique.png', b'aaa', 'https://a.com/unique.png')
        _html(cleaned, 'post-a', '<img src="/assets/posts/post-a/unique.png">')
        consolidate(assets, cleaned)
        text = (cleaned / 'post-a.html').read_text()
        assert '/assets/posts/post-a/unique.png' in text

    def test_updated_html_count_correct(self, project):
        assets, cleaned = project
        shared = b'shared'
        _plant(assets, 'post-a', 'img.png', shared, 'https://a.com/img.png')
        _plant(assets, 'post-b', 'img.png', shared, 'https://b.com/img.png')
        _html(cleaned, 'post-a', '<img src="/assets/posts/post-a/img.png">')
        _html(cleaned, 'post-b', '<img src="/assets/posts/post-b/img.png">')
        _html(cleaned, 'post-c', '<p>No images here.</p>')
        report = consolidate(assets, cleaned)
        assert report['updated_html'] == 2  # post-a and post-b updated, post-c not

    def test_multiple_references_in_same_html_all_rewritten(self, project):
        assets, cleaned = project
        shared = b'logo'
        _plant(assets, 'post-a', 'logo.png', shared, 'https://a.com/logo.png')
        _plant(assets, 'post-b', 'logo.png', shared, 'https://b.com/logo.png')
        # HTML references the image twice
        body = ('<img src="/assets/posts/post-a/logo.png">'
                '<img src="/assets/posts/post-a/logo.png">')
        _html(cleaned, 'post-a', body)
        _html(cleaned, 'post-b', '<img src="/assets/posts/post-b/logo.png">')
        consolidate(assets, cleaned)
        text = (cleaned / 'post-a.html').read_text()
        assert text.count('/assets/global/') == 2

    def test_no_html_files_no_crash(self, project):
        assets, cleaned = project
        shared = b'shared'
        _plant(assets, 'post-a', 'img.png', shared, 'https://a.com/img.png')
        _plant(assets, 'post-b', 'img.png', shared, 'https://b.com/img.png')
        # cleaned/ is empty — no HTML to update
        report = consolidate(assets, cleaned)
        assert report['promoted'] == 1
        assert report['updated_html'] == 0


# ══════════════════════════════════════════════════════════════════════════════
# Asset store index updated after consolidation
# ══════════════════════════════════════════════════════════════════════════════

class TestIndexConsistency:
    def test_index_updated_for_promoted_url(self, project):
        assets, cleaned = project
        shared = b'shared'
        _plant(assets, 'post-a', 'img.png', shared, 'https://a.com/img.png')
        _plant(assets, 'post-b', 'img.png', shared, 'https://b.com/img.png')
        consolidate(assets, cleaned)
        store = AssetStore(assets)
        # Both URLs should now point to global/
        wp_a = store.web_path('https://a.com/img.png')
        wp_b = store.web_path('https://b.com/img.png')
        assert wp_a and '/assets/global/' in wp_a
        assert wp_b and '/assets/global/' in wp_b

    def test_idempotent_second_run_promotes_nothing(self, project):
        assets, cleaned = project
        shared = b'shared'
        _plant(assets, 'post-a', 'img.png', shared, 'https://a.com/img.png')
        _plant(assets, 'post-b', 'img.png', shared, 'https://b.com/img.png')
        report1 = consolidate(assets, cleaned)
        report2 = consolidate(assets, cleaned)
        assert report1['promoted'] == 1
        assert report2['promoted'] == 0  # nothing left to promote
