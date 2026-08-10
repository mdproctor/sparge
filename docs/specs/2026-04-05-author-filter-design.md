# Sparge Storage Migration + Author Filter Design

## Goals

1. **Storage migration** — Move project data out of the repo into a proper user-level location (`~/sparge-projects/`), with Sparge's own app config at `~/.sparge/config.json` pointing to it.
2. **Author filter** — Restrict both the API and UI to a configured author by default, with a UI dropdown to override.

These are implemented together because both require changes to how `server.py` resolves paths.

---

## Part 1: Storage Migration

### Current state

```
blog-migrator/
  projects.json
  projects/kie-mark-proctor/
    config.json
    state.json
    enriched/
```

Problems: project data lives inside the app repo, couples data to code, not portable.

### Target state

```
~/.sparge/
  config.json          ← { "projects_dir": "~/sparge-projects" }

~/sparge-projects/     ← default, user-configurable
  projects.json
  kie-mark-proctor/
    config.json
    state.json
    enriched/
```

### `~/.sparge/config.json` schema

```json
{
  "projects_dir": "~/sparge-projects"
}
```

`projects_dir` supports `~/` expansion. Default if file absent: `~/sparge-projects`.

### Migration

On first startup after the change, if `~/.sparge/config.json` does not exist:
1. Create `~/.sparge/` and write default `config.json`
2. Create `~/sparge-projects/` if it doesn't exist
3. If `blog-migrator/projects.json` exists, copy it to `~/sparge-projects/projects.json`
4. Copy each project directory from `blog-migrator/projects/{id}/` to `~/sparge-projects/{id}/`
5. Print migration notice to console

### Server changes

`server.py` currently hardcodes `PROJECTS_FILE = ROOT / 'projects' / 'projects.json'` and `_project_dir()` relative to `ROOT`. After the change:

- On startup, read `~/.sparge/config.json` → resolve `projects_dir`
- `PROJECTS_DIR: Path` module-level variable pointing to resolved `projects_dir`
- `PROJECTS_FILE = PROJECTS_DIR / 'projects.json'`
- `_project_dir(id)` returns `PROJECTS_DIR / id`
- `ENRICHED_DIR` default fallback updated to use `PROJECTS_DIR`

No other endpoints change — all path resolution flows through these two variables.

---

## Part 2: Author Filter

### Context

- Posts in `state.json` have an `author` field
- `config.json` already has `filter.author` (used during ingest)
- The UI's `filtered()` function filters posts by status client-side
- `GET /api/posts` currently returns all posts with no author filtering

### Backend — `GET /api/posts?author=X`

`_api_posts_list()` reads an optional `author` query parameter:
- `?author=X` present and non-empty → filter posts to that author
- `?author=` absent → fall back to `cfg.get('filter', {}).get('author', '')` as default
- Default also empty → return all posts (existing behaviour)

### UI — Author dropdown in filter bar

A `<select>` added to `#nav-filters`:
- Options: "All authors" + unique authors extracted from the returned post list
- On page load: pre-selected from `cfg.filter.author` (loaded via `/api/config`)
- On change: re-fetches `/api/posts?author=X` and re-renders
- "All authors" sends `?author=` to override the config default

The existing `filtered()` function applies status filters on top unchanged.

### Behaviour table

| Config `filter.author` | Dropdown | Posts returned |
|---|---|---|
| `"Mark Proctor"` | Mark Proctor (default) | Mark's posts only |
| `"Mark Proctor"` | All authors | All posts in state.json |
| *(empty)* | All authors (default) | All posts |
| *(empty)* | Specific author | That author's posts |

---

## Files Changed

| File | Change |
|---|---|
| `blog-migrator/server.py` | Read `~/.sparge/config.json` on startup; `PROJECTS_DIR` variable; migration logic; `_api_posts_list()` author param |
| `blog-migrator/ui/index.html` | Author `<select>` in `#nav-filters`; pre-select from config; re-fetch on change |

## What Does NOT Change

- Project `config.json` schema unchanged (serve_root, posts_dir, filter, github_token, etc.)
- All per-post API endpoints unchanged
- `filtered()` status filter logic unchanged
- Posts list sort order unchanged
- Existing `blog-migrator/projects/` left in place during migration (not deleted automatically)
