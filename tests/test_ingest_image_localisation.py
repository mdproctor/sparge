"""
Unit tests for ingest image localisation (_localise_images).

All network I/O and filesystem writes are mocked — no real HTTP calls are made.
Tests exercise _localise_images directly, covering:

  1. <img src> normal — downloads and replaces src with local path
  2. <img src> imgur — wayback substituted proactively before download
  3. <img src> download fails — wayback tried as fallback (any domain)
  4. <img src> both direct and wayback fail — left as external, counted as failed
  5. <img src> tracking pixel — decomposed, not downloaded
  6. <img src> duplicate — same URL in two <img> tags uses one download
  7. <a href> same as <img src> — reuses local path, no extra download
  8. <a href> same as imgur <img src> — reuses wayback-resolved local path
  9. <a href> different image — downloaded separately
 10. <a href> webpage URL — left as external (no image extension)
 11. <a href> image, download fails — wayback fallback tried
 12. <a href> already local path — untouched
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest
from bs4 import BeautifulSoup

MIGRATOR_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(MIGRATOR_ROOT / 'scripts'))

from ingest import _localise_images, _WAYBACK_DOMAINS

# ── Helpers ───────────────────────────────────────────────────────────────────

def _article(html: str):
    soup = BeautifulSoup(f'<article>{html}</article>', 'html.parser')
    return soup.find('article')


def _make_session(wayback_responses: dict | None = None):
    """Return a mock requests session whose .get() returns pre-canned responses."""
    session = MagicMock()
    wb_responses = wayback_responses or {}

    def _get(url, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        if 'wayback/available' in url:
            # Determine which original URL was looked up
            params = kwargs.get('params', {})
            orig = params.get('url', '')
            snap = wb_responses.get(orig)
            if snap:
                resp.json.return_value = {
                    'archived_snapshots': {
                        'closest': {'available': True, 'status': '200', 'url': snap}
                    }
                }
            else:
                resp.json.return_value = {'archived_snapshots': {}}
        return resp

    session.get.side_effect = _get
    return session


SERVE_ROOT = Path('/fake/serve')
DATE = '2014-10-30'
IMG_URL  = 'http://example.com/image.png'
IMG_URL2 = 'http://example.com/other.jpg'
IMGUR_URL = 'http://i.imgur.com/kDVQjkz.png'
WAYBACK_URL = 'https://web.archive.org/web/20141030/https://i.imgur.com/kDVQjkz.png'
WEBPAGE_URL = 'http://example.com/some-post.html'

LOCAL_IMG  = '/assets/images/2014/10/abc123-image.png'
LOCAL_IMG2 = '/assets/images/2014/10/def456-other.jpg'
LOCAL_WB   = '/assets/images/2014/10/wb789-kDVQjkz.png'


def _patch_asset_helpers(local_img=LOCAL_IMG, local_wb=LOCAL_WB, local_img2=LOCAL_IMG2):
    """Patch _asset_local_path and _download_asset with sensible defaults."""

    def fake_local_path(url, serve_root, subdir, date_str):
        if 'web.archive.org' in url:
            return (SERVE_ROOT / local_wb.lstrip('/'), local_wb)
        if 'other' in url:
            return (SERVE_ROOT / local_img2.lstrip('/'), local_img2)
        return (SERVE_ROOT / local_img.lstrip('/'), local_img)

    return fake_local_path


# ── 1. Normal <img src> localisation ─────────────────────────────────────────

class TestImgSrcNormal:
    def test_img_src_replaced_with_local_path(self, tmp_path):
        article = _article(f'<img src="{IMG_URL}"/>')
        session = _make_session()

        with patch('ingest._asset_local_path', _patch_asset_helpers()), \
             patch('ingest._download_asset', return_value=True):
            stats = _localise_images(article, tmp_path, DATE, session)

        img = article.find('img')
        assert img['src'] == LOCAL_IMG, f'Expected local path, got {img["src"]}'
        assert stats == {'localised': 1, 'failed': 0}

    def test_non_http_src_skipped(self, tmp_path):
        article = _article('<img src="/already/local.png"/>')
        session = _make_session()

        with patch('ingest._download_asset', return_value=True) as mock_dl:
            stats = _localise_images(article, tmp_path, DATE, session)

        mock_dl.assert_not_called()
        assert stats == {'localised': 0, 'failed': 0}

    def test_data_src_skipped(self, tmp_path):
        article = _article('<img src="data:image/png;base64,abc"/>')
        session = _make_session()

        with patch('ingest._download_asset', return_value=True) as mock_dl:
            stats = _localise_images(article, tmp_path, DATE, session)

        mock_dl.assert_not_called()
        assert stats['localised'] == 0


# ── 2. imgur proactive Wayback substitution ───────────────────────────────────

class TestImgurProactiveWayback:
    def test_imgur_src_uses_wayback_url(self, tmp_path):
        article = _article(f'<img src="{IMGUR_URL}"/>')
        session = _make_session(wayback_responses={IMGUR_URL: WAYBACK_URL})

        downloaded = []

        def fake_dl(url, local_path, session):
            downloaded.append(url)
            return True

        with patch('ingest._asset_local_path', _patch_asset_helpers()), \
             patch('ingest._download_asset', side_effect=fake_dl):
            stats = _localise_images(article, tmp_path, DATE, session)

        assert WAYBACK_URL in downloaded, (
            f'Expected download from Wayback URL, got {downloaded}. '
            f'imgur must be fetched via Wayback proactively.'
        )
        assert IMGUR_URL not in downloaded, (
            f'Direct imgur URL must not be downloaded — it returns geo-blocked placeholder.'
        )
        assert stats['localised'] == 1

    def test_imgur_no_snapshot_falls_back_to_direct(self, tmp_path):
        """If Wayback has no snapshot for an imgur image, try direct as last resort."""
        article = _article(f'<img src="{IMGUR_URL}"/>')
        session = _make_session(wayback_responses={})  # no snapshot

        downloaded = []

        def fake_dl(url, local_path, session):
            downloaded.append(url)
            return True

        with patch('ingest._asset_local_path', _patch_asset_helpers()), \
             patch('ingest._download_asset', side_effect=fake_dl):
            _localise_images(article, tmp_path, DATE, session)

        assert IMGUR_URL in downloaded, (
            'When no Wayback snapshot exists, direct URL must still be attempted.'
        )


# ── 3. Failed download → Wayback fallback (any domain) ───────────────────────

class TestWaybackFallbackOnFailure:
    def test_failed_img_download_tries_wayback(self, tmp_path):
        """Any <img src> that fails direct download must try Wayback as fallback."""
        article = _article(f'<img src="{IMG_URL}"/>')
        wb = 'https://web.archive.org/web/20141030/http://example.com/image.png'
        session = _make_session(wayback_responses={IMG_URL: wb})

        call_log = []

        def fake_dl(url, local_path, sess):
            call_log.append(url)
            return 'web.archive.org' in url  # direct fails, wayback succeeds

        with patch('ingest._asset_local_path', _patch_asset_helpers(local_wb='/assets/wb.png')), \
             patch('ingest._download_asset', side_effect=fake_dl):
            stats = _localise_images(article, tmp_path, DATE, session)

        assert IMG_URL in call_log, 'Direct URL must be tried first'
        assert wb in call_log, (
            'After direct download fails, Wayback must be tried as fallback. '
            'Currently only imgur gets this treatment — all domains should.'
        )
        assert stats['localised'] == 1
        assert stats['failed'] == 0

    def test_failed_href_download_tries_wayback(self, tmp_path):
        """Any <a href> image link that fails download must try Wayback as fallback."""
        article = _article(
            f'<a href="{IMG_URL2}"><img src="/local/thumb.jpg"/></a>'
        )
        wb = 'https://web.archive.org/web/20141030/http://example.com/other.jpg'
        session = _make_session(wayback_responses={IMG_URL2: wb})

        call_log = []

        def fake_dl(url, local_path, sess):
            call_log.append(url)
            return 'web.archive.org' in url

        with patch('ingest._asset_local_path', _patch_asset_helpers(local_wb='/assets/wb2.png')), \
             patch('ingest._download_asset', side_effect=fake_dl):
            stats = _localise_images(article, tmp_path, DATE, session)

        assert IMG_URL2 in call_log, 'Direct href URL must be tried first'
        assert wb in call_log, (
            'After href direct download fails, Wayback must be tried as fallback.'
        )
        assert stats['localised'] == 1

    def test_both_direct_and_wayback_fail_counted_as_failed(self, tmp_path):
        """If both direct download and Wayback fail, counted as failed — src unchanged."""
        article = _article(f'<img src="{IMG_URL}"/>')
        session = _make_session(wayback_responses={IMG_URL: 'https://web.archive.org/web/xyz'})

        with patch('ingest._asset_local_path', _patch_asset_helpers()), \
             patch('ingest._download_asset', return_value=False):
            stats = _localise_images(article, tmp_path, DATE, session)

        img = article.find('img')
        assert img['src'] == IMG_URL, 'src must remain external when all downloads fail'
        assert stats == {'localised': 0, 'failed': 1}


# ── 4. Tracking pixel removed ─────────────────────────────────────────────────

class TestTrackingPixel:
    def test_tracking_pixel_decomposed(self, tmp_path):
        article = _article(
            '<img src="http://track.example.com/pixel.gif" width="1" height="1" alt=""/>'
        )
        session = _make_session()

        with patch('ingest._is_tracking_pixel', return_value=True), \
             patch('ingest._download_asset', return_value=True) as mock_dl:
            stats = _localise_images(article, tmp_path, DATE, session)

        assert article.find('img') is None, 'Tracking pixel must be removed from article'
        mock_dl.assert_not_called()
        assert stats == {'localised': 0, 'failed': 0}


# ── 5. Duplicate <img src> reuses one download ────────────────────────────────

class TestDuplicateImgSrc:
    def test_same_url_in_two_imgs_downloads_once(self, tmp_path):
        article = _article(
            f'<img src="{IMG_URL}"/><img src="{IMG_URL}"/>'
        )
        session = _make_session()
        call_count = []

        def fake_dl(url, local_path, sess):
            call_count.append(url)
            return True

        with patch('ingest._asset_local_path', _patch_asset_helpers()), \
             patch('ingest._download_asset', side_effect=fake_dl):
            stats = _localise_images(article, tmp_path, DATE, session)

        assert len(call_count) == 1, (
            f'Same URL in two <img> tags must only be downloaded once, '
            f'got {len(call_count)} downloads'
        )
        assert stats['localised'] == 2  # both imgs updated


# ── 6. <a href> same image as <img src> ──────────────────────────────────────

class TestAHrefSameImage:
    def test_href_same_as_src_reuses_local_path(self, tmp_path):
        """<a href> wrapping <img src> with same URL must reuse the local path."""
        article = _article(
            f'<a href="{IMG_URL}"><img src="{IMG_URL}"/></a>'
        )
        session = _make_session()
        call_count = []

        def fake_dl(url, local_path, sess):
            call_count.append(url)
            return True

        with patch('ingest._asset_local_path', _patch_asset_helpers()), \
             patch('ingest._download_asset', side_effect=fake_dl):
            stats = _localise_images(article, tmp_path, DATE, session)

        a = article.find('a')
        img = article.find('img')
        assert img['src'] == LOCAL_IMG
        assert a['href'] == LOCAL_IMG, (
            f'<a href> must be updated to local path when it wraps same-URL img. '
            f'Got: {a["href"]}'
        )
        assert len(call_count) == 1, (
            f'Same image in href and src must download only once, '
            f'got {len(call_count)} downloads'
        )
        assert stats == {'localised': 1, 'failed': 0}

    def test_imgur_href_same_as_src_reuses_wayback_path(self, tmp_path):
        """imgur <a href> wrapping same imgur <img src> must reuse the wayback-resolved path."""
        article = _article(
            f'<a href="{IMGUR_URL}"><img src="{IMGUR_URL}"/></a>'
        )
        session = _make_session(wayback_responses={IMGUR_URL: WAYBACK_URL})
        call_count = []

        def fake_dl(url, local_path, sess):
            call_count.append(url)
            return True

        with patch('ingest._asset_local_path', _patch_asset_helpers()), \
             patch('ingest._download_asset', side_effect=fake_dl):
            stats = _localise_images(article, tmp_path, DATE, session)

        a = article.find('a')
        img = article.find('img')
        assert img['src'] == a['href'], (
            'href and src must point to the same local asset when they were the same URL'
        )
        assert len(call_count) == 1, 'Only one download for both href and src'
        assert stats == {'localised': 1, 'failed': 0}


# ── 7. <a href> different image ───────────────────────────────────────────────

class TestAHrefDifferentImage:
    def test_href_different_image_downloaded_separately(self, tmp_path):
        """<a href> pointing to a different image than <img src> must be downloaded."""
        article = _article(
            f'<a href="{IMG_URL2}"><img src="{IMG_URL}"/></a>'
        )
        session = _make_session()
        downloaded = []

        def fake_dl(url, local_path, sess):
            downloaded.append(url)
            return True

        with patch('ingest._asset_local_path', _patch_asset_helpers()), \
             patch('ingest._download_asset', side_effect=fake_dl):
            stats = _localise_images(article, tmp_path, DATE, session)

        assert IMG_URL in downloaded
        assert IMG_URL2 in downloaded, (
            'Different image in href must be downloaded separately'
        )
        assert stats == {'localised': 2, 'failed': 0}

    def test_href_webpage_left_as_external(self, tmp_path):
        """<a href> pointing to a webpage (no image extension) must not be localised."""
        article = _article(
            f'<a href="{WEBPAGE_URL}"><img src="{IMG_URL}"/></a>'
        )
        session = _make_session()
        downloaded = []

        def fake_dl(url, local_path, sess):
            downloaded.append(url)
            return True

        with patch('ingest._asset_local_path', _patch_asset_helpers()), \
             patch('ingest._download_asset', side_effect=fake_dl):
            stats = _localise_images(article, tmp_path, DATE, session)

        a = article.find('a')
        assert a['href'] == WEBPAGE_URL, (
            f'Webpage href must remain external. Got: {a["href"]}'
        )
        assert WEBPAGE_URL not in downloaded, 'Webpage href must not be downloaded'
        assert stats['localised'] == 1   # only the img src

    def test_href_imgur_uses_wayback(self, tmp_path):
        """<a href> pointing to imgur (different from img src) must use Wayback."""
        article = _article(
            f'<a href="{IMGUR_URL}"><img src="{IMG_URL}"/></a>'
        )
        session = _make_session(wayback_responses={IMGUR_URL: WAYBACK_URL})
        downloaded = []

        def fake_dl(url, local_path, sess):
            downloaded.append(url)
            return True

        with patch('ingest._asset_local_path', _patch_asset_helpers()), \
             patch('ingest._download_asset', side_effect=fake_dl):
            _localise_images(article, tmp_path, DATE, session)

        assert WAYBACK_URL in downloaded, (
            f'imgur href must be fetched via Wayback. Downloaded: {downloaded}'
        )
        assert IMGUR_URL not in downloaded


# ── 8. Already-local href untouched ──────────────────────────────────────────

class TestAlreadyLocalHref:
    def test_already_local_href_not_reprocessed(self, tmp_path):
        """<a href> that already points to a local path must not be downloaded."""
        local_href = '/legacy/assets/images/2014/10/already-local.png'
        article = _article(
            f'<a href="{local_href}"><img src="{IMG_URL}"/></a>'
        )
        session = _make_session()
        downloaded = []

        def fake_dl(url, local_path, sess):
            downloaded.append(url)
            return True

        with patch('ingest._asset_local_path', _patch_asset_helpers()), \
             patch('ingest._download_asset', side_effect=fake_dl):
            _localise_images(article, tmp_path, DATE, session)

        a = article.find('a')
        assert a['href'] == local_href, 'Already-local href must not be changed'
        assert local_href not in downloaded


# ── 9. _try_download: already-wayback URL skips double fallback ───────────────

class TestTryDownloadWaybackGuard:
    def test_already_wayback_url_does_not_retry_wayback(self, tmp_path):
        """If _resolve_download_src returns a wayback URL and it fails,
        we must NOT call _wayback_url again — the guard 'web.archive.org' not
        in download_src prevents an infinite loop."""
        from ingest import _try_download

        wb_src = 'https://web.archive.org/web/20141030/https://i.imgur.com/abc.png'
        session = MagicMock()
        wayback_calls = []

        def fake_wayback(url, date_str, sess):
            wayback_calls.append(url)
            return wb_src  # proactive substitution

        with patch('ingest._resolve_download_src', return_value=wb_src), \
             patch('ingest._asset_local_path', return_value=(tmp_path / 'x.png', '/local/x.png')), \
             patch('ingest._download_asset', return_value=False), \
             patch('ingest._wayback_url', side_effect=fake_wayback) as mock_wb:
            _try_download('http://i.imgur.com/abc.png', DATE, tmp_path, session)

        mock_wb.assert_not_called(), (
            '_wayback_url must not be called when download_src is already a '
            'web.archive.org URL — would be a redundant retry'
        )

    def test_wayback_fallback_not_called_twice_for_same_url(self, tmp_path):
        """If _try_download already resolved to the same wayback URL, skip the
        fallback call (wb == download_src guard)."""
        from ingest import _try_download

        wb = 'https://web.archive.org/web/20141030/http://example.com/img.png'
        session = MagicMock()

        def fake_resolve(src, date_str, sess):
            return src  # no proactive substitution

        with patch('ingest._resolve_download_src', side_effect=fake_resolve), \
             patch('ingest._asset_local_path', return_value=(tmp_path / 'x.png', '/local/x.png')), \
             patch('ingest._download_asset', return_value=False), \
             patch('ingest._wayback_url', return_value=wb) as mock_wb:
            # wb == download_src (both are the same non-wayback URL resolved to same wb)
            # In this case wb != download_src so the fallback IS attempted — test that
            # it doesn't loop if wb comes back the same
            _try_download('http://example.com/img.png', DATE, tmp_path, session)

        # _wayback_url called once — that's fine
        assert mock_wb.call_count <= 1, 'Wayback API must not be called more than once per URL'


# ── 10. Parent <a href> with DIFFERENT href — must not be updated ─────────────

class TestAHrefDifferentFromSrc:
    def test_parent_href_differs_from_src_not_touched_in_pass1(self, tmp_path):
        """If <a href> wraps <img src> but href points to a DIFFERENT URL,
        pass 1 must NOT overwrite the href.  Pass 2 handles it separately."""
        different_href = 'http://example.com/fullsize.jpg'
        article = _article(
            f'<a href="{different_href}"><img src="{IMG_URL}"/></a>'
        )
        session = _make_session()
        downloaded = []

        def fake_dl(url, local_path, sess):
            downloaded.append(url)
            return True

        with patch('ingest._asset_local_path', _patch_asset_helpers()), \
             patch('ingest._download_asset', side_effect=fake_dl):
            stats = _localise_images(article, tmp_path, DATE, session)

        a = article.find('a')
        img = article.find('img')
        assert img['src'] == LOCAL_IMG, 'img src must be localised'
        assert a['href'] != IMG_URL, 'href must not be set to img src URL'
        # href should be localised to its own local path (via pass 2)
        assert a['href'].startswith('/'), f'href should be local path, got {a["href"]}'
        assert stats['localised'] == 2  # img src + href


# ── 11. Standalone <a href> image (no <img> inside) ──────────────────────────

class TestStandaloneAHref:
    def test_standalone_image_href_localised(self, tmp_path):
        """<a href> pointing to an image with no <img> inside must be localised
        by pass 2."""
        article = _article(f'<a href="{IMG_URL}">Click to view image</a>')
        session = _make_session()

        with patch('ingest._asset_local_path', _patch_asset_helpers()), \
             patch('ingest._download_asset', return_value=True):
            stats = _localise_images(article, tmp_path, DATE, session)

        a = article.find('a')
        assert a['href'] == LOCAL_IMG, (
            f'Standalone <a href> image link must be localised. Got: {a["href"]}'
        )
        assert stats == {'localised': 1, 'failed': 0}

    def test_standalone_webpage_href_untouched(self, tmp_path):
        """<a href> pointing to a webpage with no <img> inside must be left alone."""
        article = _article(f'<a href="{WEBPAGE_URL}">Read more</a>')
        session = _make_session()

        with patch('ingest._download_asset', return_value=True) as mock_dl:
            stats = _localise_images(article, tmp_path, DATE, session)

        a = article.find('a')
        assert a['href'] == WEBPAGE_URL
        mock_dl.assert_not_called()
        assert stats == {'localised': 0, 'failed': 0}


# ── 12. Nested img inside <span> inside <a> ───────────────────────────────────

class TestNestedImgInsideA:
    def test_img_nested_in_span_inside_a_href_localised_by_pass2(self, tmp_path):
        """<a href="img.png"><span><img src="img.png"/></span></a>
        Pass 1 sees parent=<span>, not <a>, so it can't update href directly.
        Pass 2 must catch the href because href is in seen after img is localised."""
        article = _article(
            f'<a href="{IMG_URL}"><span><img src="{IMG_URL}"/></span></a>'
        )
        session = _make_session()
        downloaded = []

        def fake_dl(url, local_path, sess):
            downloaded.append(url)
            return True

        with patch('ingest._asset_local_path', _patch_asset_helpers()), \
             patch('ingest._download_asset', side_effect=fake_dl):
            stats = _localise_images(article, tmp_path, DATE, session)

        a = article.find('a')
        img = article.find('img')
        assert img['src'] == LOCAL_IMG
        assert a['href'] == LOCAL_IMG, (
            f'href must be updated to local path by pass 2 (src was added to seen '
            f'in pass 1, href matches). Got: {a["href"]}'
        )
        assert len(downloaded) == 1, 'Only one download — pass 2 reuses from seen'
        assert stats == {'localised': 1, 'failed': 0}
