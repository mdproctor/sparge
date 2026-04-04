"""
Tests for scripts/asset_store.py

Run: python3 -m pytest tests/test_asset_store.py -v
"""
import json
import shutil
import tempfile
from pathlib import Path

import pytest

from asset_store import AssetStore, _safe_filename, _split_stem_suffix, file_hash


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_assets(tmp_path):
    """Return a fresh AssetStore backed by a temp directory."""
    return AssetStore(tmp_path / 'assets')


def _write(path: Path, content: bytes = b'imagedata'):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


# ══════════════════════════════════════════════════════════════════════════════
# Path resolution
# ══════════════════════════════════════════════════════════════════════════════

class TestResolve:
    def test_returns_none_for_unknown_url(self, tmp_assets):
        assert tmp_assets.resolve('https://example.com/img.png') is None

    def test_returns_none_web_path_for_unknown(self, tmp_assets):
        assert tmp_assets.web_path('https://example.com/img.png') is None

    def test_returns_path_after_record(self, tmp_assets):
        url   = 'https://example.com/img.png'
        dest  = tmp_assets.allocate(url, 'post-a')
        _write(dest)
        tmp_assets.record(url, dest)
        assert tmp_assets.resolve(url) == dest

    def test_web_path_starts_with_assets(self, tmp_assets):
        url  = 'https://example.com/img.png'
        dest = tmp_assets.allocate(url, 'post-a')
        _write(dest)
        tmp_assets.record(url, dest)
        assert tmp_assets.web_path(url).startswith('/assets/')


# ══════════════════════════════════════════════════════════════════════════════
# Allocation — post-specific routing
# ══════════════════════════════════════════════════════════════════════════════

class TestAllocatePostSpecific:
    """First-seen URL goes into posts/{slug}/."""

    def test_new_url_routes_to_post_folder(self, tmp_assets):
        url  = 'https://blog.example.com/img.png'
        dest = tmp_assets.allocate(url, 'my-post')
        assert 'posts/my-post' in dest.as_posix()

    def test_filename_preserved(self, tmp_assets):
        url  = 'https://example.com/rete-diagram.png'
        dest = tmp_assets.allocate(url, 'my-post')
        assert dest.name == 'rete-diagram.png'

    def test_allocate_twice_same_post_same_url_returns_existing(self, tmp_assets):
        url   = 'https://example.com/img.png'
        dest1 = tmp_assets.allocate(url, 'post-a')
        _write(dest1)
        tmp_assets.record(url, dest1)
        dest2 = tmp_assets.allocate(url, 'post-a')
        assert dest1 == dest2

    def test_index_persists_across_instances(self, tmp_assets):
        url   = 'https://example.com/img.png'
        dest  = tmp_assets.allocate(url, 'post-a')
        _write(dest)
        tmp_assets.record(url, dest)
        # Create a new AssetStore pointing at same directory
        store2 = AssetStore(tmp_assets.root)
        assert store2.resolve(url) == dest


# ══════════════════════════════════════════════════════════════════════════════
# Allocation — URL-based global routing (real-time dedup)
# ══════════════════════════════════════════════════════════════════════════════

class TestAllocateGlobal:
    """URL seen in a second post routes to global/."""

    def test_second_post_routes_to_global(self, tmp_assets):
        url   = 'https://example.com/shared-logo.png'
        # First post downloads it
        dest1 = tmp_assets.allocate(url, 'post-a')
        _write(dest1)
        tmp_assets.record(url, dest1)
        # Second post requests the same URL
        dest2 = tmp_assets.allocate(url, 'post-b')
        # Returns the already-downloaded path (no new download needed)
        assert dest2 == dest1

    def test_same_url_different_post_web_path_unchanged(self, tmp_assets):
        url  = 'https://example.com/logo.png'
        dest = tmp_assets.allocate(url, 'post-a')
        _write(dest)
        tmp_assets.record(url, dest)
        wp   = tmp_assets.web_path(url)
        # Second access should return the same web path
        assert tmp_assets.web_path(url) == wp

    def test_different_urls_different_images_stay_separate(self, tmp_assets):
        url_a = 'https://example.com/diagram.png'
        url_b = 'https://example.com/screenshot.png'
        dest_a = tmp_assets.allocate(url_a, 'post-a')
        _write(dest_a)
        tmp_assets.record(url_a, dest_a)
        dest_b = tmp_assets.allocate(url_b, 'post-a')
        _write(dest_b)
        tmp_assets.record(url_b, dest_b)
        assert dest_a != dest_b
        assert 'posts/post-a' in dest_a.as_posix()
        assert 'posts/post-a' in dest_b.as_posix()


# ══════════════════════════════════════════════════════════════════════════════
# Within-post filename collision resolution
# ══════════════════════════════════════════════════════════════════════════════

class TestFilenameCollision:
    """Two different URLs with the same filename in the same post get suffixes."""

    def test_second_same_name_gets_suffix(self, tmp_assets):
        url_a = 'https://site1.com/diagram.png'
        url_b = 'https://site2.com/diagram.png'
        dest_a = tmp_assets.allocate(url_a, 'post-a')
        _write(dest_a)
        tmp_assets.record(url_a, dest_a)
        dest_b = tmp_assets.allocate(url_b, 'post-a')
        assert dest_b.name == 'diagram-2.png'

    def test_collisions_increment_correctly(self, tmp_assets):
        # site1→img.png, site2→img-2.png, site3→img-3.png
        for host in ['site1', 'site2', 'site3']:
            url  = f'https://{host}.com/img.png'
            dest = tmp_assets.allocate(url, 'post-a')
            _write(dest)
            tmp_assets.record(url, dest)
        # Fourth URL gets img-4.png (first three slots are taken)
        dest4 = tmp_assets.allocate('https://site4.com/img.png', 'post-a')
        assert dest4.name == 'img-4.png'

    def test_collision_across_posts_no_suffix(self, tmp_assets):
        # Same filename in different posts is fine — no collision
        url_a = 'https://site1.com/diagram.png'
        url_b = 'https://site2.com/diagram.png'
        dest_a = tmp_assets.allocate(url_a, 'post-a')
        _write(dest_a)
        tmp_assets.record(url_a, dest_a)
        dest_b = tmp_assets.allocate(url_b, 'post-b')
        assert dest_b.name == 'diagram.png'
        assert 'posts/post-b' in dest_b.as_posix()


# ══════════════════════════════════════════════════════════════════════════════
# promote_to_global (used by consolidation pass)
# ══════════════════════════════════════════════════════════════════════════════

class TestPromoteToGlobal:
    def test_file_moved_to_global(self, tmp_assets):
        url  = 'https://example.com/img.png'
        dest = tmp_assets.allocate(url, 'post-a')
        _write(dest)
        tmp_assets.record(url, dest)
        assert 'posts/post-a' in dest.as_posix()

        new_path = tmp_assets.promote_to_global(dest)
        assert 'global' in new_path.as_posix()
        assert new_path.exists()
        assert not dest.exists()

    def test_index_updated_after_promote(self, tmp_assets):
        url  = 'https://example.com/img.png'
        dest = tmp_assets.allocate(url, 'post-a')
        _write(dest)
        tmp_assets.record(url, dest)
        new_path = tmp_assets.promote_to_global(dest)
        assert tmp_assets.resolve(url) == new_path
        assert 'global' in tmp_assets.web_path(url)

    def test_promote_handles_name_collision_in_global(self, tmp_assets):
        # If global/ already has img.png, promoted file gets suffix
        url_a = 'https://example.com/img.png'
        dest_a = tmp_assets.allocate(url_a, 'post-a')
        _write(dest_a)
        tmp_assets.record(url_a, dest_a)
        # Plant a file in global/ with the same name
        global_img = tmp_assets.root / 'global' / 'img.png'
        _write(global_img, b'other')

        url_b = 'https://other.com/img.png'
        dest_b = tmp_assets.allocate(url_b, 'post-b')
        _write(dest_b)
        tmp_assets.record(url_b, dest_b)
        new_path = tmp_assets.promote_to_global(dest_b)
        assert new_path.name == 'img-2.png'


# ══════════════════════════════════════════════════════════════════════════════
# Inspection helpers
# ══════════════════════════════════════════════════════════════════════════════

class TestInspection:
    def test_all_post_assets_returns_correct_slugs(self, tmp_assets):
        for slug, img in [('post-a', 'a.png'), ('post-b', 'b.png')]:
            url  = f'https://example.com/{img}'
            dest = tmp_assets.allocate(url, slug)
            _write(dest)
            tmp_assets.record(url, dest)
        assets = tmp_assets.all_post_assets()
        assert 'post-a' in assets
        assert 'post-b' in assets

    def test_global_assets_returns_promoted_files(self, tmp_assets):
        url  = 'https://example.com/shared.png'
        dest = tmp_assets.allocate(url, 'post-a')
        _write(dest)
        tmp_assets.record(url, dest)
        tmp_assets.promote_to_global(dest)
        globs = tmp_assets.global_assets()
        assert any('shared' in p.name for p in globs)


# ══════════════════════════════════════════════════════════════════════════════
# Helper functions
# ══════════════════════════════════════════════════════════════════════════════

class TestHelpers:
    @pytest.mark.parametrize('url,expected', [
        ('https://example.com/diagram.png', 'diagram.png'),
        ('https://example.com/path/to/image.jpg', 'image.jpg'),
        ('https://example.com/', 'asset'),
        ('https://example.com/file?v=1&t=2', 'file'),
        ('https://example.com/My Image (1).png', 'My_Image__1_.png'),
    ])
    def test_safe_filename(self, url, expected):
        assert _safe_filename(url) == expected

    @pytest.mark.parametrize('filename,stem,suffix', [
        ('diagram.png', 'diagram', '.png'),
        ('archive.tar.gz', 'archive.tar', '.gz'),
        ('noext', 'noext', ''),
        ('.hidden', '.hidden', ''),
    ])
    def test_split_stem_suffix(self, filename, stem, suffix):
        s, x = _split_stem_suffix(filename)
        assert s == stem and x == suffix

    def test_file_hash_consistent(self, tmp_path):
        f = tmp_path / 'test.png'
        f.write_bytes(b'hello world')
        h1 = file_hash(f)
        h2 = file_hash(f)
        assert h1 == h2
        assert len(h1) == 64

    def test_file_hash_differs_for_different_content(self, tmp_path):
        a = tmp_path / 'a.png'; a.write_bytes(b'aaa')
        b = tmp_path / 'b.png'; b.write_bytes(b'bbb')
        assert file_hash(a) != file_hash(b)

    def test_file_hash_same_for_same_content(self, tmp_path):
        a = tmp_path / 'a.png'; a.write_bytes(b'shared')
        b = tmp_path / 'b.png'; b.write_bytes(b'shared')
        assert file_hash(a) == file_hash(b)
