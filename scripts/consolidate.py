"""
Asset Consolidation
===================
Hash-based consolidation pass: finds assets with identical content across
multiple post folders and moves them to global/, updating all cleaned/ HTML
references.

This complements the URL-based real-time detection in asset_store.py.
Use it after bulk ingestion to catch cases where the same image was served
from different URLs (CDN mirrors, redirects, re-uploads).

Usage
─────
    from consolidate import consolidate
    report = consolidate(assets_root, cleaned_dir)
    print(f"Moved {report['promoted']} assets to global/")
"""

import re
from collections import defaultdict
from pathlib import Path

from asset_store import AssetStore, file_hash


def consolidate(assets_root: Path, cleaned_dir: Path) -> dict:
    """
    Scan all post asset folders, find files with identical SHA-256 across
    different posts, promote them to global/, update cleaned/ HTML references.

    Parameters
    ----------
    assets_root : Path
        The assets/ directory containing global/ and posts/.
    cleaned_dir : Path
        The cleaned/ directory containing the working HTML copies.

    Returns
    -------
    dict with keys:
        promoted     int  — number of files moved to global/
        updated_html int  — number of HTML files whose references were rewritten
        duplicates   list — [{hash, files: [...], global_path}] for each group
    """
    store = AssetStore(assets_root)
    post_assets = store.all_post_assets()

    # Build hash → [path] map across all post folders
    hash_to_paths: dict[str, list[Path]] = defaultdict(list)
    for slug, paths in post_assets.items():
        for p in paths:
            if p.is_file():
                hash_to_paths[file_hash(p)].append(p)

    promoted    = 0
    duplicates  = []
    global_map: dict[Path, Path] = {}  # old_path → new_global_path

    for h, paths in hash_to_paths.items():
        # Only consolidate if the same content appears in 2+ different posts
        slugs = {p.parent.name for p in paths}
        if len(slugs) < 2:
            continue

        # Promote the first file; record mapping for all duplicates
        primary = paths[0]
        new_path = store.promote_to_global(primary)
        global_map[primary] = new_path
        promoted += 1

        # Remove the duplicate copies (same content, different post folders)
        removed = []
        for dup in paths[1:]:
            if dup.exists():
                old_rel = dup.relative_to(assets_root).as_posix()
                new_rel = new_path.relative_to(assets_root).as_posix()
                # Update index entry
                store._idx = {
                    url: (new_rel if rel == old_rel else rel)
                    for url, rel in store._idx.items()
                }
                global_map[dup] = new_path
                removed.append(dup)
                dup.unlink()

        store._save_index()
        duplicates.append({
            'hash':        h[:12],
            'files':       [str(p) for p in paths],
            'global_path': str(new_path),
        })

    # Rewrite cleaned/ HTML references
    updated_html = _rewrite_html_references(cleaned_dir, global_map, assets_root)

    return {
        'promoted':     promoted,
        'updated_html': updated_html,
        'duplicates':   duplicates,
    }


def _rewrite_html_references(
    cleaned_dir: Path,
    global_map: dict[Path, Path],
    assets_root: Path,
) -> int:
    """
    Update src/href attributes in cleaned/ HTML files to point to new global/ paths.
    Returns the number of HTML files that were modified.
    """
    if not cleaned_dir.exists() or not global_map:
        return 0

    # Build old_web_path → new_web_path map
    path_remap: dict[str, str] = {}
    for old_path, new_path in global_map.items():
        try:
            old_rel = '/assets/' + old_path.relative_to(assets_root).as_posix()
            new_rel = '/assets/' + new_path.relative_to(assets_root).as_posix()
            path_remap[old_rel] = new_rel
        except ValueError:
            continue

    if not path_remap:
        return 0

    # Build a single regex that matches any of the old paths
    pattern = re.compile(
        '|'.join(re.escape(old) for old in path_remap),
        re.IGNORECASE,
    )

    updated = 0
    for html_file in cleaned_dir.rglob('*.html'):
        text = html_file.read_text(errors='replace')
        new_text = pattern.sub(lambda m: path_remap[m.group(0)], text)
        if new_text != text:
            html_file.write_text(new_text, encoding='utf-8')
            updated += 1

    return updated
