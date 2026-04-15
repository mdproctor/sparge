# Quarkus Migration Phase 0 — JEP Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Electron talks to Quarkus; Python runs in-process via JEP. No modules ported — pure HTTP translation layer bridging to existing Python logic.

**Architecture:** `scripts/bridge.py` exposes all server handler logic as JSON-returning functions; `server/` Quarkus Maven project calls them via `PythonBridge` (JEP `SharedInterpreter` singleton); `java-server.js` mirrors `python-server.js` state machine but spawns `java -jar`; `main.js` uses `SPARGE_SERVER=java` env var to choose server. Done when all existing pytest integration tests pass against the Quarkus server.

**Tech Stack:** Quarkus 3.15.x, RESTEasy Reactive + Jackson, JEP 4.2.0, Java 21, Maven 3.9+

---

## File Map

**New files:**
- `scripts/bridge.py` — Python bridge: all handler logic as JSON-returning functions
- `server/pom.xml` — Quarkus Maven project (JEP + RESTEasy Reactive + Jackson)
- `server/src/main/resources/application.properties` — port, CORS, logging config
- `server/src/main/java/io/sparge/server/PythonBridge.java` — `@ApplicationScoped` JEP singleton
- `server/src/main/java/io/sparge/server/BridgeResponse.java` — JSON→JAX-RS Response helper
- `server/src/main/java/io/sparge/server/ProjectsResource.java` — projects + config + search
- `server/src/main/java/io/sparge/server/PostsResource.java` — posts CRUD + HTML + view + MD + staged + scan + dismiss
- `server/src/main/java/io/sparge/server/IngestResource.java` — ingest + consolidate
- `server/src/main/java/io/sparge/server/StaticResource.java` — blog assets + UI serving + root redirect
- `server/src/test/java/io/sparge/server/SmokeTest.java` — `@QuarkusTest` ping on `/api/config`
- `java-server.js` — mirrors `python-server.js` but spawns JVM process

**Modified files:**
- `server.py:128` — fix hardcoded `kie-mark-proctor` fallback in `ENRICHED_DIR`
- `main.js` — add `SPARGE_SERVER=java` toggle

---

## Task 1: Pre-req — Fix ENRICHED_DIR hardcoded fallback

**Files:**
- Modify: `server.py:128`

- [ ] **Step 1: Read the line**

Open `server.py` and find line 128:
```python
ENRICHED_DIR: Path = PROJECTS_DIR / 'kie-mark-proctor' / 'enriched'
```

- [ ] **Step 2: Replace with generic fallback**

```python
ENRICHED_DIR: Path = PROJECTS_DIR / '_default' / 'enriched'
```

`_default` won't exist, so `enriched_path.exists()` returns False and callers fall back to the original HTML — safe behaviour when no project is active.

- [ ] **Step 3: Verify tests still pass**

```bash
cd ~/claude/sparge && python3 -m pytest tests/ -q
```
Expected: 473 passing, 0 failing.

- [ ] **Step 4: Commit**

```bash
cd ~/claude/sparge
git add server.py
git commit -m "fix: remove hardcoded kie-mark-proctor from ENRICHED_DIR fallback

Refs #51"
```

---

## Task 2: Install JEP native library via bundled Python

JEP needs a native library (`libjep.dylib` on macOS) compiled against the exact Python version we're using. Installing via the bundled pip creates the right binary automatically.

**Files:** none modified — this is environment setup only.

- [ ] **Step 1: Install JEP via bundled pip**

```bash
cd ~/claude/sparge
resources/python/mac-arm64/bin/pip install jep
```

Expected output ends with: `Successfully installed jep-4.2.0` (or later).

- [ ] **Step 2: Locate the native library**

```bash
find resources/python/mac-arm64 -name "libjep*" 2>/dev/null
```

Expected: `resources/python/mac-arm64/lib/python3.12/site-packages/jep/libjep.dylib`

Record this path — it goes in `java.library.path` when running the server.

- [ ] **Step 3: Verify Python 3.12 dylib is present**

```bash
ls resources/python/mac-arm64/lib/libpython3.12.dylib
```

Expected: file exists (already confirmed in design spec, just double-checking).

- [ ] **Step 4: Note runtime env var**

When running Quarkus (dev mode or jar), two env vars are required:
```bash
export DYLD_LIBRARY_PATH=~/claude/sparge/resources/python/mac-arm64/lib:$DYLD_LIBRARY_PATH
# JVM arg: -Djava.library.path=~/claude/sparge/resources/python/mac-arm64/lib/python3.12/site-packages/jep
```

These will be baked into `java-server.js` in Task 14 and the Quarkus Maven plugin in Task 4.

---

## Task 3: Create scripts/bridge.py

All Python handler logic extracted from `server.py` into importable functions. Each function returns a JSON string `{"status": int, "body": Any}` (or `{"status": int, "content_type": "text/plain", "body": str}` for HTML/text endpoints). This lets Java parse status + body without complex JEP type marshaling.

**Files:**
- Create: `scripts/bridge.py`

- [ ] **Step 1: Write bridge.py**

```python
#!/usr/bin/env python3
"""
JEP bridge — thin wrappers over Sparge handler logic.

All public functions return JSON strings:
  {"status": int, "body": Any}
  {"status": int, "content_type": "text/plain", "body": str}  ← HTML/text endpoints

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
sys.path.insert(0, str(ROOT / 'scripts'))

from config import cfg, set_config_path, save as save_cfg
import state as State
from state import stage as state_stage, accept_staged, reject_staged, set_state_file
from sparge_home import get_projects_dir

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
        from convert_post import convert_post as _cp
        convert_post = _cp; _can_generate = True
    except ImportError:
        pass

    try:
        from md_validator import validate as _vm, refine as _rm
        validate_md = _vm; refine_md = _rm; _can_validate = True
    except ImportError:
        pass

    try:
        from scan_html import scan_post as _sp
        _scan_post = _sp; _can_scan = True
    except ImportError:
        pass

    try:
        from scan_assets import scan_assets as _sa
        _scan_assets = _sa; _can_scan_assets = True
    except ImportError:
        pass

    try:
        from enrich import enrich_post as _ep
        _enrich_post = _ep; _can_enrich = True
    except ImportError:
        pass

    try:
        import requests  # noqa: F401
        _can_ingest = True
    except ImportError:
        pass

    try:
        from consolidate import consolidate as _c
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
        from html_utils import prettify_html as _prettify_html
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
    return _text(staged_path.read_text(encoding='utf-8'))

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
                from fix_code_blocks import apply_code_block_fixes as _fix_blocks
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
    import requests
    from ingest import ingest_post
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
    from ingest import detect_platform
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
    from ingest import detect_platform, discover_urls
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
    from ingest import preview_post
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


# ── Static file resolution (Java reads the file; bridge just resolves the path) ─
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
        if not resolved.exists():
            return _err(404, str(resolved))
        return json.dumps({'status': 200, 'file_path': str(resolved)}, ensure_ascii=False)
    except Exception as e:
        return _err(500, str(e))
```

- [ ] **Step 2: Smoke-test bridge.py standalone (outside JEP)**

```bash
cd ~/claude/sparge
python3 -c "
import sys; sys.path.insert(0, 'scripts')
import bridge
print(bridge.bridge_init())
print(bridge.config_get())
print(bridge.projects_list())
"
```

Expected: JSON output for each call, `"initialized": true`, 577 posts, no exceptions.

- [ ] **Step 3: Commit**

```bash
git add scripts/bridge.py
git commit -m "feat(#51): add scripts/bridge.py — JEP-facing Python handler wrappers"
```

---

## Task 4: Scaffold Quarkus Maven project

**Files:**
- Create: `server/pom.xml`
- Create: `server/src/main/resources/application.properties`
- Create directory structure

- [ ] **Step 1: Create directory structure**

```bash
cd ~/claude/sparge
mkdir -p server/src/main/java/io/sparge/server
mkdir -p server/src/main/resources
mkdir -p server/src/test/java/io/sparge/server
```

- [ ] **Step 2: Write server/pom.xml**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>

  <groupId>io.sparge</groupId>
  <artifactId>sparge-server</artifactId>
  <version>1.0.0-SNAPSHOT</version>

  <properties>
    <quarkus.platform.group-id>io.quarkus.platform</quarkus.platform.group-id>
    <quarkus.platform.artifact-id>quarkus-bom</quarkus.platform.artifact-id>
    <quarkus.platform.version>3.15.0.Final</quarkus.platform.version>
    <maven.compiler.release>21</maven.compiler.release>
    <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
    <jep.version>4.2.0</jep.version>
    <!-- Path to libjep.dylib — override per platform -->
    <jep.library.path>${project.basedir}/../resources/python/mac-arm64/lib/python3.12/site-packages/jep</jep.library.path>
  </properties>

  <dependencyManagement>
    <dependencies>
      <dependency>
        <groupId>${quarkus.platform.group-id}</groupId>
        <artifactId>${quarkus.platform.artifact-id}</artifactId>
        <version>${quarkus.platform.version}</version>
        <type>pom</type>
        <scope>import</scope>
      </dependency>
    </dependencies>
  </dependencyManagement>

  <dependencies>
    <dependency>
      <groupId>io.quarkus</groupId>
      <artifactId>quarkus-resteasy-reactive-jackson</artifactId>
    </dependency>
    <dependency>
      <groupId>io.quarkus</groupId>
      <artifactId>quarkus-arc</artifactId>
    </dependency>
    <!-- JEP: Java Embedded Python -->
    <dependency>
      <groupId>black.ninia</groupId>
      <artifactId>jep</artifactId>
      <version>${jep.version}</version>
    </dependency>
    <!-- Test -->
    <dependency>
      <groupId>io.quarkus</groupId>
      <artifactId>quarkus-junit5</artifactId>
      <scope>test</scope>
    </dependency>
    <dependency>
      <groupId>io.rest-assured</groupId>
      <artifactId>rest-assured</artifactId>
      <scope>test</scope>
    </dependency>
  </dependencies>

  <build>
    <plugins>
      <plugin>
        <groupId>${quarkus.platform.group-id}</groupId>
        <artifactId>quarkus-maven-plugin</artifactId>
        <version>${quarkus.platform.version}</version>
        <extensions>true</extensions>
        <executions>
          <execution>
            <goals>
              <goal>build</goal>
              <goal>generate-code</goal>
              <goal>generate-code-tests</goal>
            </goals>
          </execution>
        </executions>
      </plugin>
      <plugin>
        <artifactId>maven-compiler-plugin</artifactId>
        <version>3.13.0</version>
      </plugin>
      <plugin>
        <artifactId>maven-surefire-plugin</artifactId>
        <version>3.3.1</version>
        <configuration>
          <systemPropertyVariables>
            <java.library.path>${jep.library.path}</java.library.path>
          </systemPropertyVariables>
        </configuration>
      </plugin>
    </plugins>
  </build>
</project>
```

- [ ] **Step 3: Write application.properties**

```properties
# server/src/main/resources/application.properties
quarkus.http.port=9001
quarkus.http.cors=true
quarkus.http.cors.origins=*
quarkus.http.cors.methods=GET,POST,PATCH,DELETE,OPTIONS

# Dev mode logging
%dev.quarkus.log.level=INFO
%dev.quarkus.log.category."io.sparge".level=DEBUG
```

Port 9001 is the dev default. At runtime, `java-server.js` passes `-Dquarkus.http.port={port}` to override.

- [ ] **Step 4: Verify Maven can parse the POM**

```bash
cd ~/claude/sparge/server
mvn validate 2>&1 | tail -5
```

Expected: `BUILD SUCCESS`

- [ ] **Step 5: Commit**

```bash
cd ~/claude/sparge
git add server/pom.xml server/src/main/resources/application.properties
git commit -m "feat(#51): scaffold Quarkus Maven project at server/"
```

---

## Task 5: PythonBridge @ApplicationScoped bean

The single JEP `SharedInterpreter` lives here. All JAX-RS resources inject it. `call()` is synchronized — serializes Python access, matching Python's own GIL behavior.

**Files:**
- Create: `server/src/main/java/io/sparge/server/PythonBridge.java`
- Create: `server/src/main/java/io/sparge/server/BridgeResponse.java`

- [ ] **Step 1: Write PythonBridge.java**

```java
package io.sparge.server;

import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import jakarta.enterprise.context.ApplicationScoped;
import jep.JepException;
import jep.SharedInterpreter;

import java.nio.file.Path;
import java.nio.file.Paths;

@ApplicationScoped
public class PythonBridge {

    private SharedInterpreter interp;
    private final String scriptsPath;
    private final String repoRootPath;

    public PythonBridge() {
        // server/ is CWD when Quarkus runs from server/; parent is repo root
        Path serverDir = Paths.get(System.getProperty("user.dir")).toAbsolutePath();
        Path repoRoot  = serverDir.getParent();
        this.repoRootPath = repoRoot.toString();
        this.scriptsPath  = repoRoot.resolve("scripts").toString();
    }

    @PostConstruct
    void init() {
        try {
            interp = new SharedInterpreter();
            interp.exec("import sys");
            // Add repo root first (bridge.py lives in scripts/ which imports from scripts/)
            interp.exec("sys.path.insert(0, '" + escape(scriptsPath)  + "')");
            interp.exec("sys.path.insert(0, '" + escape(repoRootPath) + "')");
            interp.exec("import bridge");
            String result = (String) interp.invoke("bridge.bridge_init");
            System.out.println("[PythonBridge] initialized: " + result);
        } catch (JepException e) {
            throw new RuntimeException("PythonBridge init failed: " + e.getMessage(), e);
        }
    }

    @PreDestroy
    void destroy() {
        if (interp != null) {
            try { interp.close(); } catch (JepException ignored) {}
        }
    }

    /**
     * Call a bridge function, return its raw JSON string.
     * All calls are synchronized — Python's GIL is respected.
     */
    public synchronized String call(String function, Object... args) {
        try {
            return (String) interp.invoke(function, args);
        } catch (JepException e) {
            String msg = e.getMessage() == null ? "JEP error" : e.getMessage()
                .replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n");
            return "{\"status\":500,\"body\":{\"error\":\"" + msg + "\"}}";
        }
    }

    private static String escape(String path) {
        return path.replace("\\", "/");
    }
}
```

- [ ] **Step 2: Write BridgeResponse.java**

BridgeResponse converts the `{"status":int,"body":Any}` JSON from bridge.py into a JAX-RS `Response`.

```java
package io.sparge.server;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.ws.rs.core.Response;

public final class BridgeResponse {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    private BridgeResponse() {}

    /**
     * Parse bridge JSON and produce the appropriate JAX-RS Response.
     *
     * bridge returns one of:
     *   {"status":int, "body": jsonValue}           → application/json
     *   {"status":int, "content_type":"text/plain", "body":"string"}  → text/plain
     *   {"status":int, "content_type":"text/html",  "body":"string"}  → text/html
     */
    public static Response of(String bridgeJson) {
        try {
            JsonNode node = MAPPER.readTree(bridgeJson);
            int    status      = node.get("status").asInt();
            String contentType = node.has("content_type")
                ? node.get("content_type").asText() + "; charset=utf-8"
                : "application/json; charset=utf-8";

            JsonNode bodyNode = node.get("body");
            String   body     = bodyNode.isTextual()
                ? bodyNode.asText()       // text/plain or text/html
                : bodyNode.toString();    // JSON — serialize back

            return Response.status(status)
                .header("Content-Type",              contentType)
                .header("Access-Control-Allow-Origin", "*")
                .entity(body)
                .build();
        } catch (Exception e) {
            return Response.serverError()
                .header("Content-Type", "application/json")
                .entity("{\"error\":\"bridge parse error: " + e.getMessage() + "\"}")
                .build();
        }
    }
}
```

- [ ] **Step 3: Commit**

```bash
cd ~/claude/sparge
git add server/src/main/java/io/sparge/server/PythonBridge.java \
        server/src/main/java/io/sparge/server/BridgeResponse.java
git commit -m "feat(#51): add PythonBridge JEP singleton and BridgeResponse helper"
```

---

## Task 6: SmokeTest — verify Quarkus starts and /api/config responds

Write a `@QuarkusTest` before implementing any resources. It will fail until Task 7 is done, but writing it first proves the JEP + bridge setup works end-to-end.

**Files:**
- Create: `server/src/test/java/io/sparge/server/SmokeTest.java`

- [ ] **Step 1: Write SmokeTest.java**

```java
package io.sparge.server;

import io.quarkus.test.junit.QuarkusTest;
import org.junit.jupiter.api.Test;

import static io.restassured.RestAssured.given;
import static org.hamcrest.Matchers.equalTo;

@QuarkusTest
class SmokeTest {

    @Test
    void configEndpointReturns200() {
        given()
            .when().get("/api/config")
            .then()
            .statusCode(200)
            .body("saved", equalTo(null));  // config_get returns project config, not {"saved":...}
    }
}
```

- [ ] **Step 2: Run the test — expect failure (no resource yet)**

```bash
cd ~/claude/sparge/server
export DYLD_LIBRARY_PATH=~/claude/sparge/resources/python/mac-arm64/lib:$DYLD_LIBRARY_PATH
mvn test -Dtest=SmokeTest \
  -Djava.library.path=~/claude/sparge/resources/python/mac-arm64/lib/python3.12/site-packages/jep \
  2>&1 | tail -20
```

Expected: BUILD FAILURE — `404` (no resource yet) or startup error. That's fine — TDD.

- [ ] **Step 3: Commit the failing test**

```bash
cd ~/claude/sparge
git add server/src/test/java/io/sparge/server/SmokeTest.java
git commit -m "test(#51): add SmokeTest — @QuarkusTest smoke on /api/config (failing)"
```

---

## Task 7: ProjectsResource + ConfigResource + SearchResource

**Files:**
- Create: `server/src/main/java/io/sparge/server/ProjectsResource.java`
- Create: `server/src/main/java/io/sparge/server/ConfigResource.java`
- Create: `server/src/main/java/io/sparge/server/SearchResource.java`

- [ ] **Step 1: Write ProjectsResource.java**

```java
package io.sparge.server;

import jakarta.inject.Inject;
import jakarta.ws.rs.*;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;

@Path("/api/projects")
@Produces(MediaType.APPLICATION_JSON)
@Consumes(MediaType.APPLICATION_JSON)
public class ProjectsResource {

    @Inject PythonBridge bridge;

    @GET
    public Response list() {
        return BridgeResponse.of(bridge.call("bridge.projects_list"));
    }

    @POST
    public Response create(String body) {
        return BridgeResponse.of(bridge.call("bridge.projects_create", body));
    }

    @DELETE
    @Path("{id}")
    public Response delete(@PathParam("id") String id) {
        return BridgeResponse.of(bridge.call("bridge.projects_delete", id));
    }

    @POST
    @Path("{id}/activate")
    public Response activate(@PathParam("id") String id) {
        return BridgeResponse.of(bridge.call("bridge.projects_activate", id));
    }

    @POST
    @Path("{id}/ingest/run")
    public Response projectIngestRun(@PathParam("id") String id, String body) {
        return BridgeResponse.of(bridge.call("bridge.project_ingest_run", id,
                                             body == null ? "{}" : body));
    }
}
```

- [ ] **Step 2: Write ConfigResource.java**

```java
package io.sparge.server;

import jakarta.inject.Inject;
import jakarta.ws.rs.*;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;

@Path("/api/config")
@Produces(MediaType.APPLICATION_JSON)
@Consumes(MediaType.APPLICATION_JSON)
public class ConfigResource {

    @Inject PythonBridge bridge;

    @GET
    public Response get() {
        return BridgeResponse.of(bridge.call("bridge.config_get"));
    }

    @POST
    public Response post(String body) {
        return BridgeResponse.of(bridge.call("bridge.config_post", body == null ? "{}" : body));
    }
}
```

- [ ] **Step 3: Write SearchResource.java**

```java
package io.sparge.server;

import jakarta.inject.Inject;
import jakarta.ws.rs.*;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;

@Path("/api/search")
@Produces(MediaType.APPLICATION_JSON)
public class SearchResource {

    @Inject PythonBridge bridge;

    @GET
    public Response search(@QueryParam("q")     @DefaultValue("") String q,
                           @QueryParam("scope") @DefaultValue("both") String scope) {
        return BridgeResponse.of(bridge.call("bridge.search", q, scope));
    }
}
```

- [ ] **Step 4: Run SmokeTest — should pass now**

```bash
cd ~/claude/sparge/server
export DYLD_LIBRARY_PATH=~/claude/sparge/resources/python/mac-arm64/lib:$DYLD_LIBRARY_PATH
mvn test -Dtest=SmokeTest \
  -Djava.library.path=~/claude/sparge/resources/python/mac-arm64/lib/python3.12/site-packages/jep \
  2>&1 | tail -10
```

Expected: `BUILD SUCCESS`, 1 test passing.

- [ ] **Step 5: Commit**

```bash
cd ~/claude/sparge
git add server/src/main/java/io/sparge/server/ProjectsResource.java \
        server/src/main/java/io/sparge/server/ConfigResource.java \
        server/src/main/java/io/sparge/server/SearchResource.java
git commit -m "feat(#51): add ProjectsResource, ConfigResource, SearchResource"
```

---

## Task 8: PostsResource

All posts endpoints in one resource. Covers: CRUD, HTML source, iframe view, save HTML, generate MD, validate MD, save MD, staged workflow, scan HTML, and dismiss/undismiss HTML checks.

**Files:**
- Create: `server/src/main/java/io/sparge/server/PostsResource.java`

- [ ] **Step 1: Write PostsResource.java**

```java
package io.sparge.server;

import jakarta.inject.Inject;
import jakarta.ws.rs.*;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;

@Path("/api/posts")
@Produces(MediaType.APPLICATION_JSON)
@Consumes(MediaType.APPLICATION_JSON)
public class PostsResource {

    @Inject PythonBridge bridge;

    // ── CRUD ──────────────────────────────────────────────────────────────────

    @GET
    public Response list(@QueryParam("author") String author) {
        return BridgeResponse.of(bridge.call("bridge.posts_list",
                                             author != null ? author : ""));
    }

    @GET
    @Path("{slug}")
    public Response get(@PathParam("slug") String slug) {
        return BridgeResponse.of(bridge.call("bridge.post_get", slug));
    }

    @PATCH
    @Path("{slug}")
    public Response patch(@PathParam("slug") String slug, String body) {
        return BridgeResponse.of(bridge.call("bridge.post_patch", slug,
                                             body == null ? "{}" : body));
    }

    // ── HTML ──────────────────────────────────────────────────────────────────

    @GET
    @Path("{slug}/html")
    @Produces(MediaType.TEXT_PLAIN)
    public Response html(@PathParam("slug") String slug) {
        return BridgeResponse.of(bridge.call("bridge.post_html", slug));
    }

    @GET
    @Path("{slug}/view")
    @Produces(MediaType.TEXT_HTML)
    public Response view(@PathParam("slug") String slug) {
        return BridgeResponse.of(bridge.call("bridge.post_view", slug));
    }

    @POST
    @Path("{slug}/save-html")
    @Consumes(MediaType.TEXT_PLAIN)
    public Response saveHtml(@PathParam("slug") String slug, String body) {
        return BridgeResponse.of(bridge.call("bridge.post_save_html", slug,
                                             body == null ? "" : body));
    }

    // ── Markdown ──────────────────────────────────────────────────────────────

    @POST
    @Path("{slug}/generate-md")
    public Response generateMd(@PathParam("slug") String slug,
                                @QueryParam("dry") @DefaultValue("false") boolean dry) {
        return BridgeResponse.of(bridge.call("bridge.post_generate_md", slug, dry));
    }

    @POST
    @Path("{slug}/validate-md")
    public Response validateMd(@PathParam("slug") String slug) {
        return BridgeResponse.of(bridge.call("bridge.post_validate_md", slug));
    }

    @POST
    @Path("{slug}/save-md")
    @Consumes(MediaType.TEXT_PLAIN)
    public Response saveMd(@PathParam("slug") String slug, String body) {
        return BridgeResponse.of(bridge.call("bridge.post_save_md", slug,
                                             body == null ? "" : body));
    }

    // ── Staged workflow ───────────────────────────────────────────────────────

    @GET
    @Path("{slug}/staged")
    @Produces(MediaType.TEXT_PLAIN)
    public Response stagedGet(@PathParam("slug") String slug) {
        return BridgeResponse.of(bridge.call("bridge.post_staged_get", slug));
    }

    @POST
    @Path("{slug}/stage")
    @Consumes(MediaType.TEXT_PLAIN)
    public Response stage(@PathParam("slug") String slug, String body) {
        return BridgeResponse.of(bridge.call("bridge.post_stage", slug,
                                             body == null ? "" : body));
    }

    @POST
    @Path("{slug}/accept-staged")
    public Response acceptStaged(@PathParam("slug") String slug) {
        return BridgeResponse.of(bridge.call("bridge.post_accept_staged", slug));
    }

    @POST
    @Path("{slug}/reject-staged")
    public Response rejectStaged(@PathParam("slug") String slug) {
        return BridgeResponse.of(bridge.call("bridge.post_reject_staged", slug));
    }

    // ── Scan ─────────────────────────────────────────────────────────────────

    @POST
    @Path("{slug}/scan")
    public Response scan(@PathParam("slug") String slug) {
        return BridgeResponse.of(bridge.call("bridge.post_scan_html", slug));
    }

    // ── Dismiss ───────────────────────────────────────────────────────────────

    @POST
    @Path("{slug}/dismiss-html-check")
    public Response dismiss(@PathParam("slug") String slug, String body) {
        return BridgeResponse.of(bridge.call("bridge.post_dismiss_html_check", slug,
                                             body == null ? "{}" : body));
    }

    @DELETE
    @Path("{slug}/dismiss-html-check/{type}")
    public Response undismiss(@PathParam("slug") String slug,
                              @PathParam("type") String type) {
        return BridgeResponse.of(bridge.call("bridge.post_undismiss_html_check", slug, type));
    }
}
```

Note on `posts_list`: bridge.py's `posts_list(author)` treats empty string as "no filter" (matches server.py behavior where `author=None` means use config default). Java passes `""` when `author` query param is absent.

- [ ] **Step 2: Commit**

```bash
cd ~/claude/sparge
git add server/src/main/java/io/sparge/server/PostsResource.java
git commit -m "feat(#51): add PostsResource — all posts endpoints via JEP bridge"
```

---

## Task 9: IngestResource + ConsolidateResource

**Files:**
- Create: `server/src/main/java/io/sparge/server/IngestResource.java`
- Create: `server/src/main/java/io/sparge/server/ConsolidateResource.java`

- [ ] **Step 1: Write IngestResource.java**

```java
package io.sparge.server;

import jakarta.inject.Inject;
import jakarta.ws.rs.*;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;

@Path("/api/ingest")
@Produces(MediaType.APPLICATION_JSON)
@Consumes(MediaType.APPLICATION_JSON)
public class IngestResource {

    @Inject PythonBridge bridge;

    @GET
    @Path("status")
    public Response status() {
        return BridgeResponse.of(bridge.call("bridge.ingest_status"));
    }

    @POST
    @Path("detect")
    public Response detect(String body) {
        return BridgeResponse.of(bridge.call("bridge.ingest_detect", body == null ? "{}" : body));
    }

    @POST
    @Path("discover")
    public Response discover(String body) {
        return BridgeResponse.of(bridge.call("bridge.ingest_discover", body == null ? "{}" : body));
    }

    @POST
    @Path("preview")
    public Response preview(String body) {
        return BridgeResponse.of(bridge.call("bridge.ingest_preview", body == null ? "{}" : body));
    }

    @POST
    @Path("run")
    public Response run(String body) {
        return BridgeResponse.of(bridge.call("bridge.ingest_run", body == null ? "{}" : body));
    }

    @POST
    @Path("cancel")
    public Response cancel() {
        return BridgeResponse.of(bridge.call("bridge.ingest_cancel"));
    }
}
```

- [ ] **Step 2: Write ConsolidateResource.java**

```java
package io.sparge.server;

import jakarta.inject.Inject;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;

@Path("/api/consolidate")
@Produces(MediaType.APPLICATION_JSON)
public class ConsolidateResource {

    @Inject PythonBridge bridge;

    @POST
    public Response consolidate() {
        return BridgeResponse.of(bridge.call("bridge.consolidate"));
    }
}
```

- [ ] **Step 3: Commit**

```bash
cd ~/claude/sparge
git add server/src/main/java/io/sparge/server/IngestResource.java \
        server/src/main/java/io/sparge/server/ConsolidateResource.java
git commit -m "feat(#51): add IngestResource and ConsolidateResource"
```

---

## Task 10: StaticResource — UI serving, blog assets, root redirect

Quarkus serves UI files from `../ui/` (filesystem, not classpath) and blog assets from `SERVE_ROOT` (resolved via bridge). Root `/` redirects to `/ui/projects.html`.

**Files:**
- Create: `server/src/main/java/io/sparge/server/StaticResource.java`

- [ ] **Step 1: Write StaticResource.java**

```java
package io.sparge.server;

import jakarta.inject.Inject;
import jakarta.ws.rs.*;
import jakarta.ws.rs.core.Response;

import java.io.IOException;
import java.net.URI;
import java.net.URLConnection;
import java.nio.file.Files;
import java.nio.file.NoSuchFileException;
import java.nio.file.Path;
import java.nio.file.Paths;

/**
 * Serves three categories:
 *   GET /               → redirect to /ui/projects.html
 *   GET /ui/{path}      → ../ui/{path} on disk (dev) or classpath (packaged)
 *   GET /{anything}     → blog asset from SERVE_ROOT (resolved via bridge)
 */
@Path("/")
public class StaticResource {

    @Inject PythonBridge bridge;

    private final Path uiDir;

    public StaticResource() {
        Path serverDir = Paths.get(System.getProperty("user.dir")).toAbsolutePath();
        this.uiDir = serverDir.getParent().resolve("ui");
    }

    @GET
    public Response root() {
        return Response.temporaryRedirect(URI.create("/ui/projects.html")).build();
    }

    @GET
    @Path("ui/{path:.*}")
    public Response serveUi(@PathParam("path") String path) {
        String rel = path.isEmpty() ? "projects.html" : path;
        return serveFile(uiDir.resolve(rel));
    }

    @GET
    @Path("{path:.*}")
    public Response serveStatic(@PathParam("path") String path) {
        // Ask bridge to resolve the path against SERVE_ROOT
        String json = bridge.call("bridge.static_resolve", "/" + path);
        try {
            com.fasterxml.jackson.databind.JsonNode node =
                new com.fasterxml.jackson.databind.ObjectMapper().readTree(json);
            if (node.get("status").asInt() != 200) {
                return Response.status(404).build();
            }
            return serveFile(Paths.get(node.get("file_path").asText()));
        } catch (Exception e) {
            return Response.serverError().build();
        }
    }

    private Response serveFile(Path file) {
        try {
            byte[] data = Files.readAllBytes(file);
            String mime = URLConnection.guessContentTypeFromName(file.toString());
            if (mime == null) mime = "application/octet-stream";
            return Response.ok(data)
                .header("Content-Type",              mime)
                .header("Access-Control-Allow-Origin", "*")
                .build();
        } catch (NoSuchFileException e) {
            return Response.status(404).build();
        } catch (IOException e) {
            return Response.serverError().build();
        }
    }
}
```

- [ ] **Step 2: Commit**

```bash
cd ~/claude/sparge
git add server/src/main/java/io/sparge/server/StaticResource.java
git commit -m "feat(#51): add StaticResource — UI and blog asset file serving"
```

---

## Task 11: java-server.js

Mirrors `python-server.js` exactly — same state machine, same events, same readiness polling — but spawns `java -jar sparge-server-runner.jar` with the required JVM flags.

**Files:**
- Create: `java-server.js`

- [ ] **Step 1: Write java-server.js**

```javascript
// java-server.js
'use strict';
const { spawn }        = require('child_process');
const http             = require('http');
const net              = require('net');
const path             = require('path');
const { EventEmitter } = require('events');

const MAX_RESTARTS       = 3;
const STABILITY_RESET_MS = 60_000;
const BACKOFF_MS         = [1000, 2000, 4000];
const LOG_BUFFER_SIZE    = 200;

function findFreePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.listen(0, '127.0.0.1', () => {
      const { port } = server.address();
      server.close(() => resolve(port));
    });
    server.on('error', reject);
  });
}

function pollUntilReady(port, { intervalMs = 200, timeoutMs = 20000 } = {}) {
  return new Promise((resolve, reject) => {
    const deadline = Date.now() + timeoutMs;
    const attempt = () => {
      if (Date.now() >= deadline) {
        reject(new Error(`Java server did not start within ${timeoutMs}ms`));
        return;
      }
      const req = http.get(`http://127.0.0.1:${port}/api/config`, (res) => {
        res.resume();
        if (res.statusCode === 200) resolve();
        else setTimeout(attempt, intervalMs);
      });
      req.on('error', () => setTimeout(attempt, intervalMs));
      req.setTimeout(intervalMs, () => { req.destroy(); });
    };
    attempt();
  });
}

function getJarPath(isPackaged, resourcesPath) {
  if (isPackaged) {
    return path.join(resourcesPath, 'sparge-server-runner.jar');
  }
  return path.join(__dirname, 'server', 'target', 'quarkus-app', 'quarkus-run.jar');
}

function getJepLibPath(isPackaged, resourcesPath) {
  const base = isPackaged
    ? path.join(resourcesPath, 'python')
    : path.join(__dirname, 'resources', 'python', 'mac-arm64');
  return path.join(base, 'lib', 'python3.12', 'site-packages', 'jep');
}

function getPythonLibPath(isPackaged, resourcesPath) {
  const base = isPackaged
    ? path.join(resourcesPath, 'python')
    : path.join(__dirname, 'resources', 'python', 'mac-arm64');
  return path.join(base, 'lib');
}

class JavaServer extends EventEmitter {
  constructor({ isPackaged = false, resourcesPath = '' } = {}) {
    super();
    this._isPackaged   = isPackaged;
    this._resourcesPath = resourcesPath;
    this._port         = null;
    this._process      = null;
    this._state        = 'idle';
    this._logs         = [];
    this._crashCount   = 0;
    this._stabilityTimer = null;
    this._pollFn       = pollUntilReady;
  }

  getPort() { return this._port; }
  getLogs() { return [...this._logs]; }

  async spawnServer(port) {
    this._port  = port;
    this._state = 'starting';
    this._doSpawn();
    await this._pollFn(port);
    this._state = 'healthy';
    this._resetStabilityTimer();
  }

  _doSpawn() {
    const jarPath    = getJarPath(this._isPackaged, this._resourcesPath);
    const jepLib     = getJepLibPath(this._isPackaged, this._resourcesPath);
    const pythonLib  = getPythonLibPath(this._isPackaged, this._resourcesPath);

    const jvmArgs = [
      `-Djava.library.path=${jepLib}`,
      `-Dquarkus.http.port=${this._port}`,
      '-jar', jarPath,
    ];

    const env = {
      ...process.env,
      DYLD_LIBRARY_PATH: `${pythonLib}:${process.env.DYLD_LIBRARY_PATH || ''}`,
      LD_LIBRARY_PATH:   `${pythonLib}:${process.env.LD_LIBRARY_PATH   || ''}`,
    };

    this._process = spawn('java', jvmArgs, { env });
    this._process.stdout.on('data', d => this._appendLog(d.toString()));
    this._process.stderr.on('data', d => this._appendLog(d.toString()));
    this._process.on('exit', (code, signal) => this._onExit(code, signal));
  }

  _appendLog(text) {
    const lines = text.split('\n').filter(l => l.length > 0);
    this._logs.push(...lines);
    if (this._logs.length > LOG_BUFFER_SIZE) this._logs = this._logs.slice(-LOG_BUFFER_SIZE);
  }

  _resetStabilityTimer() {
    if (this._stabilityTimer) clearTimeout(this._stabilityTimer);
    this._stabilityTimer = setTimeout(() => { this._crashCount = 0; }, STABILITY_RESET_MS);
  }

  _onExit(code, signal) {
    if (this._state === 'idle') return;
    this._state = 'crashed';
    this.emit('crashed', { code, signal });
    this._crashCount++;
    if (this._crashCount > MAX_RESTARTS) {
      this._state = 'fatal';
      this.emit('fatal', { logs: this.getLogs() });
      return;
    }
    const delay = BACKOFF_MS[Math.min(this._crashCount - 1, BACKOFF_MS.length - 1)];
    setTimeout(() => this._restart(), delay);
  }

  async _restart() {
    this._state = 'restarting';
    this._doSpawn();
    try {
      await this._pollFn(this._port);
      this._state = 'healthy';
      this.emit('restarted');
      this._resetStabilityTimer();
    } catch (_) {
      // _onExit handles the next failure
    }
  }

  async killServer() {
    this._state = 'idle';
    if (this._stabilityTimer) clearTimeout(this._stabilityTimer);
    if (!this._process) return;
    return new Promise((resolve) => {
      const timer = setTimeout(() => { this._process.kill('SIGKILL'); resolve(); }, 5000);
      this._process.once('exit', () => { clearTimeout(timer); resolve(); });
      this._process.kill('SIGTERM');
    });
  }
}

module.exports = { JavaServer, findFreePort, pollUntilReady };
```

- [ ] **Step 2: Commit**

```bash
cd ~/claude/sparge
git add java-server.js
git commit -m "feat(#51): add java-server.js — JavaServer state machine mirroring python-server.js"
```

---

## Task 12: main.js toggle

Add `SPARGE_SERVER=java` env var support. When set, use `JavaServer` instead of `PythonServer`. Both coexist — easy fallback.

**Files:**
- Modify: `main.js`

- [ ] **Step 1: Read current main.js** (already done — 110 lines, see Task analysis above)

- [ ] **Step 2: Add the import and factory function**

Add after line 7 (`const { PythonServer, findFreePort } = require('./python-server');`):

```javascript
const { JavaServer } = require('./java-server');

function createServer() {
  if (process.env.SPARGE_SERVER === 'java') {
    log.info('Using JavaServer (SPARGE_SERVER=java)');
    return new JavaServer({
      isPackaged:    app.isPackaged,
      resourcesPath: process.resourcesPath,
    });
  }
  log.info('Using PythonServer (default)');
  return new PythonServer({ pythonExe: getPythonExe(), serverScript: getServerScript() });
}
```

- [ ] **Step 3: Replace the `const server = ...` line**

Replace:
```javascript
const server = new PythonServer({ pythonExe: getPythonExe(), serverScript: getServerScript() });
```

With:
```javascript
const server = createServer();
```

- [ ] **Step 4: Verify main.js still loads (no syntax error)**

```bash
node -e "require('./main.js')" 2>&1 | head -5
```

Expected: Electron-specific error about not being in Electron context — that's fine. No `SyntaxError` or `MODULE_NOT_FOUND`.

- [ ] **Step 5: Commit**

```bash
cd ~/claude/sparge
git add main.js
git commit -m "feat(#51): add SPARGE_SERVER=java toggle to main.js"
```

---

## Task 13: Smoke test — Quarkus server starts and serves /api/config

Build the jar, start Quarkus manually, hit /api/config.

- [ ] **Step 1: Build the Quarkus jar**

```bash
cd ~/claude/sparge/server
export DYLD_LIBRARY_PATH=~/claude/sparge/resources/python/mac-arm64/lib:$DYLD_LIBRARY_PATH
mvn package -DskipTests \
  -Djava.library.path=~/claude/sparge/resources/python/mac-arm64/lib/python3.12/site-packages/jep \
  2>&1 | tail -15
```

Expected: `BUILD SUCCESS`, jar at `target/quarkus-app/quarkus-run.jar`.

- [ ] **Step 2: Start the server**

```bash
export DYLD_LIBRARY_PATH=~/claude/sparge/resources/python/mac-arm64/lib:$DYLD_LIBRARY_PATH
cd ~/claude/sparge/server
java \
  -Djava.library.path=~/claude/sparge/resources/python/mac-arm64/lib/python3.12/site-packages/jep \
  -Dquarkus.http.port=9001 \
  -jar target/quarkus-app/quarkus-run.jar &
JAVA_PID=$!
sleep 5  # wait for JVM + Python init
```

- [ ] **Step 3: Hit /api/config**

```bash
curl -s http://127.0.0.1:9001/api/config | python3 -m json.tool | head -20
```

Expected: JSON config object with `project_name`, no `error` key.

- [ ] **Step 4: Hit /api/projects**

```bash
curl -s http://127.0.0.1:9001/api/projects | python3 -m json.tool | head -10
```

Expected: JSON array with at least one project.

- [ ] **Step 5: Stop the server and commit smoke result**

```bash
kill $JAVA_PID
```

```bash
cd ~/claude/sparge
git commit --allow-empty -m "chore(#51): Quarkus server smoke test passed — /api/config and /api/projects respond"
```

---

## Task 14: Run pytest integration tests against Quarkus server

The existing pytest integration tests (the 433 currently skipped) test against a live server. Run them against Quarkus, fix failures.

- [ ] **Step 1: Check how integration tests discover the server port**

```bash
cd ~/claude/sparge && cat tests/conftest.py
```

Look for: `BASE_URL`, `SERVER_URL`, or how the port is determined.

- [ ] **Step 2: Start Quarkus server in background**

```bash
export DYLD_LIBRARY_PATH=~/claude/sparge/resources/python/mac-arm64/lib:$DYLD_LIBRARY_PATH
cd ~/claude/sparge/server
java \
  -Djava.library.path=~/claude/sparge/resources/python/mac-arm64/lib/python3.12/site-packages/jep \
  -Dquarkus.http.port=9001 \
  -jar target/quarkus-app/quarkus-run.jar > /tmp/quarkus-test.log 2>&1 &
JAVA_PID=$!
sleep 8  # JVM + CPython init takes ~5s
```

- [ ] **Step 3: Run pytest integration tests**

```bash
cd ~/claude/sparge
BASE_URL=http://127.0.0.1:9001 python3 -m pytest tests/ -q --tb=short 2>&1 | tail -30
```

If conftest.py uses a different env var for the server URL, adjust accordingly (check Step 1).

- [ ] **Step 4: For each failing test — diagnose and fix**

Likely failure categories:
- **Missing CORS header** → check BridgeResponse adds `Access-Control-Allow-Origin: *`
- **Content-Type mismatch** → check `text/plain` vs `application/json` endpoints
- **Query param not passed** → check `posts_list(author)` handles empty string vs None
- **Route not matching** → compare server.py routing vs JAX-RS `@Path` annotations

Fix in the appropriate resource or bridge.py. Run the failing test after each fix:
```bash
BASE_URL=http://127.0.0.1:9001 python3 -m pytest tests/test_<name>.py -q
```

- [ ] **Step 5: All integration tests green**

```bash
BASE_URL=http://127.0.0.1:9001 python3 -m pytest tests/ -q 2>&1 | tail -5
```

Expected: `N passed, M skipped, 0 failed` where previously-failing integration tests now pass.

- [ ] **Step 6: Stop server, run non-integration tests**

```bash
kill $JAVA_PID
cd ~/claude/sparge && python3 -m pytest tests/ -q 2>&1 | tail -5
```

Expected: 473 passing, 0 failing (Python server not running, integration tests skip — same as before).

- [ ] **Step 7: Commit all fixes**

```bash
cd ~/claude/sparge
git add -p  # stage only relevant changes
git commit -m "fix(#51): resolve integration test failures against Quarkus server"
```

---

## Task 15: Closing commit

- [ ] **Step 1: Final full test run (Python server)**

```bash
cd ~/claude/sparge && python3 -m pytest tests/ -q 2>&1 | tail -5
```

Expected: 473 passing, 0 failing.

- [ ] **Step 2: Maven test run (Quarkus JUnit)**

```bash
cd ~/claude/sparge/server
export DYLD_LIBRARY_PATH=~/claude/sparge/resources/python/mac-arm64/lib:$DYLD_LIBRARY_PATH
mvn test \
  -Djava.library.path=~/claude/sparge/resources/python/mac-arm64/lib/python3.12/site-packages/jep \
  2>&1 | tail -10
```

Expected: BUILD SUCCESS, SmokeTest passes.

- [ ] **Step 3: Final commit referencing closure**

```bash
cd ~/claude/sparge
git commit --allow-empty -m "feat(#51): Phase 0 complete — Quarkus JEP bridge serving all endpoints

All pytest integration tests pass against Quarkus server.
SPARGE_SERVER=java selects java-server.js in Electron.
bridge.py wraps all Python handler logic; no modules ported yet.

Closes #51"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|---|---|
| Quarkus project at `server/` | Task 4 |
| JEP + `libpython3.12.dylib` linking | Task 2 |
| `PythonBridge` `@ApplicationScoped` singleton | Task 5 |
| All 35+ endpoints as JAX-RS resources | Tasks 7–10 |
| `java-server.js` state machine | Task 11 |
| `main.js` toggle (`SPARGE_SERVER=java`) | Task 12 |
| All pytest integration tests pass against Quarkus | Task 14 |
| `ENRICHED_DIR` hardcoded path fixed | Task 1 |
| `tests/python-legacy/` holding area | Not needed until Phase 1 (first port) |
| JMH benchmarks | Not needed until Phase 1 |

**Type consistency check:**
- `bridge.py` function names match `bridge.call("bridge.<name>", ...)` in resources ✓
- `BridgeResponse.of()` used consistently in every resource ✓
- `posts_list(author: str)` — Java passes `""` for absent param, Python treats `""` as "no filter" ✓

**Placeholder check:**
- Task 14, Step 4 mentions "Likely failure categories" — this is intentionally open-ended because actual failures depend on runtime behavior. The categories are specific enough to guide diagnosis.

---

## Execution

**Two options:**

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task with two-stage review between tasks.

**2. Inline Execution** — execute in this session using `superpowers:executing-plans`.

Which approach?
