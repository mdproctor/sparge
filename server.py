#!/usr/bin/env python3
"""
Sparge — unified server.

Serves static files from serve_root AND the UI, plus a JSON API.

Endpoints
─────────
GET  /                              → redirect to /ui/
GET  /ui/                           → ui/index.html
GET  /api/config                    → current config (public fields)
POST /api/config                    → update config fields and reload
GET  /api/posts                     → all posts with state (JSON array)
GET  /api/posts/{slug}              → single post state
PATCH /api/posts/{slug}             → update flagged / user_note / reviewed
POST /api/posts/{slug}/generate-md  → generate (or regenerate) Markdown
POST /api/posts/{slug}/generate-md?dry=1 → dry-run: return content, no write
POST /api/posts/{slug}/validate-md  → run MD validator
POST /api/posts/{slug}/scan-html    → scan HTML for issues
POST /api/posts/{slug}/scan-assets  → scan image/asset localisation for this post
POST /api/posts/{slug}/save-md      → body=md content → write directly (manual edit)
POST /api/posts/{slug}/stage        → body=md content → write .md.staged, mark staged
GET  /api/posts/{slug}/staged       → return content of .md.staged file
POST /api/posts/{slug}/accept-staged → promote .md.staged → .md
POST /api/posts/{slug}/reject-staged → delete .md.staged, clear staged flag
POST /api/ingest/detect             → body={url} → detect platform + blog name
POST /api/ingest/discover           → body={url,author_filter} → list post URLs
POST /api/ingest/preview            → body={url} → extract one post (no write)
POST /api/ingest/run                → body={urls,author_filter} → start background ingest
GET  /api/ingest/status             → current ingest job progress
POST /api/ingest/cancel             → cancel running ingest job
GET  /*                             → static file from serve_root
"""
import json
import mimetypes
import re
import sys
import threading
import urllib.parse
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

# ── Bootstrap path so scripts/ is importable ──────────────────────────────────
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from scripts.config import cfg, set_config_path
from scripts import state as State
from scripts.state import stage as state_stage, accept_staged, reject_staged, set_state_file

UI_DIR = ROOT / 'ui'

# ── Projects management ────────────────────────────────────────────────────────
PROJECTS_FILE = ROOT / 'projects.json'
_active_project_id: str | None = None


def _load_projects() -> list[dict]:
    if PROJECTS_FILE.exists():
        return json.loads(PROJECTS_FILE.read_text())
    return []


def _save_projects(projects: list[dict]):
    PROJECTS_FILE.write_text(json.dumps(projects, indent=2))


def _project_dir(project_id: str) -> Path:
    return ROOT / 'projects' / project_id


def _activate_project(project_id: str) -> bool:
    """Load project config + state, update all module-level path vars."""
    global _active_project_id, POSTS_DIR, MD_DIR, SERVE_ROOT, SOURCE_DIR, CLEANED_DIR, ASSETS_ROOT
    proj_dir    = _project_dir(project_id)
    config_path = proj_dir / 'config.json'
    state_path  = proj_dir / 'state.json'
    if not config_path.exists():
        return False
    set_config_path(config_path)   # mutates cfg in-place
    set_state_file(state_path)
    SERVE_ROOT   = cfg['_root']
    SOURCE_DIR   = cfg['_source_dir']
    CLEANED_DIR  = cfg['_cleaned_dir']
    ASSETS_ROOT  = cfg['_assets_dir']
    POSTS_DIR    = cfg['_posts_dir']   # = CLEANED_DIR for new schema, original dir for legacy
    MD_DIR       = cfg['_md_dir']
    _active_project_id = project_id
    State.init_from_source()
    print(f'Active project: {project_id} ({len(State.get_all())} posts)')
    return True


def _project_stats(project_id: str) -> dict:
    state_path = _project_dir(project_id) / 'state.json'
    stats = {'total': 0, 'reviewed': 0, 'staged': 0, 'md_generated': 0, 'html_issues': 0}
    if not state_path.exists():
        return stats
    try:
        state = json.loads(state_path.read_text())
        for entry in state.values():
            stats['total'] += 1
            if entry.get('reviewed'):                            stats['reviewed']     += 1
            if entry.get('md', {}).get('staged'):               stats['staged']       += 1
            if entry.get('md', {}).get('generated_at'):         stats['md_generated'] += 1
            if (entry.get('html', {}).get('issues') or []):     stats['html_issues']  += 1
    except Exception:
        pass
    return stats


# Activate on startup — use first project in the index
_startup_projects = _load_projects()
if _startup_projects:
    _activate_project(_startup_projects[0]['id'])

# Fallback path vars (overwritten by _activate_project on startup)
SERVE_ROOT  = cfg.get('_root',        ROOT.parent)
SOURCE_DIR  = cfg.get('_source_dir',  ROOT.parent / 'source')
CLEANED_DIR = cfg.get('_cleaned_dir', ROOT.parent / 'cleaned')
ASSETS_ROOT = cfg.get('_assets_dir',  ROOT.parent / 'assets')
POSTS_DIR   = cfg.get('_posts_dir',   ROOT.parent / 'legacy' / 'posts')
MD_DIR      = cfg.get('_md_dir',      ROOT.parent / 'mark-proctor')

# All tools live in our own scripts/
sys.path.insert(0, str(ROOT / 'scripts'))
try:
    from convert_post import convert_post
    _can_generate = True
except ImportError:
    _can_generate = False

try:
    from md_validator import validate as validate_md
    _can_validate = True
except ImportError:
    _can_validate = False
try:
    from scan_html import scan_post as _scan_post
    _can_scan = True
except ImportError:
    _can_scan = False

try:
    from scan_assets import scan_assets as _scan_assets
    _can_scan_assets = True
except ImportError:
    _can_scan_assets = False

try:
    import requests as _requests
    from ingest import detect_platform, discover_urls, preview_post, ingest_post
    _can_ingest = True
except ImportError:
    _can_ingest = False

# ── Background ingest job state ────────────────────────────────────────────────
_job: dict = {
    'running': False, 'done': 0, 'total': 0,
    'current': '', 'errors': [], 'cancelled': False, 'log': [],
}
_job_lock = threading.Lock()


def _ingest_worker(urls: list, author_filter: str | None):
    """Background thread: ingest each URL, update _job state."""
    import requests
    session = requests.Session()
    session.headers['User-Agent'] = (
        'Mozilla/5.0 (compatible; Sparge/1.0; +https://github.com/mdproctor)')
    with _job_lock:
        _job.update({'running': True, 'done': 0, 'total': len(urls),
                     'errors': [], 'cancelled': False, 'log': []})
    for url in urls:
        with _job_lock:
            if _job['cancelled']:
                break
            _job['current'] = url
        try:
            result = ingest_post(url, session, SOURCE_DIR, CLEANED_DIR, ASSETS_ROOT)
            with _job_lock:
                _job['done'] += 1
                _job['log'].append({'url': url, 'slug': result.get('slug', ''),
                                    'ok': not result.get('error')})
                if result.get('error'):
                    _job['errors'].append({'url': url, 'error': result['error']})
        except Exception as e:
            with _job_lock:
                _job['done'] += 1
                _job['errors'].append({'url': url, 'error': str(e)})
    # Refresh state from newly written posts
    State.init_from_source()
    with _job_lock:
        _job['running'] = False
        _job['current'] = ''


# ── Handler ────────────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        print(f'  {self.command} {self.path}')

    def send_cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PATCH, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_cors()
        self.end_headers()

    # ── Routing ────────────────────────────────────────────────────────────────

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path   = parsed.path.rstrip('/')

        if path == '':
            self._redirect('/ui/projects.html')
        elif path == '/ui' or path.startswith('/ui/'):
            self._serve_ui(path)
        elif path == '/api/projects':
            self._api_projects_list()
        elif path == '/api/config':
            self._api_config_get()
        elif path == '/api/posts':
            self._api_posts_list()
        elif path.startswith('/api/posts/'):
            rest = path[len('/api/posts/'):]
            if rest.endswith('/staged'):
                self._api_staged_get(rest[:-len('/staged')])
            else:
                self._api_post_get(rest)
        elif path == '/api/ingest/status':
            with _job_lock:
                self._json(200, dict(_job))
        else:
            self._serve_static(parsed.path)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        params = dict(urllib.parse.parse_qsl(parsed.query))
        path   = parsed.path.rstrip('/')
        body   = self._read_body()

        if path == '/api/projects':
            self._api_projects_create(body)
        elif path.startswith('/api/projects/'):
            rest = path[len('/api/projects/'):]
            if rest.endswith('/activate'):
                self._api_projects_activate(rest[:-len('/activate')])
            elif rest.endswith('/ingest/run'):
                proj_id = rest[:-len('/ingest/run')]
                # Ingest into a specific project
                try:
                    data = json.loads(body) if body.strip() else {}
                except Exception:
                    data = {}
                self._api_ingest('run', json.dumps({**data, '_project_id': proj_id}))
            else:
                self._json(404, {'error': 'unknown project endpoint'})
        elif path == '/api/config':
            self._api_config_post(body)
        elif path.startswith('/api/posts/'):
            rest = path[len('/api/posts/'):]
            if rest.endswith('/generate-md'):
                dry = params.get('dry') == '1'
                self._api_generate_md(rest[:-len('/generate-md')], dry=dry)
            elif rest.endswith('/validate-md'):
                self._api_validate_md(rest[:-len('/validate-md')])
            elif rest.endswith('/scan'):
                self._api_scan_html(rest[:-len('/scan')])
            elif rest.endswith('/stage'):
                self._api_stage(rest[:-len('/stage')], body)
            elif rest.endswith('/save-md'):
                self._api_save_md(rest[:-len('/save-md')], body)
            elif rest.endswith('/accept-staged'):
                self._api_accept_staged(rest[:-len('/accept-staged')])
            elif rest.endswith('/reject-staged'):
                self._api_reject_staged(rest[:-len('/reject-staged')])
            else:
                self._json(404, {'error': 'unknown endpoint'})
        elif path == '/api/consolidate':
            self._api_consolidate()
        elif path.startswith('/api/ingest/'):
            action = path[len('/api/ingest/'):]
            self._api_ingest(action, body)
        else:
            self._json(404, {'error': 'unknown endpoint'})

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path   = parsed.path.rstrip('/')
        if path.startswith('/api/projects/'):
            project_id = path[len('/api/projects/'):]
            self._api_projects_delete(project_id)
        else:
            self._json(404, {'error': 'unknown endpoint'})

    def do_PATCH(self):
        parsed = urllib.parse.urlparse(self.path)
        path   = parsed.path.rstrip('/')
        body   = self._read_body()

        if path.startswith('/api/posts/'):
            slug = path[len('/api/posts/'):]
            self._api_post_patch(slug, body)
        else:
            self._json(404, {'error': 'unknown endpoint'})

    # ── API handlers ───────────────────────────────────────────────────────────

    # ── Projects API ───────────────────────────────────────────────────────────────

    def _api_projects_list(self):
        projects = _load_projects()
        result = []
        for p in projects:
            stats = _project_stats(p['id'])
            result.append({**p, 'stats': stats, 'active': p['id'] == _active_project_id})
        self._json(200, result)

    def _api_projects_create(self, body: str):
        try:
            data = json.loads(body)
        except Exception:
            self._json(400, {'error': 'invalid JSON'}); return
        name = (data.get('name') or '').strip()
        if not name:
            self._json(400, {'error': 'name required'}); return
        project_id = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')[:40]
        proj_dir   = _project_dir(project_id)
        proj_dir.mkdir(parents=True, exist_ok=True)
        project_cfg = {
            'project_name': name,
            'serve_root':   data.get('serve_root', str(ROOT.parent)),
            'source': {
                'posts_dir':  data.get('posts_dir',  'legacy/posts'),
                'assets_dir': data.get('assets_dir', 'legacy/assets'),
            },
            'output': {'md_dir': data.get('md_dir', 'output/md')},
            'filter': {'author': data.get('author_filter', '')},
            'server': {'port': cfg.get('server', {}).get('port', 9000)},
        }
        (proj_dir / 'config.json').write_text(json.dumps(project_cfg, indent=2))
        projects = _load_projects()
        if not any(p['id'] == project_id for p in projects):
            projects.append({'id': project_id, 'name': name,
                             'created_at': datetime.now().isoformat(timespec='seconds')})
            _save_projects(projects)
        self._json(200, {'id': project_id, 'name': name})

    def _api_projects_delete(self, project_id: str):
        projects = [p for p in _load_projects() if p['id'] != project_id]
        _save_projects(projects)
        # Data files are kept — only removed from index
        self._json(200, {'deleted': project_id})

    def _api_projects_activate(self, project_id: str):
        ok = _activate_project(project_id)
        if not ok:
            self._json(404, {'error': f'project not found: {project_id}'}); return
        self._json(200, {'active': project_id, 'name': cfg.get('project_name', project_id)})

    def _api_config_get(self):
        public = {k: v for k, v in cfg.items() if not k.startswith('_')}
        self._json(200, public)

    def _api_config_post(self, body: str):
        try:
            patch = json.loads(body)
        except json.JSONDecodeError:
            self._json(400, {'error': 'invalid JSON'})
            return
        cfg.update(patch)
        save_cfg(cfg)
        self._json(200, {'saved': True})

    def _api_posts_list(self):
        posts = State.get_all()
        # Sort by date then slug
        posts.sort(key=lambda p: (p.get('date', ''), p.get('slug', '')))
        self._json(200, posts)

    def _api_post_get(self, slug: str):
        post = State.get(slug)
        if post is None:
            self._json(404, {'error': f'unknown slug: {slug}'})
            return
        self._json(200, post)

    def _api_post_patch(self, slug: str, body: str):
        try:
            patch = json.loads(body)
        except json.JSONDecodeError:
            self._json(400, {'error': 'invalid JSON'})
            return
        # Only allow safe top-level fields
        allowed = {'flagged', 'user_note', 'reviewed'}
        safe = {k: v for k, v in patch.items() if k in allowed}
        State.update(slug, safe)
        self._json(200, State.get(slug))

    def _api_generate_md(self, slug: str, dry: bool = False):
        if not _can_generate:
            self._json(503, {'error': 'convert_post not available'})
            return
        html_path = POSTS_DIR / (slug + '.html')
        if not html_path.exists():
            self._json(404, {'error': f'HTML not found: {slug}'})
            return
        md_path = MD_DIR / (slug + '.md')
        try:
            content = convert_post(html_path)
            if dry:
                # Return generated content without writing anything
                print(f'Dry-run: {slug}.md')
                self._text(200, content)
                return
            md_path.write_text(content, encoding='utf-8')
            State.mark_md_generated(slug)
            if _can_validate:
                issues = validate_md(content, slug, html_path)
                State.set_md_issues(slug, [
                    {'check': i.check, 'level': i.level,
                     'detail': i.detail, 'selector': None}
                    for i in issues
                ])
            print(f'Generated: {slug}.md')
            self._json(200, State.get(slug))
        except Exception as e:
            self._json(500, {'error': str(e)})

    def _api_validate_md(self, slug: str):
        if not _can_validate:
            self._json(503, {'error': 'md_validator not available'})
            return
        md_path   = MD_DIR / (slug + '.md')
        html_path = POSTS_DIR / (slug + '.html')
        if not md_path.exists():
            self._json(404, {'error': 'MD not generated yet'})
            return
        content = md_path.read_text(errors='replace')
        issues  = validate_md(content, slug,
                              html_path if html_path.exists() else None)
        State.set_md_issues(slug, [
            {'check': i.check, 'level': i.level,
             'detail': i.detail, 'selector': None}
            for i in issues
        ])
        self._json(200, State.get(slug))

    def _api_scan_html(self, slug: str):
        """Scan a post for all issues — HTML content problems AND asset localisation."""
        html_path = POSTS_DIR / (slug + '.html')
        if not html_path.exists():
            self._json(404, {'error': f'HTML not found: {slug}'})
            return
        if not _can_scan:
            self._json(503, {'error': 'scan_html not available'})
            return
        try:
            # Content issues (XSS, missing images, empty embeds, WordPress chrome, etc.)
            raw_issues = _scan_post(html_path)
            issues = [
                {'type': i['type'], 'level': i['level'],
                 'check': i['type'],
                 'detail': i['detail'], 'selector': i.get('selector')}
                for i in raw_issues
            ]
            State.set_html_issues(slug, issues)

            # Asset localisation (images not yet downloaded, external src, etc.)
            if _can_scan_assets:
                from datetime import datetime, timezone
                asset_result = _scan_assets(html_path)
                State.update(slug, {'assets': {
                    'total':      asset_result['total'],
                    'localised':  asset_result['localised'],
                    'broken':     asset_result['broken'],
                    'checked_at': datetime.now(timezone.utc).isoformat(),
                }})

            errors = sum(1 for i in issues if i['level'] == 'ERROR')
            warns  = sum(1 for i in issues if i['level'] == 'WARN')
            print(f'Scanned: {slug} — {errors}E {warns}W html, '
                  f'{asset_result["broken"] if _can_scan_assets else "?"} asset issues')
            self._json(200, State.get(slug))
        except Exception as e:
            self._json(500, {'error': str(e)})

    def _api_save_md(self, slug: str, content: str):
        """Write manually-edited MD content directly to SLUG.md and re-validate."""
        md_path = MD_DIR / (slug + '.md')
        try:
            md_path.write_text(content, encoding='utf-8')
            # Mark as generated from current HTML hash (manual edit doesn't change staleness)
            State.mark_md_generated(slug)
            # Re-validate immediately
            html_path = POSTS_DIR / (slug + '.html')
            if _can_validate:
                issues = validate_md(content, slug,
                                     html_path if html_path.exists() else None)
                State.set_md_issues(slug, [
                    {'check': i.check, 'level': i.level,
                     'detail': i.detail, 'selector': None}
                    for i in issues
                ])
            print(f'Saved (manual edit): {slug}.md')
            self._json(200, State.get(slug))
        except Exception as e:
            self._json(500, {'error': str(e)})

    # ── Consolidation endpoint ────────────────────────────────────────────────────

    def _api_consolidate(self):
        """Run hash-based asset consolidation for the active project."""
        try:
            from consolidate import consolidate
            report = consolidate(ASSETS_ROOT, CLEANED_DIR)
            print(f'Consolidate: {report["promoted"]} promoted, '
                  f'{report["updated_html"]} HTML files updated')
            self._json(200, report)
        except Exception as e:
            self._json(500, {'error': str(e)})

    # ── Ingest endpoints ───────────────────────────────────────────────────────────

    def _api_ingest(self, action: str, body: str):
        if not _can_ingest:
            self._json(503, {'error': 'ingest not available — install requests library'})
            return
        import requests
        try:
            data = json.loads(body) if body.strip() else {}
        except json.JSONDecodeError:
            data = {}

        session = requests.Session()
        session.headers['User-Agent'] = (
            'Mozilla/5.0 (compatible; Sparge/1.0)')

        if action == 'detect':
            url = data.get('url', '')
            if not url:
                self._json(400, {'error': 'url required'}); return
            try:
                result = detect_platform(url, session)
                self._json(200, result)
            except Exception as e:
                self._json(500, {'error': str(e)})

        elif action == 'discover':
            url    = data.get('url', '')
            author = data.get('author_filter') or None
            if not url:
                self._json(400, {'error': 'url required'}); return
            try:
                platform_info = detect_platform(url, session)
                urls = discover_urls(platform_info['base_url'],
                                     platform_info['platform'], session, author)
                self._json(200, {**platform_info, 'urls': urls, 'count': len(urls)})
            except Exception as e:
                self._json(500, {'error': str(e)})

        elif action == 'preview':
            url = data.get('url', '')
            if not url:
                self._json(400, {'error': 'url required'}); return
            try:
                result = preview_post(url, session)
                self._json(200, result)
            except Exception as e:
                self._json(500, {'error': str(e)})

        elif action == 'run':
            urls   = data.get('urls', [])
            author = data.get('author_filter') or None
            if not urls:
                self._json(400, {'error': 'urls required'}); return
            with _job_lock:
                if _job['running']:
                    self._json(409, {'error': 'ingest already running'}); return
            t = threading.Thread(target=_ingest_worker,
                                 args=(urls, author), daemon=True)
            t.start()
            print(f'Ingest started: {len(urls)} URLs')
            self._json(200, {'started': True, 'total': len(urls)})

        elif action == 'cancel':
            with _job_lock:
                _job['cancelled'] = True
            self._json(200, {'cancelled': True})

        else:
            self._json(404, {'error': f'unknown ingest action: {action}'})

    # ── Staged workflow endpoints ──────────────────────────────────────────────────

    def _api_staged_get(self, slug: str):
        """Return the content of the staged MD file."""
        staged_path = MD_DIR / (slug + '.md.staged')
        if not staged_path.exists():
            self._json(404, {'error': 'no staged version'})
            return
        self._text(200, staged_path.read_text(encoding='utf-8'))

    def _api_stage(self, slug: str, content: str):
        """Write content to SLUG.md.staged and mark post as staged."""
        staged_path = MD_DIR / (slug + '.md.staged')
        try:
            staged_path.write_text(content, encoding='utf-8')
            state_stage(slug)
            print(f'Staged: {slug}')
            self._json(200, State.get(slug))
        except Exception as e:
            self._json(500, {'error': str(e)})

    def _api_accept_staged(self, slug: str):
        """Promote SLUG.md.staged → SLUG.md, run validation, update state."""
        ok = accept_staged(slug)
        if not ok:
            self._json(404, {'error': 'no staged version to accept'})
            return
        md_path   = MD_DIR / (slug + '.md')
        html_path = POSTS_DIR / (slug + '.html')
        if _can_validate and md_path.exists():
            content = md_path.read_text(errors='replace')
            issues  = validate_md(content, slug,
                                  html_path if html_path.exists() else None)
            State.set_md_issues(slug, [
                {'check': i.check, 'level': i.level,
                 'detail': i.detail, 'selector': None}
                for i in issues
            ])
        print(f'Accepted staged: {slug}')
        self._json(200, State.get(slug))

    def _api_reject_staged(self, slug: str):
        """Delete SLUG.md.staged, clear staged flag."""
        reject_staged(slug)
        print(f'Rejected staged: {slug}')
        self._json(200, State.get(slug))

    # ── Static file serving ────────────────────────────────────────────────────

    def _serve_ui(self, url_path: str):
        if url_path in ('/ui', '/ui/'):
            file_path = UI_DIR / 'projects.html'  # entry point is projects page
        else:
            rel = url_path[len('/ui/'):]
            file_path = UI_DIR / rel
        self._serve_file(file_path)

    def _serve_static(self, url_path: str):
        # Decode percent-encoding and strip leading slash
        rel = urllib.parse.unquote(url_path.lstrip('/'))
        self._serve_file(SERVE_ROOT / rel)

    def _serve_file(self, file_path: Path):
        try:
            file_path = file_path.resolve()
            data = file_path.read_bytes()
        except (FileNotFoundError, IsADirectoryError, PermissionError):
            self._json(404, {'error': str(file_path)})
            return
        mime = mimetypes.guess_type(str(file_path))[0] or 'application/octet-stream'
        self.send_response(200)
        self.send_cors()
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', len(data))
        self.end_headers()
        self.wfile.write(data)

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _redirect(self, location: str):
        self.send_response(302)
        self.send_header('Location', location)
        self.end_headers()

    def _json(self, code: int, data):
        payload = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_cors()
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(payload))
        self.end_headers()
        self.wfile.write(payload)

    def _read_body(self) -> str:
        length = int(self.headers.get('Content-Length', 0))
        return self.rfile.read(length).decode('utf-8')


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print('Initialising state from source posts…')
    added = State.init_from_source()
    print(f'  {added} new posts added to state')

    total = len(State.get_all())
    port  = cfg['server']['port']
    print(f'  {total} posts tracked')
    print(f'\nSparge running → http://localhost:{port}/ui/')
    print(f'Project: {cfg["project_name"]}')

    HTTPServer(('localhost', port), Handler).serve_forever()
