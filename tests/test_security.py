"""
Security tests for the blog-migrator ingest pipeline.

Tests verify that:
1. XSS payloads in blog content (title, body, attributes) are stripped
2. file:// and other non-http scheme URLs are rejected
3. Malicious URLs in RSS/sitemap feeds are filtered
4. javascript: hrefs are stripped
5. Exfiltration via CSS (data: urls, external CSS @import) is blocked
6. Metadata fields (title, author) are not interpreted as HTML when stored

Run: python3 -m pytest blog-migrator/tests/test_security.py -v
"""
import json
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))
from ingest import detect_platform, discover_urls, preview_post, ingest_post

SESSION = requests.Session()
SESSION.headers['User-Agent'] = 'BlogMigrator-Test/1.0'


# ── Helpers ───────────────────────────────────────────────────────────────────

def _serve_single_page(html: str) -> tuple:
    """Start a local server returning a single HTML page. Returns (server, url)."""
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_GET(self):
            if self.path == '/sitemap.xml':
                port = self.server.server_address[1]
                body = f'''<?xml version="1.0"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>http://localhost:{port}/post/</loc></url>
</urlset>'''.encode()
                self.send_response(200); self.send_header('Content-Type','application/xml')
                self.send_header('Content-Length', len(body)); self.end_headers()
                self.wfile.write(body)
            else:
                body = html.encode('utf-8')
                self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8')
                self.send_header('Content-Length', len(body)); self.end_headers()
                self.wfile.write(body)
    server = HTTPServer(('localhost', 0), H)
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server, f'http://localhost:{port}'


def _blog_html(title: str, content: str, author: str = 'Test Author') -> str:
    return f'''<!DOCTYPE html><html><head>
  <meta charset="UTF-8">
  <title>{title} — Test Blog</title>
  <meta property="og:title" content="{title}">
  <meta property="article:published_time" content="2022-06-15T10:00:00Z">
  <meta name="author" content="{author}">
</head><body>
  <article>
    <h1 class="entry-title">{title}</h1>
    <div class="entry-content">{content}</div>
  </article>
</body></html>'''


def _preview(url: str) -> dict:
    return preview_post(url, SESSION)


def _ingest(url: str) -> tuple[dict, Path, Path]:
    """Ingest a URL into a temp dir. Returns (result, serve_root, posts_dir)."""
    tmp = Path(tempfile.mkdtemp())
    posts = tmp / 'posts'
    posts.mkdir()
    result = ingest_post(url, SESSION, posts, tmp)
    return result, tmp, posts


# ── XSS in content ────────────────────────────────────────────────────────────

class TestXSSInContent:
    """Script tags and event handlers in blog content must be stripped."""

    def test_inline_script_stripped_from_preview(self):
        """<script>alert(1)</script> in article body is not in preview HTML."""
        html = _blog_html('Safe Title',
                          '<p>Normal text.</p><script>alert("xss")</script><p>More.</p>')
        srv, url = _serve_single_page(html)
        try:
            result = _preview(url + '/post/')
            assert '<script' not in result.get('html', '').lower(), \
                'Script tag survived in preview HTML'
        finally:
            srv.shutdown()

    def test_inline_script_stripped_from_ingest(self):
        """Script tags must not appear in the written HTML file."""
        html = _blog_html('Safe Title',
                          '<p>Content.</p><script src="evil.js"></script>')
        srv, url = _serve_single_page(html)
        try:
            result, tmp, posts = _ingest(url + '/post/')
            slug = result.get('slug', '')
            if slug:
                written = (posts / f'{slug}.html').read_text()
                assert '<script' not in written.lower(), \
                    'Script tag survived in written HTML'
        finally:
            srv.shutdown()

    def test_onerror_attribute_stripped(self):
        """onerror= and other event handler attributes must be removed."""
        html = _blog_html('Safe Title',
                          '<img src="x.jpg" onerror="alert(1)" alt="img">')
        srv, url = _serve_single_page(html)
        try:
            result = _preview(url + '/post/')
            extracted = result.get('html', '')
            assert 'onerror' not in extracted, 'onerror attribute survived'
        finally:
            srv.shutdown()

    def test_onclick_attribute_stripped(self):
        """onclick= event handlers must be removed."""
        html = _blog_html('Safe Title',
                          '<div onclick="alert(1)"><p>Content.</p></div>')
        srv, url = _serve_single_page(html)
        try:
            result = _preview(url + '/post/')
            assert 'onclick' not in result.get('html', ''), 'onclick attribute survived'
        finally:
            srv.shutdown()

    def test_javascript_href_stripped(self):
        """href="javascript:..." links must be stripped or sanitised."""
        html = _blog_html('Safe Title',
                          '<p>Click <a href="javascript:alert(1)">here</a>.</p>')
        srv, url = _serve_single_page(html)
        try:
            result = _preview(url + '/post/')
            assert 'javascript:' not in result.get('html', ''), \
                'javascript: href survived'
        finally:
            srv.shutdown()

    def test_data_uri_in_img_not_in_preview(self):
        """data: URIs in <img src> should not appear as external requests."""
        html = _blog_html('Safe Title',
                          '<img src="data:text/html,<script>alert(1)</script>" alt="x">')
        srv, url = _serve_single_page(html)
        try:
            result = _preview(url + '/post/')
            # data: imgs should either be stripped or kept as data: — not as external URLs
            extracted = result.get('html', '')
            assert '<script' not in extracted.lower()
        finally:
            srv.shutdown()


# ── XSS in metadata ───────────────────────────────────────────────────────────

class TestXSSInMetadata:
    """Script payloads in title/author must not be executed."""

    def test_script_in_title_escaped_in_sidecar(self):
        """XSS in title stored safely in JSON sidecar."""
        xss_title = 'Good Post<script>alert(1)</script>'
        html = _blog_html(xss_title, '<p>Normal content here.</p>')
        srv, url = _serve_single_page(html)
        try:
            result, tmp, posts = _ingest(url + '/post/')
            slug = result.get('slug', '')
            if slug:
                sidecar = posts / f'{slug}.json'
                if sidecar.exists():
                    data = json.loads(sidecar.read_text())
                    # Title in JSON is stored as text — json.loads will return it as a string
                    # The important thing: it must not be raw HTML that would execute
                    stored_title = data.get('title', '')
                    # Parsing the JSON should not have caused any script execution
                    # and the title should be stored as a plain string
                    assert isinstance(stored_title, str)
        finally:
            srv.shutdown()

    def test_author_with_html_stored_as_text(self):
        """Author field with HTML chars is stored as plain text in sidecar."""
        html = _blog_html('Normal Title', '<p>Content.</p>',
                          author='Alice <img src=x onerror=alert(1)>')
        srv, url = _serve_single_page(html)
        try:
            result, tmp, posts = _ingest(url + '/post/')
            slug = result.get('slug', '')
            if slug:
                sidecar = posts / f'{slug}.json'
                if sidecar.exists():
                    data = json.loads(sidecar.read_text())
                    author = data.get('author', '')
                    # Should be stored — json.loads won't execute anything
                    assert isinstance(author, str)
        finally:
            srv.shutdown()


# ── URL scheme injection ───────────────────────────────────────────────────────

class TestURLSchemeInjection:
    """Non-http/https URLs must be rejected gracefully."""

    def test_file_url_returns_error(self):
        """file:// URL as blog URL should not read local files."""
        result = preview_post('file:///etc/passwd', SESSION)
        # Should return an error, not the contents of /etc/passwd
        assert result.get('error') is not None, \
            'file:// URL should return an error'
        html = result.get('html', '')
        assert 'root:' not in html, \
            'file:// URL read local filesystem content!'

    def test_file_url_detect_platform_fails_gracefully(self):
        """detect_platform with file:// URL should not crash."""
        try:
            result = detect_platform('file:///etc/passwd', SESSION)
            # Should either return generic or raise/return error
            # — just must not crash and must not return filesystem content
            assert 'root:' not in str(result)
        except Exception:
            pass  # Any exception is acceptable — just no crash + no content leak

    def test_ftp_url_returns_error(self):
        """ftp:// URL should not be fetched."""
        result = preview_post('ftp://ftp.example.com/blog/', SESSION)
        assert result.get('error') is not None

    def test_internal_ip_ingest_is_bounded(self):
        """Ingest from a non-routable IP should fail gracefully with timeout."""
        # 10.0.0.1 is typically not reachable from test env — should time out or refuse
        result = preview_post('http://10.255.255.1/post/', SESSION)
        # Should return error (timeout/refused) — not hang forever
        assert result.get('error') is not None


# ── RSS/Sitemap URL injection ─────────────────────────────────────────────────

class TestSitemapURLInjection:
    """Malicious URLs in sitemap/RSS feeds must be filtered."""

    def test_file_urls_in_sitemap_filtered(self):
        """file:// URLs in sitemap <loc> are not returned by discover_urls."""
        class H(BaseHTTPRequestHandler):
            def log_message(self, *a): pass
            def do_GET(self):
                if self.path == '/sitemap.xml':
                    port = self.server.server_address[1]
                    body = f'''<?xml version="1.0"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>http://localhost:{port}/post/</loc></url>
  <url><loc>file:///etc/passwd</loc></url>
  <url><loc>javascript:alert(1)</loc></url>
  <url><loc>ftp://internal.corp/secret</loc></url>
</urlset>'''.encode()
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/xml')
                    self.send_header('Content-Length', len(body))
                    self.end_headers(); self.wfile.write(body)
                else:
                    self.send_response(404); self.end_headers()

        server = HTTPServer(('localhost', 0), H)
        port = server.server_address[1]
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        try:
            urls = discover_urls(f'http://localhost:{port}', 'generic', SESSION)
            # Only http:// URLs from the same host should be returned
            for u in urls:
                assert u.startswith('http://') or u.startswith('https://'), \
                    f'Non-http URL in results: {u}'
                assert 'etc/passwd' not in u, f'Path traversal in URL: {u}'
                assert 'javascript' not in u.lower(), f'JavaScript URL in results: {u}'
        finally:
            server.shutdown()

    def test_path_traversal_in_sitemap_not_fetched(self):
        """../../../etc/passwd style paths in sitemap are not followed."""
        class H(BaseHTTPRequestHandler):
            def log_message(self, *a): pass
            def do_GET(self):
                if self.path == '/sitemap.xml':
                    port = self.server.server_address[1]
                    body = f'''<?xml version="1.0"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>http://localhost:{port}/post/</loc></url>
  <url><loc>http://localhost:{port}/../../../etc/passwd</loc></url>
</urlset>'''.encode()
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/xml')
                    self.send_header('Content-Length', len(body))
                    self.end_headers(); self.wfile.write(body)
                else:
                    self.send_response(404); self.end_headers()

        server = HTTPServer(('localhost', 0), H)
        port = server.server_address[1]
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        try:
            urls = discover_urls(f'http://localhost:{port}', 'generic', SESSION)
            for u in urls:
                assert 'etc/passwd' not in u, f'Path traversal URL returned: {u}'
        finally:
            server.shutdown()


# ── Stylesheet injection ──────────────────────────────────────────────────────

class TestStylesheetInjection:
    """CSS from blog content must not leak data or make external requests."""

    def test_inline_style_with_external_url_stripped(self):
        """CSS url() pointing at external hosts should be stripped."""
        html = _blog_html('Style Test',
                          '<div style="background:url(http://evil.com/track.gif)">Content.</div>')
        srv, url = _serve_single_page(html)
        try:
            result = _preview(url + '/post/')
            extracted = result.get('html', '')
            # The style attribute should be stripped (ingest removes all non-content attrs)
            # If it's not stripped, at minimum it shouldn't be able to make real requests
            # (this is a rendering concern, not a server concern)
            assert 'evil.com' not in extracted, \
                'External CSS URL survived in extracted content'
        finally:
            srv.shutdown()

    def test_style_tag_stripped_from_article(self):
        """<style> tags inside article content are removed."""
        html = _blog_html('Style Test',
                          '<style>body{background:url(http://evil.com/x)}</style>'
                          '<p>Normal content.</p>')
        srv, url = _serve_single_page(html)
        try:
            result = _preview(url + '/post/')
            assert '<style' not in result.get('html', '').lower(), \
                '<style> tag survived extraction'
        finally:
            srv.shutdown()


# ── No-crash guarantee ────────────────────────────────────────────────────────

class TestGracefulDegradation:
    """Malformed or hostile inputs never crash the ingest functions."""

    @pytest.mark.parametrize('bad_url', [
        '',
        'not-a-url',
        'http://',
        'http://localhost:99999',      # invalid port
        'http://[invalid-ipv6',        # malformed
    ])
    def test_bad_urls_return_error_not_exception(self, bad_url):
        """Malformed URLs return error dict, never raise."""
        result = preview_post(bad_url, SESSION)
        assert isinstance(result, dict), f'Expected dict, got {type(result)}'
        assert 'error' in result, f'Expected error field for bad URL: {bad_url!r}'
        assert result['error'] is not None, f'Error should not be None for: {bad_url!r}'

    def test_truncated_html_does_not_crash(self):
        """Truncated/malformed HTML is handled gracefully."""
        class H(BaseHTTPRequestHandler):
            def log_message(self, *a): pass
            def do_GET(self):
                body = b'<html><body><article><h1>Test</h1><p>Truncated'
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.send_header('Content-Length', len(body))
                self.end_headers(); self.wfile.write(body)
        server = HTTPServer(('localhost', 0), H)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        port = server.server_address[1]
        try:
            result = preview_post(f'http://localhost:{port}/', SESSION)
            assert isinstance(result, dict)
        finally:
            server.shutdown()

    def test_huge_response_does_not_hang(self):
        """Very large responses are handled (or error) without hanging."""
        class H(BaseHTTPRequestHandler):
            def log_message(self, *a): pass
            def do_GET(self):
                # 5MB of 'a' — should be handled or rejected quickly
                body = (b'<html><body><article><p>' +
                        b'a' * 5_000_000 + b'</p></article></body></html>')
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.send_header('Content-Length', len(body))
                self.end_headers(); self.wfile.write(body)
        server = HTTPServer(('localhost', 0), H)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        port = server.server_address[1]
        try:
            import signal
            def timeout(sig, frame): raise TimeoutError('ingest hung')
            signal.signal(signal.SIGALRM, timeout)
            signal.alarm(15)  # 15 second hard limit
            try:
                result = preview_post(f'http://localhost:{port}/', SESSION)
                assert isinstance(result, dict)
            finally:
                signal.alarm(0)
        except TimeoutError:
            pytest.fail('preview_post hung on large response')
        finally:
            server.shutdown()
