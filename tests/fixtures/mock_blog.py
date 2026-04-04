"""
Mock WordPress-like blog server for integration testing.

Provides a session-scoped pytest fixture `mock_blog_server` that starts a
local HTTP server serving 20 articles, a sitemap, and minimal JPEG images.
Also exposes the `ARTICLES` list for use in test assertions.
"""

import re
import threading
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

# ── Minimal valid 1×1 JPEG (red pixel) ────────────────────────────────────────

TINY_JPEG = bytes([
    0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01,
    0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43,
    0x00, 0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08, 0x07, 0x07, 0x07, 0x09,
    0x09, 0x08, 0x0A, 0x0C, 0x14, 0x0D, 0x0C, 0x0B, 0x0B, 0x0C, 0x19, 0x12,
    0x13, 0x0F, 0x14, 0x1D, 0x1A, 0x1F, 0x1E, 0x1D, 0x1A, 0x1C, 0x1C, 0x20,
    0x24, 0x2E, 0x27, 0x20, 0x22, 0x2C, 0x23, 0x1C, 0x1C, 0x28, 0x37, 0x29,
    0x2C, 0x30, 0x31, 0x34, 0x34, 0x34, 0x1F, 0x27, 0x39, 0x3D, 0x38, 0x32,
    0x3C, 0x2E, 0x33, 0x34, 0x32, 0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x00, 0x01,
    0x00, 0x01, 0x01, 0x01, 0x11, 0x00, 0xFF, 0xC4, 0x00, 0x1F, 0x00, 0x00,
    0x01, 0x05, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
    0x09, 0x0A, 0x0B, 0xFF, 0xC4, 0x00, 0xB5, 0x10, 0x00, 0x02, 0x01, 0x03,
    0x03, 0x02, 0x04, 0x03, 0x05, 0x05, 0x04, 0x04, 0x00, 0x00, 0x01, 0x7D,
    0x01, 0x02, 0x03, 0x00, 0x04, 0x11, 0x05, 0x12, 0x21, 0x31, 0x41, 0x06,
    0x13, 0x51, 0x61, 0x07, 0x22, 0x71, 0x14, 0x32, 0x81, 0x91, 0xA1, 0x08,
    0x23, 0x42, 0xB1, 0xC1, 0x15, 0x52, 0xD1, 0xF0, 0x24, 0x33, 0x62, 0x72,
    0x82, 0x09, 0x0A, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x25, 0x26, 0x27, 0x28,
    0x29, 0x2A, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3A, 0x43, 0x44, 0x45,
    0x46, 0x47, 0x48, 0x49, 0x4A, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59,
    0x5A, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69, 0x6A, 0x73, 0x74, 0x75,
    0x76, 0x77, 0x78, 0x79, 0x7A, 0x83, 0x84, 0x85, 0x86, 0x87, 0x88, 0x89,
    0x8A, 0x92, 0x93, 0x94, 0x95, 0x96, 0x97, 0x98, 0x99, 0x9A, 0xA2, 0xA3,
    0xA4, 0xA5, 0xA6, 0xA7, 0xA8, 0xA9, 0xAA, 0xB2, 0xB3, 0xB4, 0xB5, 0xB6,
    0xB7, 0xB8, 0xB9, 0xBA, 0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7, 0xC8, 0xC9,
    0xCA, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8, 0xD9, 0xDA, 0xE1, 0xE2,
    0xE3, 0xE4, 0xE5, 0xE6, 0xE7, 0xE8, 0xE9, 0xEA, 0xF1, 0xF2, 0xF3, 0xF4,
    0xF5, 0xF6, 0xF7, 0xF8, 0xF9, 0xFA, 0xFF, 0xDA, 0x00, 0x08, 0x01, 0x01,
    0x00, 0x00, 0x3F, 0x00, 0xFB, 0xD3, 0xFF, 0xD9,
])

# ── Lorem-style paragraph pool ─────────────────────────────────────────────────

_PARAGRAPHS = [
    (
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
        "Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. "
        "Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris."
    ),
    (
        "Duis aute irure dolor in reprehenderit in voluptate velit esse cillum "
        "dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non "
        "proident, sunt in culpa qui officia deserunt mollit anim id est laborum."
    ),
    (
        "Pellentesque habitant morbi tristique senectus et netus et malesuada "
        "fames ac turpis egestas. Vestibulum tortor quam, feugiat vitae, "
        "ultricies eget, tempor sit amet, ante."
    ),
    (
        "Donec eu libero sit amet quam egestas semper. Aenean ultricies mi vitae "
        "est. Mauris placerat eleifend leo. Quisque sit amet est et sapien "
        "ullamcorper pharetra."
    ),
    (
        "Curabitur pretium tincidunt lacus. Nulla gravida orci a odio. Nullam "
        "varius, turpis molestie dictum semper, nunc augue placerat leo, vel "
        "interdum quam nunc sit amet dui."
    ),
    (
        "Praesent dapibus, neque id cursus faucibus, tortor neque egestas augue, "
        "eu vulputate magna eros eu erat. Aliquam erat volutpat. Nam dui mi, "
        "tincidunt quis, accumsan porttitor, facilisis luctus, metus."
    ),
    (
        "Integer in mauris eu nibh euismod gravida diam. Morbi in sem quis dui "
        "placerat ornare. Pellentesque odio nisi, euismod in, pharetra a, "
        "ultricies in, diam."
    ),
]


# ── Article generation ─────────────────────────────────────────────────────────

_AUTHORS = ["Alice Smith", "Bob Jones", "Carol White"]
_TOPICS = ["Technology", "Engineering", "Design"]

_ARTICLE_TITLES = [
    "Introduction to Modern Software Architecture",
    "Building Scalable Distributed Systems",
    "The Art of Clean Code Design",
    "Understanding Database Performance Tuning",
    "Microservices Patterns and Best Practices",
    "Functional Programming in the Real World",
    "DevOps Culture and Continuous Delivery",
    "Designing Resilient Cloud Infrastructure",
    "Machine Learning Pipeline Engineering",
    "API Design Principles for Developers",
    "Observability and Monitoring Strategies",
    "Container Orchestration with Kubernetes",
    "Event-Driven Architecture Deep Dive",
    "Security Engineering Fundamentals",
    "Test-Driven Development Techniques",
    "Domain-Driven Design in Practice",
    "Performance Optimisation at Scale",
    "Data Engineering and Stream Processing",
    "Infrastructure as Code with Terraform",
    "Collaborative Engineering Team Workflows",
]

assert len(_ARTICLE_TITLES) == 20, "Must have exactly 20 titles"


def _title_to_slug(title: str) -> str:
    """Convert title to a URL-friendly slug."""
    slug = title.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug


def _build_articles() -> list[dict]:
    """Generate 20 article metadata dicts with evenly distributed dates."""
    start = date(2020, 1, 15)
    end = date(2023, 11, 20)
    total_days = (end - start).days
    articles = []
    for i, title in enumerate(_ARTICLE_TITLES):
        # Evenly space across the date range (index 0 → start, index 19 → end)
        frac = i / (len(_ARTICLE_TITLES) - 1)
        article_date = start + timedelta(days=int(total_days * frac))
        author = _AUTHORS[i % len(_AUTHORS)]
        topic = _TOPICS[i % len(_TOPICS)]
        slug_title = _title_to_slug(title)
        slug_path = (
            f"{article_date.year}/{article_date.month:02d}"
            f"/{article_date.day:02d}/{slug_title}"
        )
        # Three paragraphs, cycling through the pool
        p1 = _PARAGRAPHS[i % len(_PARAGRAPHS)]
        p2 = _PARAGRAPHS[(i + 2) % len(_PARAGRAPHS)]
        p3 = _PARAGRAPHS[(i + 4) % len(_PARAGRAPHS)]
        articles.append(
            {
                "n": i + 1,
                "title": title,
                "author": author,
                "topic": topic,
                "date": article_date.isoformat(),
                "slug": slug_path,
                "slug_title": slug_title,
                "p1": p1,
                "p2": p2,
                "p3": p3,
            }
        )
    return articles


# Module-level articles list, available for test assertions
ARTICLES: list[dict] = _build_articles()


# ── HTML / XML generators ──────────────────────────────────────────────────────

def _render_article_html(article: dict, port: int) -> str:
    n = article["n"]
    title = article["title"]
    author = article["author"]
    date_str = article["date"]
    slug = article["slug"]
    p1, p2, p3 = article["p1"], article["p2"], article["p3"]
    # Use an absolute URL for the image so ingest_post can localise it
    # (ingest_post only downloads images whose src starts with 'http')
    img_src = f"http://localhost:{port}/assets/img{n:03d}.jpg"
    return f"""\
<!DOCTYPE html><html><head>
  <meta charset="UTF-8">
  <title>{title} \u2014 Mock Blog</title>
  <meta property="og:title" content="{title}">
  <meta property="og:site_name" content="Mock Blog">
  <meta property="article:published_time" content="{date_str}T10:00:00Z">
  <meta name="author" content="{author}">
  <link rel="canonical" href="http://localhost:{port}/{slug}">
</head><body>
  <header class="site-header"><nav>Mock Blog Nav</nav></header>
  <article class="post">
    <h1 class="entry-title">{title}</h1>
    <div class="entry-meta">by {author} on {date_str}</div>
    <div class="entry-content">
      <p>{p1}</p>
      <img src="{img_src}" alt="Figure {n}">
      <p>{p2}</p>
      <p>{p3}</p>
    </div>
  </article>
  <aside class="sidebar"><div class="widget">Recent Posts</div></aside>
  <div id="comments"><h2>Comments</h2></div>
  <footer class="site-footer">\u00a9 Mock Blog</footer>
</body></html>"""


def _render_sitemap(port: int) -> str:
    urls_xml = "\n".join(
        f"  <url>"
        f"<loc>http://localhost:{port}/{a['slug']}/</loc>"
        f"<lastmod>{a['date']}</lastmod>"
        f"</url>"
        for a in ARTICLES
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls_xml}\n"
        "</urlset>"
    )


# ── HTTP request handler ───────────────────────────────────────────────────────

class MockBlogHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler for the mock blog."""

    _port: int = 0  # set by fixture after server binds

    # Map slug_path → article dict for O(1) lookups
    _slug_map: dict[str, dict] = {}

    # Map image filename → index (1-based) for assets
    _image_map: dict[str, bool] = {}

    def log_message(self, format, *args):  # noqa: A002
        # Suppress default request logging during tests
        pass

    def _send_response_body(self, body: bytes, content_type: str, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        path = self.path.split("?")[0]  # strip query string

        # ── Sitemap ───────────────────────────────────────────────────────────
        if path == "/sitemap.xml":
            body = _render_sitemap(self.__class__._port).encode("utf-8")
            self._send_response_body(body, "application/xml")
            return

        # ── Images ────────────────────────────────────────────────────────────
        if path.startswith("/assets/img") and path.endswith(".jpg"):
            self._send_response_body(TINY_JPEG, "image/jpeg")
            return

        # ── Article pages ─────────────────────────────────────────────────────
        # Strip leading/trailing slashes for lookup
        key = path.strip("/")
        article = self.__class__._slug_map.get(key)
        if article is not None:
            html = _render_article_html(article, self.__class__._port)
            body = html.encode("utf-8")
            self._send_response_body(body, "text/html; charset=utf-8")
            return

        # ── 404 ───────────────────────────────────────────────────────────────
        body = b"<html><body><h1>404 Not Found</h1></body></html>"
        self._send_response_body(body, "text/html", status=404)


def _build_slug_map() -> dict[str, dict]:
    """Build the slug → article lookup map."""
    return {a["slug"]: a for a in ARTICLES}


# Pre-build slug map at import time
MockBlogHandler._slug_map = _build_slug_map()


def start_mock_blog() -> tuple:
    """Start the mock blog server and return (server, base_url).
    Caller is responsible for calling server.shutdown()."""
    server = HTTPServer(("localhost", 0), MockBlogHandler)
    port = server.server_address[1]
    MockBlogHandler._port = port
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server, f"http://localhost:{port}"


# ── Pytest fixture ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def mock_blog_server():
    """Start mock blog, yield base URL, shut down after test session."""
    server, url = start_mock_blog()
    yield url
    server.shutdown()
