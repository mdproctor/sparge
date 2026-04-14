#!/usr/bin/env python3
"""
JEP bridge — thin wrappers over Sparge handler logic.

All public functions return JSON strings:
  {"status": int, "body": Any}
  {"status": int, "content_type": "text/plain", "body": str}  ← HTML/text endpoints
  {"status": int, "content_type": "text/html",  "body": str}  ← iframe view endpoint

Call bridge_init() once at JEP startup.
"""
from __future__ import annotations
import json
import re
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent  # sparge/
sys.path.insert(0, str(ROOT))  # add repo root so 'scripts' is importable as a package

from scripts.config import cfg, set_config_path, save as save_cfg
from scripts import state as State
from scripts.state import stage as state_stage, accept_staged, reject_staged, set_state_file
from scripts.sparge_home import get_projects_dir

# ── Global state (mirrors server.py) ─────────────────────────────────────────
PROJECTS_DIR  = get_projects_dir()
PROJECTS_FILE = PROJECTS_DIR / 'projects.json'
_active_project_id: str | None = None
POSTS_DIR:    Path = ROOT.parent / 'legacy' / 'posts'
MD_DIR:       Path = ROOT.parent / 'mark-proctor'
SERVE_ROOT:   Path = ROOT.parent
ENRICHED_DIR: Path = PROJECTS_DIR / '_default' / 'enriched'

# ── Feature flags ─────────────────────────────────────────────────────────────
_can_generate     = False; convert_post  = None
_can_validate     = False; validate_md   = None; refine_md = None
_can_scan         = False; _scan_post    = None
_can_scan_assets  = False; _scan_assets  = None
_can_enrich       = False; _enrich_post  = None
_can_ingest       = False
_can_consolidate  = False; _consolidate  = None

# ── Ingest job state ──────────────────────────────────────────────────────────
_job: dict = {
    'running': False, 'done': 0, 'total': 0,
    'current': '', 'errors': [], 'cancelled': False, 'log': [],
}
_job_lock = threading.Lock()


# ── Init ─────────────────────────────────────────────────────────────────────
def bridge_init() -> str:
    """Call once at JEP startup. Loads all optional modules, activates first project."""
    global _can_generate, convert_post
    global _can_validate, validate_md, refine_md
    global _can_scan, _scan_post
    global _can_scan_assets, _scan_assets
    global _can_enrich, _enrich_post
    global _can_ingest
    global _can_consolidate, _consolidate

    try:
        from scripts.convert_post import convert_post as _cp
        convert_post = _cp; _can_generate = True
    except ImportError:
        pass

    try:
        from scripts.md_validator import validate as _vm, refine as _rm
        validate_md = _vm; refine_md = _rm; _can_validate = True
    except ImportError:
        pass

    try:
        from scripts.scan_html import scan_post as _sp
        _scan_post = _sp; _can_scan = True
    except ImportError:
        pass

    try:
        from scripts.scan_assets import scan_assets as _sa
        _scan_assets = _sa; _can_scan_assets = True
    except ImportError:
        pass

    try:
        from scripts.enrich import enrich_post as _ep
        _enrich_post = _ep; _can_enrich = True
    except ImportError:
        pass

    try:
        import requests  # noqa: F401
        _can_ingest = True
    except ImportError:
        pass

    try:
        from scripts.consolidate import consolidate as _c
        _consolidate = _c; _can_consolidate = True
    except ImportError:
        pass

    startup_projects = _load_projects()
    if startup_projects:
        _activate_project(startup_projects[0]['id'])

    State.init_from_source()
    total = len(State.get_all())
    return _ok({
        'initialized': True, 'posts': total,
        'can_generate': _can_generate, 'can_validate': _can_validate,
        'can_scan': _can_scan, 'can_ingest': _can_ingest,
    })


# ── Response helpers ──────────────────────────────────────────────────────────
def _ok(body) -> str:
    return json.dumps({'status': 200, 'body': body}, ensure_ascii=False)

def _text(content: str) -> str:
    return json.dumps({'status': 200, 'content_type': 'text/plain', 'body': content},
                      ensure_ascii=False)

def _err(status: int, msg: str) -> str:
    return json.dumps({'status': status, 'body': {'error': msg}}, ensure_ascii=False)


# ── Projects helpers ──────────────────────────────────────────────────────────
def _load_projects() -> list[dict]:
    if PROJECTS_FILE.exists():
        return json.loads(PROJECTS_FILE.read_text())
    return []

def _save_projects(projects: list[dict]) -> None:
    PROJECTS_FILE.write_text(json.dumps(projects, indent=2))

def _project_dir(project_id: str) -> Path:
    return PROJECTS_DIR / project_id

def _activate_project(project_id: str) -> bool:
    global _active_project_id, POSTS_DIR, MD_DIR, SERVE_ROOT, ENRICHED_DIR
    proj_dir    = _project_dir(project_id)
    config_path = proj_dir / 'config.json'
    state_path  = proj_dir / 'state.json'
    if not config_path.exists():
        return False
    set_config_path(config_path)
    set_state_file(state_path)
    POSTS_DIR    = Path(cfg['_posts_dir'])
    MD_DIR       = Path(cfg['_md_dir'])
    SERVE_ROOT   = Path(cfg['_root'])
    ENRICHED_DIR = proj_dir / 'enriched'
    ENRICHED_DIR.mkdir(exist_ok=True)
    _active_project_id = project_id
    State.init_from_source()
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
            if entry.get('reviewed'):                           stats['reviewed']     += 1
            if entry.get('md', {}).get('staged'):              stats['staged']       += 1
            if entry.get('md', {}).get('generated_at'):        stats['md_generated'] += 1
            if (entry.get('html', {}).get('issues') or []):    stats['html_issues']  += 1
    except Exception:
        pass
    return stats


# ── Projects API ──────────────────────────────────────────────────────────────
def projects_list() -> str:
    projects = _load_projects()
    result = []
    for p in projects:
        stats = _project_stats(p['id'])
        result.append({**p, 'stats': stats, 'active': p['id'] == _active_project_id})
    return _ok(result)

def projects_create(body: str) -> str:
    try:
        data = json.loads(body)
    except Exception:
        return _err(400, 'invalid JSON')
    name = (data.get('name') or '').strip()
    if not name:
        return _err(400, 'name required')
    project_id = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')[:40]
    proj_dir   = _project_dir(project_id)
    proj_dir.mkdir(parents=True, exist_ok=True)
    project_cfg = {
        'project_name': name,
        'serve_root':   data.get('serve_root', str(Path.home())),
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
    return _ok({'id': project_id, 'name': name})

def projects_delete(project_id: str) -> str:
    projects = [p for p in _load_projects() if p['id'] != project_id]
    _save_projects(projects)
    return _ok({'deleted': project_id})

def projects_activate(project_id: str) -> str:
    ok = _activate_project(project_id)
    if not ok:
        return _err(404, f'project not found: {project_id}')
    return _ok({'active': project_id, 'name': cfg.get('project_name', project_id)})

def project_ingest_run(project_id: str, body: str) -> str:
    """Activate project then start ingest run."""
    ok = _activate_project(project_id)
    if not ok:
        return _err(404, f'project not found: {project_id}')
    return ingest_run(body)


# ── Config API ────────────────────────────────────────────────────────────────
def config_get() -> str:
    public = {k: v for k, v in cfg.items() if not k.startswith('_')}
    return _ok(public)

def config_post(body: str) -> str:
    try:
        patch = json.loads(body)
    except json.JSONDecodeError:
        return _err(400, 'invalid JSON')
    cfg.update(patch)
    save_cfg(cfg)
    return _ok({'saved': True})


# ── Search API ────────────────────────────────────────────────────────────────
def search(q: str, scope: str) -> str:
    q = q.strip().lower()
    if not q:
        return _ok({'slugs': [p['slug'] for p in State.get_all()]})
    results = []
    for p in State.get_all():
        slug  = p.get('slug', '')
        title = (p.get('title', '') or '').lower()
        in_title = scope in ('title', 'both') and q in title
        in_body  = False
        if scope in ('body', 'both') and not in_title:
            md_path = MD_DIR / (slug + '.md')
            if md_path.exists():
                try:
                    content = md_path.read_text(encoding='utf-8', errors='replace').lower()
                    in_body = q in content
                except Exception:
                    pass
        if in_title or in_body:
            results.append(slug)
    return _ok({'slugs': results})


# ── Posts CRUD ────────────────────────────────────────────────────────────────
def posts_list(author: str | None = None) -> str:
    posts = State.get_all()
    effective = author if author is not None else cfg.get('filter', {}).get('author', '')
    if effective:
        posts = [p for p in posts if p.get('author', '') == effective]
    posts.sort(key=lambda p: (p.get('date', ''), p.get('slug', '')))
    return _ok(posts)

def post_get(slug: str) -> str:
    post = State.get(slug)
    if post is None:
        return _err(404, f'unknown slug: {slug}')
    return _ok(post)

def post_patch(slug: str, body: str) -> str:
    try:
        patch = json.loads(body)
    except json.JSONDecodeError:
        return _err(400, 'invalid JSON')
    allowed = {'flagged', 'user_note', 'reviewed'}
    safe = {k: v for k, v in patch.items() if k in allowed}
    State.update(slug, safe)
    return _ok(State.get(slug))


# ── Posts HTML ────────────────────────────────────────────────────────────────
def post_html(slug: str) -> str:
    """Return prettified HTML for editor (text/plain)."""
    enriched = ENRICHED_DIR / (slug + '.html')
    original = POSTS_DIR   / (slug + '.html')
    html_path = enriched if enriched.exists() else original
    if not html_path.exists():
        return _err(404, f'HTML not found: {slug}')
    try:
        raw = html_path.read_text(encoding='utf-8', errors='replace')
        from scripts.html_utils import prettify_html as _prettify_html
        content = _prettify_html(raw)
        if 'ÃÂÃÂ' in content or ('\xc3\x82' in content):
            content = raw
        return _text(content)
    except Exception as e:
        return _err(500, str(e))

def post_view(slug: str) -> str:
    """Return raw HTML for iframe rendering (text/html)."""
    enriched = ENRICHED_DIR / (slug + '.html')
    original = POSTS_DIR   / (slug + '.html')
    html_path = enriched if enriched.exists() else original
    if not html_path.exists():
        return _err(404, f'HTML not found: {slug}')
    try:
        content = html_path.read_text(encoding='utf-8', errors='replace')
        content = re.sub(
            r'<header\s[^>]*class="[^"]*archive-header[^"]*"[^>]*>.*?</header>',
            '', content, flags=re.DOTALL | re.IGNORECASE)
        return json.dumps({'status': 200, 'content_type': 'text/html', 'body': content},
                          ensure_ascii=False)
    except Exception as e:
        return _err(500, str(e))

def post_save_html(slug: str, content: str) -> str:
    ENRICHED_DIR.mkdir(parents=True, exist_ok=True)
    html_path = ENRICHED_DIR / (slug + '.html')
    try:
        html_path.write_text(content, encoding='utf-8')
        return _ok(State.get(slug))
    except Exception as e:
        return _err(500, str(e))


# ── Posts MD ──────────────────────────────────────────────────────────────────
def post_generate_md(slug: str, dry: bool = False) -> str:
    if not _can_generate:
        return _err(503, 'convert_post not available')
    enriched_path = ENRICHED_DIR / (slug + '.html')
    html_path = enriched_path if enriched_path.exists() else POSTS_DIR / (slug + '.html')
    if not html_path.exists():
        return _err(404, f'HTML not found: {slug}')
    json_path = POSTS_DIR / (slug + '.json')
    if not json_path.exists():
        json_path = None
    md_path = MD_DIR / (slug + '.md')
    try:
        content = convert_post(html_path, json_path=json_path)
        if dry:
            return _ok({'content': content})
        md_path.write_text(content, encoding='utf-8')
        State.mark_md_generated(slug)
        if _can_validate:
            issues = validate_md(content, slug, html_path)
            State.set_md_issues(slug, [
                {'check': i.check, 'level': i.level, 'detail': i.detail, 'selector': None}
                for i in issues
            ])
            if refine_md:
                suggestions = refine_md(content, slug, html_path)
                State.update(slug, {'md_suggestions': [
                    {'check': s.check, 'level': s.level, 'detail': s.detail}
                    for s in suggestions
                ]})
        return _ok(State.get(slug))
    except Exception as e:
        return _err(500, str(e))

def post_validate_md(slug: str) -> str:
    if not _can_validate:
        return _err(503, 'md_validator not available')
    md_path       = MD_DIR / (slug + '.md')
    enriched_path = ENRICHED_DIR / (slug + '.html')
    html_path     = enriched_path if enriched_path.exists() else POSTS_DIR / (slug + '.html')
    if not md_path.exists():
        return _err(404, 'MD not generated yet')
    try:
        content  = md_path.read_text(errors='replace')
        html_arg = html_path if html_path.exists() else None
        issues   = validate_md(content, slug, html_arg)
        State.set_md_issues(slug, [
            {'check': i.check, 'level': i.level, 'detail': i.detail, 'selector': None}
            for i in issues
        ])
        if refine_md:
            suggestions = refine_md(content, slug, html_arg)
            State.update(slug, {'md_suggestions': [
                {'check': s.check, 'level': s.level, 'detail': s.detail}
                for s in suggestions
            ]})
        return _ok(State.get(slug))
    except Exception as e:
        return _err(500, str(e))

def post_save_md(slug: str, content: str) -> str:
    md_path = MD_DIR / (slug + '.md')
    try:
        md_path.write_text(content, encoding='utf-8')
        State.mark_md_generated(slug)
        html_path = POSTS_DIR / (slug + '.html')
        if _can_validate:
            issues = validate_md(content, slug, html_path if html_path.exists() else None)
            State.set_md_issues(slug, [
                {'check': i.check, 'level': i.level, 'detail': i.detail, 'selector': None}
                for i in issues
            ])
        return _ok(State.get(slug))
    except Exception as e:
        return _err(500, str(e))


# ── Staged workflow ───────────────────────────────────────────────────────────
def post_staged_get(slug: str) -> str:
    staged_path = MD_DIR / (slug + '.md.staged')
    if not staged_path.exists():
        return _err(404, 'no staged version')
    try:
        return _text(staged_path.read_text(encoding='utf-8'))
    except Exception as e:
        return _err(500, str(e))

def post_stage(slug: str, content: str) -> str:
    staged_path = MD_DIR / (slug + '.md.staged')
    try:
        staged_path.write_text(content, encoding='utf-8')
        state_stage(slug)
        return _ok(State.get(slug))
    except Exception as e:
        return _err(500, str(e))

def post_accept_staged(slug: str) -> str:
    ok = accept_staged(slug)
    if not ok:
        return _err(404, 'no staged version to accept')
    try:
        md_path   = MD_DIR / (slug + '.md')
        html_path = POSTS_DIR / (slug + '.html')
        if _can_validate and md_path.exists():
            content = md_path.read_text(errors='replace')
            issues  = validate_md(content, slug, html_path if html_path.exists() else None)
            State.set_md_issues(slug, [
                {'check': i.check, 'level': i.level, 'detail': i.detail, 'selector': None}
                for i in issues
            ])
        return _ok(State.get(slug))
    except Exception as e:
        return _err(500, str(e))

def post_reject_staged(slug: str) -> str:
    reject_staged(slug)
    return _ok(State.get(slug))


# ── HTML issue dismiss ────────────────────────────────────────────────────────
def post_dismiss_html_check(slug: str, body: str) -> str:
    try:
        data = json.loads(body)
        issue_type = data.get('type', '')
        if not issue_type:
            return _err(400, 'type required')
        State.dismiss_html_check(slug, issue_type)
        return _ok(State.get(slug))
    except Exception as e:
        return _err(400, str(e))

def post_undismiss_html_check(slug: str, issue_type: str) -> str:
    State.undismiss_html_check(slug, issue_type)
    return post_scan_html(slug)  # rescan immediately, returns full state


# ── Scan HTML + assets ────────────────────────────────────────────────────────
def post_scan_html(slug: str) -> str:
    html_path = POSTS_DIR / (slug + '.html')
    if not html_path.exists():
        return _err(404, f'HTML not found: {slug}')
    if not _can_scan:
        return _err(503, 'scan_html not available')
    try:
        enriched_path = ENRICHED_DIR / (slug + '.html')

        if _can_enrich and not enriched_path.exists():
            github_token = cfg.get('github_token', '')
            enrich_stats = _enrich_post(
                html_path, enriched_path, cfg['_assets_dir'], github_token)
            State.mark_enriched(slug, enrich_stats)

        if enriched_path.exists() and _can_generate:
            try:
                from bs4 import BeautifulSoup as _BS
                from scripts.fix_code_blocks import apply_code_block_fixes as _fix_blocks
                _soup = _BS(enriched_path.read_text(encoding='utf-8', errors='replace'),
                            'html.parser')
                _article = _soup.find('article') or _soup.find('body') or _soup
                for _pre in _article.find_all('pre'):
                    for _br in _pre.find_all('br'):
                        _br.replace_with('\n')
                if _fix_blocks(_soup):
                    enriched_path.write_text(str(_soup), encoding='utf-8')
            except Exception:
                pass

        scan_path = enriched_path if enriched_path.exists() else html_path
        raw_issues = _scan_post(scan_path, posts_dir=POSTS_DIR)
        issues = [
            {'type': i['type'], 'level': i['level'], 'check': i['type'],
             'detail': i['detail'], 'selector': i.get('selector')}
            for i in raw_issues
        ]
        State.set_html_issues(slug, issues)

        if _can_scan_assets:
            asset_result = _scan_assets(scan_path, original_path=html_path)
            State.update(slug, {'assets': {
                'total':      asset_result['total'],
                'localised':  asset_result['localised'],
                'broken':     asset_result['broken'],
                'checked_at': datetime.now(timezone.utc).isoformat(),
            }})

        return _ok(State.get(slug))
    except Exception as e:
        return _err(500, str(e))


# ── Ingest ────────────────────────────────────────────────────────────────────
def _ingest_worker(urls: list, author_filter: str | None) -> None:
    try:
        import requests
        from scripts.ingest import ingest_post
    except ImportError as e:
        with _job_lock:
            _job['running'] = False
            _job['errors'].append({'url': '', 'error': f'import error: {e}'})
        return
    session = requests.Session()
    session.headers['User-Agent'] = 'Mozilla/5.0 (compatible; BlogMigrator/1.0)'
    with _job_lock:
        _job.update({'running': True, 'done': 0, 'total': len(urls),
                     'errors': [], 'cancelled': False, 'log': []})
    for url in urls:
        with _job_lock:
            if _job['cancelled']:
                break
            _job['current'] = url
        try:
            result = ingest_post(url, session, POSTS_DIR, SERVE_ROOT)
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
    State.init_from_source()
    with _job_lock:
        _job['running'] = False
        _job['current'] = ''

def ingest_detect(body: str) -> str:
    if not _can_ingest:
        return _err(503, 'ingest not available — install requests library')
    import requests
    from scripts.ingest import detect_platform
    try:
        data = json.loads(body) if body.strip() else {}
    except json.JSONDecodeError:
        data = {}
    url = data.get('url', '')
    if not url:
        return _err(400, 'url required')
    session = requests.Session()
    session.headers['User-Agent'] = 'Mozilla/5.0 (compatible; BlogMigrator/1.0)'
    try:
        return _ok(detect_platform(url, session))
    except Exception as e:
        return _err(500, str(e))

def ingest_discover(body: str) -> str:
    if not _can_ingest:
        return _err(503, 'ingest not available — install requests library')
    import requests
    from scripts.ingest import detect_platform, discover_urls
    try:
        data = json.loads(body) if body.strip() else {}
    except json.JSONDecodeError:
        data = {}
    url    = data.get('url', '')
    author = data.get('author_filter') or None
    if not url:
        return _err(400, 'url required')
    session = requests.Session()
    session.headers['User-Agent'] = 'Mozilla/5.0 (compatible; BlogMigrator/1.0)'
    try:
        platform_info = detect_platform(url, session)
        urls = discover_urls(platform_info['base_url'], platform_info['platform'],
                             session, author)
        return _ok({**platform_info, 'urls': urls, 'count': len(urls)})
    except Exception as e:
        return _err(500, str(e))

def ingest_preview(body: str) -> str:
    if not _can_ingest:
        return _err(503, 'ingest not available — install requests library')
    import requests
    from scripts.ingest import preview_post
    try:
        data = json.loads(body) if body.strip() else {}
    except json.JSONDecodeError:
        data = {}
    url = data.get('url', '')
    if not url:
        return _err(400, 'url required')
    session = requests.Session()
    session.headers['User-Agent'] = 'Mozilla/5.0 (compatible; BlogMigrator/1.0)'
    try:
        return _ok(preview_post(url, session))
    except Exception as e:
        return _err(500, str(e))

def ingest_run(body: str) -> str:
    if not _can_ingest:
        return _err(503, 'ingest not available — install requests library')
    try:
        data = json.loads(body) if body.strip() else {}
    except json.JSONDecodeError:
        data = {}
    urls   = data.get('urls', [])
    author = data.get('author_filter') or None
    if not urls:
        return _err(400, 'urls required')
    with _job_lock:
        if _job['running']:
            return _err(409, 'ingest already running')
    t = threading.Thread(target=_ingest_worker, args=(urls, author), daemon=True)
    t.start()
    return _ok({'started': True, 'total': len(urls)})

def ingest_cancel() -> str:
    with _job_lock:
        _job['cancelled'] = True
    return _ok({'cancelled': True})

def ingest_status() -> str:
    with _job_lock:
        return _ok(dict(_job))


# ── Consolidate ───────────────────────────────────────────────────────────────
def consolidate() -> str:
    if not _can_consolidate:
        return _err(503, 'consolidate not available')
    if not _active_project_id:
        return _err(400, 'no active project')
    assets_root = cfg.get('_assets_dir')
    cleaned_dir = cfg.get('_posts_dir')
    if not assets_root or not cleaned_dir:
        return _err(400, 'project paths not configured')
    try:
        result = _consolidate(assets_root, cleaned_dir)
        return _ok(result)
    except Exception as e:
        return _err(500, str(e))


# ── Static file resolution ────────────────────────────────────────────────────
def static_resolve(url_path: str) -> str:
    """Resolve a URL path to an absolute filesystem path.

    Returns {"status": 200, "file_path": "..."} or {"status": 404, ...}.
    Java reads the file bytes and sets the MIME type itself.
    """
    import urllib.parse
    rel = urllib.parse.unquote(url_path.lstrip('/'))
    file_path = SERVE_ROOT / rel
    try:
        resolved = file_path.resolve()
        # Guard against path traversal
        if not str(resolved).startswith(str(SERVE_ROOT.resolve())):
            return _err(403, 'path outside serve root')
        if not resolved.exists():
            return _err(404, str(resolved))
        return json.dumps({'status': 200, 'file_path': str(resolved)}, ensure_ascii=False)
    except Exception as e:
        return _err(500, str(e))
