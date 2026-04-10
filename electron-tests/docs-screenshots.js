// electron-tests/docs-screenshots.js
//
// Generates all screenshots for docs/user-guide/.
// Run with: npm run docs:screenshots
//
// Prerequisites:
//   - resources/python/ must exist (run: node scripts/fetch-python.js)
//   - Electron binary must be installed

const { _electron: electron } = require('playwright');
const path = require('path');
const fs   = require('fs');
const os   = require('os');

const ROOT        = path.join(__dirname, '..');
const IMAGES_DIR  = path.join(ROOT, 'docs', 'user-guide', 'images');
const FIXTURE_DIR = path.join(__dirname, 'fixtures', 'docs-posts');

let app, window;

// ── helpers ────────────────────────────────────────────────────────────────

async function shot(selector, filename) {
  const loc  = window.locator(selector);
  await loc.waitFor({ state: 'visible', timeout: 10000 });
  const dest = path.join(IMAGES_DIR, filename);
  await loc.screenshot({ path: dest });
  console.log(`  ✓ ${filename}`);
}

async function shotRegion(filename, clip) {
  const dest = path.join(IMAGES_DIR, filename);
  await window.screenshot({ path: dest, clip });
  console.log(`  ✓ ${filename}`);
}

async function api(method, endpoint, body = null) {
  const base = new URL(window.url()).origin;
  return window.evaluate(
    async ({ method, url, body }) => {
      const opts = { method, headers: { 'Content-Type': 'application/json' } };
      if (body) opts.body = JSON.stringify(body);
      const res = await fetch(url, opts);
      return res.json();
    },
    { method, url: `${base}${endpoint}`, body }
  );
}

async function waitMs(ms) {
  return new Promise(r => setTimeout(r, ms));
}

// ── fixture project ────────────────────────────────────────────────────────

async function setupFixtureProject() {
  const fixtureRoot = path.join(os.tmpdir(), 'sparge-docs-fixture');
  const postsDir    = path.join(fixtureRoot, 'posts');
  const mdDir       = path.join(fixtureRoot, 'md');
  fs.mkdirSync(postsDir, { recursive: true });
  fs.mkdirSync(mdDir,    { recursive: true });

  for (const f of fs.readdirSync(FIXTURE_DIR)) {
    fs.copyFileSync(path.join(FIXTURE_DIR, f), path.join(postsDir, f));
  }

  const project = await api('POST', '/api/projects', {
    name:         'Docs Fixture',
    serve_root:   fixtureRoot,
    posts_dir:    'posts',
    md_dir:       'md',
    enriched_dir: 'enriched',
  });

  await api('POST', `/api/projects/${project.id}/activate`);
  await waitMs(500);
  return project;
}

// ── captures ───────────────────────────────────────────────────────────────

async function captureProjectsScreen() {
  console.log('\n[Projects screen]');
  const base = new URL(window.url()).origin;
  await window.goto(`${base}/ui/projects.html`);
  await window.waitForLoadState('domcontentloaded');
  await waitMs(500);

  // Full projects screen (empty/initial state)
  await shot('body', '01-first-launch.png');

  // Open new project form
  const newBtn = window.locator(
    'button:has-text("New Project"), [data-action="new-project"], .new-project-btn, button:has-text("New"), button:has-text("Create")'
  );
  if (await newBtn.count() > 0) {
    await newBtn.first().click();
    await waitMs(400);
    const form = window.locator('form, .project-form, #new-project-form, .modal, .dialog');
    if (await form.count() > 0) {
      await form.first().screenshot({ path: path.join(IMAGES_DIR, '02-new-project-form.png') });
      console.log('  ✓ 02-new-project-form.png');
    }
    // Close form
    const cancelBtn = window.locator('button:has-text("Cancel"), .cancel-btn, [data-action="cancel"]');
    if (await cancelBtn.count() > 0) await cancelBtn.first().click();
    await waitMs(200);
  }
}

// ── main ───────────────────────────────────────────────────────────────────

(async () => {
  console.log('\n📸  Sparge docs screenshots\n');
  fs.mkdirSync(IMAGES_DIR, { recursive: true });

  app    = await electron.launch({ args: [path.join(ROOT, 'main.js')] });
  window = await app.firstWindow();
  await window.waitForLoadState('domcontentloaded');
  await waitMs(2000);

  try {
    await captureProjectsScreen();
    await setupFixtureProject();
    console.log('\n✅  Phase 1 complete — fixture project set up\n');
  } finally {
    await app.close();
  }
})();
