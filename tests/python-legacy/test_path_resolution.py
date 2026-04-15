import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))


def _make_cfg(serve_root, posts_dir, assets_dir, md_dir):
    """Build a minimal raw config dict for _resolve() testing."""
    import config as _cfg_mod
    orig = _cfg_mod._cfg_path
    _cfg_mod._cfg_path = Path('/tmp/fake/config.json')
    try:
        return _cfg_mod._resolve({
            'serve_root': serve_root,
            'source': {'posts_dir': posts_dir, 'assets_dir': assets_dir},
            'output': {'md_dir': md_dir},
        })
    finally:
        _cfg_mod._cfg_path = orig


class TestResolveRelativePaths:
    def test_relative_md_dir_joins_serve_root(self):
        result = _make_cfg('/srv/blog', 'posts', 'assets', 'out/md')
        assert result['_md_dir'] == Path('/srv/blog/out/md')

    def test_relative_posts_dir_joins_serve_root(self):
        result = _make_cfg('/srv/blog', 'legacy/posts', 'assets', 'out/md')
        assert result['_posts_dir'] == Path('/srv/blog/legacy/posts')

    def test_relative_assets_dir_joins_serve_root(self):
        result = _make_cfg('/srv/blog', 'posts', 'legacy/assets', 'out/md')
        assert result['_assets_dir'] == Path('/srv/blog/legacy/assets')


class TestResolveAbsolutePaths:
    def test_absolute_md_dir_used_as_is(self):
        result = _make_cfg('/srv/blog', 'posts', 'assets', '/external/output')
        assert result['_md_dir'] == Path('/external/output')

    def test_absolute_posts_dir_used_as_is(self):
        result = _make_cfg('/srv/blog', '/data/posts', 'assets', 'out/md')
        assert result['_posts_dir'] == Path('/data/posts')

    def test_absolute_assets_dir_used_as_is(self):
        result = _make_cfg('/srv/blog', 'posts', '/data/assets', 'out/md')
        assert result['_assets_dir'] == Path('/data/assets')

    def test_absolute_inside_serve_root_still_used_as_is(self):
        """An absolute path that happens to be inside serve_root stays absolute."""
        result = _make_cfg('/srv/blog', 'posts', 'assets', '/srv/blog/markdown')
        assert result['_md_dir'] == Path('/srv/blog/markdown')
