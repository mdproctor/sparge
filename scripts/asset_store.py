"""
Asset Store
===========
Manages the per-post and global asset organisation for a Sparge project.

Directory layout
────────────────
  {assets_root}/
    global/           ← images shared across multiple posts
      logo.png
      avatar.jpg
    posts/
      2006-05-31-what-is-a-rule-engine/
        rete-diagram.png
        screenshot.jpg
      2006-06-02-rule-execution-flow/
        waltz-diagram.png

Detection strategy
──────────────────
1. URL-based (real-time, during ingest):
   If the same source URL has already been downloaded for a different post,
   route the asset to global/ immediately. Same URL = same asset = shared.

2. Hash-based (consolidation pass, post-processing):
   After bulk ingest, scan all posts/ subfolders, compute SHA-256 for each
   file, identify files with identical content across different posts, move
   them to global/, rewrite cleaned/ HTML references accordingly.
   Catches cases where the same image was served from different URLs.

Within-post filename collisions
────────────────────────────────
If two different images in the same post share a filename (e.g. two separate
images both called 'diagram.png'), the second gets a numeric suffix:
  diagram.png → diagram-2.png → diagram-3.png …
"""

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse


# ── Public interface ──────────────────────────────────────────────────────────

class AssetStore:
    """
    Manages asset paths and the URL index for a single project.

    Parameters
    ----------
    assets_root : Path
        Absolute path to the assets/ directory (contains global/ and posts/).
    """

    def __init__(self, assets_root: Path):
        self.root      = assets_root
        self._idx_path = assets_root / '.url-index.json'
        self._idx      = self._load_index()

    # ── Index persistence ─────────────────────────────────────────────────────

    def _load_index(self) -> dict:
        """Load URL → relative-path index from disk."""
        if self._idx_path.exists():
            try:
                return json.loads(self._idx_path.read_text())
            except Exception:
                pass
        return {}  # url → relative path from assets_root

    def _save_index(self):
        self.root.mkdir(parents=True, exist_ok=True)
        self._idx_path.write_text(json.dumps(self._idx, indent=2))

    # ── Path resolution ───────────────────────────────────────────────────────

    def resolve(self, url: str) -> Path | None:
        """
        Return the local Path for a previously-downloaded URL, or None.
        Path is absolute.
        """
        rel = self._idx.get(url)
        return (self.root / rel) if rel else None

    def web_path(self, url: str) -> str | None:
        """
        Return the web-accessible path (e.g. '/assets/posts/SLUG/img.jpg')
        for a previously-downloaded URL, or None.
        """
        rel = self._idx.get(url)
        return f'/assets/{rel}' if rel else None

    # ── Slot allocation ───────────────────────────────────────────────────────

    def allocate(self, url: str, slug: str) -> Path:
        """
        Decide the local path for a new download.

        Rules:
        - If the URL has already been downloaded for a *different* slug
          → route to global/ (URL-based sharing detection).
        - Otherwise → route to posts/{slug}/.
        - Resolve within-folder filename collisions with a numeric suffix.

        Returns the absolute Path to write to. Does NOT download.
        Does NOT update the index — call record() after successful download.
        """
        # Check if URL already downloaded for another slug
        existing_rel = self._idx.get(url)
        if existing_rel:
            # Already downloaded — return existing path (no new write needed)
            return self.root / existing_rel

        filename   = _safe_filename(url)
        same_slug  = self._slugs_for_url_pattern(url)
        use_global = bool(same_slug - {slug})   # seen by a different slug

        folder = self.root / ('global' if use_global else f'posts/{slug}')
        return self._unique_path(folder, filename)

    def record(self, url: str, local_path: Path):
        """
        Record a completed download in the URL index.
        local_path must be inside self.root.
        """
        rel = local_path.relative_to(self.root).as_posix()
        self._idx[url] = rel
        self._save_index()

    def promote_to_global(self, local_path: Path) -> Path:
        """
        Move a file from posts/{slug}/ to global/ and update the index.
        Used by the hash-based consolidation pass.
        Returns the new global path.
        """
        filename    = local_path.name
        global_dir  = self.root / 'global'
        new_path    = self._unique_path(global_dir, filename)
        new_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.rename(new_path)

        # Update all index entries pointing to the old path
        old_rel = local_path.relative_to(self.root).as_posix()
        new_rel = new_path.relative_to(self.root).as_posix()
        for url, rel in list(self._idx.items()):
            if rel == old_rel:
                self._idx[url] = new_rel
        self._save_index()
        return new_path

    # ── Inspection ────────────────────────────────────────────────────────────

    def all_post_assets(self) -> dict[str, list[Path]]:
        """Return {slug: [absolute paths]} for all post-specific assets."""
        posts_dir = self.root / 'posts'
        result: dict[str, list[Path]] = {}
        if posts_dir.exists():
            for slug_dir in posts_dir.iterdir():
                if slug_dir.is_dir():
                    result[slug_dir.name] = list(slug_dir.iterdir())
        return result

    def global_assets(self) -> list[Path]:
        """Return all absolute paths in global/."""
        global_dir = self.root / 'global'
        return list(global_dir.iterdir()) if global_dir.exists() else []

    # ── Internals ─────────────────────────────────────────────────────────────

    def _slugs_for_url_pattern(self, url: str) -> set[str]:
        """Return the set of slugs that have downloaded this URL."""
        rel = self._idx.get(url)
        if not rel:
            return set()
        # Extract slug from rel path posts/{slug}/filename
        parts = rel.split('/')
        if len(parts) >= 2 and parts[0] == 'posts':
            return {parts[1]}
        return {'__global__'}

    def _unique_path(self, folder: Path, filename: str) -> Path:
        """Return a path in folder for filename, adding suffix if name taken."""
        folder.mkdir(parents=True, exist_ok=True)
        candidate = folder / filename
        if not candidate.exists():
            return candidate
        stem, suffix = _split_stem_suffix(filename)
        n = 2
        while True:
            candidate = folder / f'{stem}-{n}{suffix}'
            if not candidate.exists():
                return candidate
            n += 1


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_filename(url: str) -> str:
    """Derive a filesystem-safe filename from a URL."""
    path     = urlparse(url).path
    name     = path.rstrip('/').split('/')[-1] or 'asset'
    name     = re.sub(r'[^\w.\-]', '_', name)
    name     = name[:120]  # cap length
    return name or 'asset'


def _split_stem_suffix(filename: str) -> tuple[str, str]:
    """Split 'diagram.png' → ('diagram', '.png'), 'archive.tar.gz' → ('archive.tar', '.gz')."""
    p      = Path(filename)
    suffix = p.suffix          # last extension only
    stem   = filename[:-len(suffix)] if suffix else filename
    return stem, suffix


def file_hash(path: Path) -> str:
    """Return SHA-256 hex digest (full 64 chars) of a file."""
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()
