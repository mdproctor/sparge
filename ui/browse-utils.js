'use strict';

/**
 * Compute the path to store in config after the user picks a folder.
 *
 * Rules:
 *   - If selected equals serveRoot     → store '.'
 *   - If selected is inside serveRoot  → store relative path
 *   - If selected is outside serveRoot → store absolute path
 *   - If serveRoot is not set          → store absolute path
 *
 * @param {string} selectedPath  Absolute path returned by the OS dialog
 * @param {string|null} serveRoot  Current value of the serve_root field
 * @returns {string}
 */
function computeStoredPath(selectedPath, serveRoot) {
  if (!serveRoot) return selectedPath;

  const norm = (p) => p.replace(/\\/g, '/').replace(/\/$/, '');
  const sel  = norm(selectedPath);
  const root = norm(serveRoot);

  if (sel === root) return '.';
  if (sel.startsWith(root + '/')) return sel.slice(root.length + 1);
  return selectedPath;
}

if (typeof module !== 'undefined') module.exports = { computeStoredPath };
