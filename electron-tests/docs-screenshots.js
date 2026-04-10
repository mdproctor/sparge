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

async function navigateToMainApp() {
  const base = new URL(window.url()).origin;
  await window.goto(`${base}/ui/index.html`);
  await window.waitForLoadState('domcontentloaded');
  await waitMs(1000);
}

async function captureMainAppScreens() {
  console.log('\n[Main app screens]');

  // Hero: full app body
  await window.screenshot({ path: path.join(IMAGES_DIR, 'README-hero.png') });
  console.log('  ✓ README-hero.png');

  // Post list
  const postListSel = '.posts, #posts, .post-list, #post-list, [class*="post-list"], main';
  await shot(postListSel, '04-post-list-mixed-states.png');

  // Config panel (top-right button)
  const configBtn = window.locator(
    'button[title*="Config"], button[title*="config"], #config-btn, .config-btn, button[title*="Settings"], button[title*="settings"]'
  );
  if (await configBtn.count() > 0) {
    await configBtn.first().click();
    await waitMs(400);
    const panel = window.locator('#config-panel, .config-panel, [data-panel="config"], .settings-panel');
    if (await panel.count() > 0) {
      await panel.first().screenshot({ path: path.join(IMAGES_DIR, '02-config-panel.png') });
      console.log('  ✓ 02-config-panel.png');
    }
    await window.keyboard.press('Escape');
    await waitMs(200);
  }

  // Click first post to open split pane
  const postRow = window.locator('.post-row, .post-item, [data-slug], li[data-id], .post').first();
  if (await postRow.count() > 0) {
    await postRow.click();
    await waitMs(800);
    await window.screenshot({ path: path.join(IMAGES_DIR, '05-split-pane-open.png') });
    console.log('  ✓ 05-split-pane-open.png');

    // Action buttons
    const actionBar = window.locator('.action-bar, .post-actions, #action-buttons, .toolbar, .actions');
    if (await actionBar.count() > 0) {
      await actionBar.first().screenshot({ path: path.join(IMAGES_DIR, '05-action-buttons.png') });
      console.log('  ✓ 05-action-buttons.png');
    }

    // Post metadata
    const metaEl = window.locator('.post-meta, .post-metadata, #post-meta, .meta-panel');
    if (await metaEl.count() > 0) {
      await metaEl.first().screenshot({ path: path.join(IMAGES_DIR, '05-post-metadata.png') });
      console.log('  ✓ 05-post-metadata.png');
    }
  }
}

async function captureEditorScreens() {
  console.log('\n[Editor screens]');

  const posts = await api('GET', '/api/posts');
  const cleanSlug = posts.find(p => p.slug === 'intro-to-sparge')?.slug || posts[0]?.slug;
  const issueSlug = posts.find(p => p.slug === 'cloud-architecture')?.slug || posts[1]?.slug;
  const javaSlug  = posts.find(p => p.slug === 'java-virtual-threads')?.slug;
  const devopsSlug = posts.find(p => p.slug === 'devops-best-practices')?.slug;

  // Scan + generate MD for clean post
  await api('POST', `/api/posts/${cleanSlug}/scan-html`);
  await waitMs(1000);
  await api('POST', `/api/posts/${cleanSlug}/generate-md`);
  await waitMs(500);

  // Navigate to clean post
  const cleanRow = window.locator(`[data-slug="${cleanSlug}"], .post-row, .post-item`).first();
  await cleanRow.click();
  await waitMs(600);

  // HTML editor (left pane)
  const htmlPane = window.locator('.html-pane, #html-editor, .editor-left, .left-pane, [class*="html"]').first();
  if (await htmlPane.count() > 0) {
    await htmlPane.screenshot({ path: path.join(IMAGES_DIR, '06-html-editor.png') });
    console.log('  ✓ 06-html-editor.png');
  }

  // MD editor (right pane)
  const mdPane = window.locator('.md-pane, #md-editor, .editor-right, .right-pane, [class*="markdown"]').first();
  if (await mdPane.count() > 0) {
    await mdPane.screenshot({ path: path.join(IMAGES_DIR, '07-md-editor.png') });
    console.log('  ✓ 07-md-editor.png');
  }

  // Scan issue post and navigate to it
  if (issueSlug) {
    await api('POST', `/api/posts/${issueSlug}/scan-html`);
    await waitMs(800);
    const issueRow = window.locator(`[data-slug="${issueSlug}"]`);
    if (await issueRow.count() > 0) {
      await issueRow.click();
      await waitMs(600);
      // Click first issue to trigger highlight
      const firstIssue = window.locator('.issue-item, .html-issue, [data-issue-type], .issue').first();
      if (await firstIssue.count() > 0) {
        await firstIssue.click();
        await waitMs(400);
        if (await htmlPane.count() > 0) {
          await htmlPane.screenshot({ path: path.join(IMAGES_DIR, '06-issue-highlight.png') });
          console.log('  ✓ 06-issue-highlight.png');
        }
      }
    }
  }

  // Stage devops post for staging screenshots
  if (devopsSlug) {
    await api('POST', `/api/posts/${devopsSlug}/scan-html`);
    await api('POST', `/api/posts/${devopsSlug}/generate-md`);
    await waitMs(800);
    await api('POST', `/api/posts/${devopsSlug}/stage`, { content: '# DevOps Best Practices\n\nThis is a staged draft for the documentation demo.\n\n## Continuous Integration\n\nRun your full test suite on every commit.\n' });
    await waitMs(300);
  }

  // Java post for validation issues screenshot
  if (javaSlug) {
    await api('POST', `/api/posts/${javaSlug}/scan-html`);
    await api('POST', `/api/posts/${javaSlug}/generate-md`);
    await waitMs(800);
    const javaRow = window.locator(`[data-slug="${javaSlug}"]`);
    if (await javaRow.count() > 0) {
      await javaRow.click();
      await waitMs(600);
      if (await mdPane.count() > 0) {
        await mdPane.screenshot({ path: path.join(IMAGES_DIR, '07-validation-issues.png') });
        console.log('  ✓ 07-validation-issues.png');
      }
    }
  }
}

async function captureIssuesScreens() {
  console.log('\n[Issues panel screens]');

  const posts = await api('GET', '/api/posts');
  const issueSlug = posts.find(p => p.slug === 'cloud-architecture')?.slug
                 || posts.find(p => p.html?.issues?.length > 0)?.slug;

  if (issueSlug) {
    const issueRow = window.locator(`[data-slug="${issueSlug}"]`);
    if (await issueRow.count() > 0) {
      await issueRow.click();
      await waitMs(600);
    }
  }

  // Open issues panel if there's a toggle
  const issuesPanelBtn = window.locator(
    'button[title*="Issues"], .issues-tab, #issues-btn, button:has-text("Issues")'
  );
  if (await issuesPanelBtn.count() > 0) {
    await issuesPanelBtn.first().click();
    await waitMs(300);
  }

  const issuesPanel = window.locator('.issues-panel, #issues-panel, .html-issues, .issues');
  if (await issuesPanel.count() > 0) {
    await issuesPanel.first().screenshot({ path: path.join(IMAGES_DIR, '08-issues-panel.png') });
    console.log('  ✓ 08-issues-panel.png');

    // Hover to reveal dismiss button
    const issueItem = window.locator('.issue-item, [data-issue-type], .issue').first();
    if (await issueItem.count() > 0) {
      await issueItem.hover();
      await waitMs(200);
      await issuesPanel.first().screenshot({ path: path.join(IMAGES_DIR, '08-dismiss-flow.png') });
      console.log('  ✓ 08-dismiss-flow.png');

      // Click issue to highlight in editor
      await issueItem.click();
      await waitMs(300);
      const htmlPane = window.locator('.html-pane, #html-editor, .editor-left, .left-pane').first();
      if (await htmlPane.count() > 0) {
        await htmlPane.screenshot({ path: path.join(IMAGES_DIR, '08-issue-highlighted.png') });
        console.log('  ✓ 08-issue-highlighted.png');
      }
    }
  }

  // Issue breakdown stats
  const breakdown = window.locator('.issue-breakdown, .issues-stats, #issue-breakdown');
  if (await breakdown.count() > 0) {
    await breakdown.first().screenshot({ path: path.join(IMAGES_DIR, '08-issue-breakdown.png') });
    console.log('  ✓ 08-issue-breakdown.png');
  }
}

async function captureSearchFilterScreens() {
  console.log('\n[Search and filter screens]');

  // Search
  const searchInput = window.locator(
    'input[type="search"], #search-input, .search-bar input, input[placeholder*="Search"], input[placeholder*="search"]'
  );
  if (await searchInput.count() > 0) {
    await searchInput.first().fill('quarkus');
    await waitMs(600);
    await window.screenshot({ path: path.join(IMAGES_DIR, '09-search-active.png') });
    console.log('  ✓ 09-search-active.png');
    await searchInput.first().fill('');
    await waitMs(300);
  }

  // Filter buttons
  const filterBtn = window.locator('.filter-btn, .issue-filter, [data-filter-type], .scope-btn').first();
  if (await filterBtn.count() > 0) {
    await filterBtn.click();
    await waitMs(400);
    await window.screenshot({ path: path.join(IMAGES_DIR, '09-filter-buttons.png') });
    console.log('  ✓ 09-filter-buttons.png');
    await filterBtn.click();
    await waitMs(200);
  }

  // Filtered list (after search scope)
  const scopeEl = window.locator('select[name*="scope"], .search-scope, #search-scope, select');
  if (await scopeEl.count() > 0) {
    const searchBar = window.locator('.search-bar, .search-container, .search-area');
    if (await searchBar.count() > 0) {
      await searchBar.first().screenshot({ path: path.join(IMAGES_DIR, 'features-search-scope.png') });
      console.log('  ✓ features-search-scope.png');
    }
  }

  const postList = window.locator('.posts, #posts, .post-list, #post-list, main').first();
  if (await postList.count() > 0) {
    await postList.screenshot({ path: path.join(IMAGES_DIR, '09-filtered-list.png') });
    console.log('  ✓ 09-filtered-list.png');
  }
}

async function captureStagingScreens() {
  console.log('\n[Staging screens]');

  const posts = await api('GET', '/api/posts');
  const stagedPost = posts.find(p => p.md?.staged);

  if (stagedPost) {
    const row = window.locator(`[data-slug="${stagedPost.slug}"]`);
    if (await row.count() > 0) {
      await row.click();
      await waitMs(600);
      const mdPane = window.locator('.md-pane, #md-editor, .editor-right, .right-pane').first();
      if (await mdPane.count() > 0) {
        await mdPane.screenshot({ path: path.join(IMAGES_DIR, '10-staged-state.png') });
        console.log('  ✓ 10-staged-state.png');
      }
      const stagingActions = window.locator(
        '.staging-actions, .md-toolbar, .editor-actions, button:has-text("Accept"), button:has-text("Reject")'
      );
      if (await stagingActions.count() > 0) {
        await stagingActions.first().screenshot({ path: path.join(IMAGES_DIR, '10-accept-reject.png') });
        console.log('  ✓ 10-accept-reject.png');
      }
    }
  }
}

async function captureFeaturesScreens() {
  console.log('\n[Features screenshots]');

  const divider = window.locator('.divider, .split-divider, .pane-divider, .resize-handle');
  if (await divider.count() > 0) {
    await divider.first().screenshot({ path: path.join(IMAGES_DIR, 'features-drag-divider.png') });
    console.log('  ✓ features-drag-divider.png');
  }

  const copyBtn = window.locator('.copy-title, [title*="Copy"], button:has-text("⎘"), [data-action="copy-title"]').first();
  if (await copyBtn.count() > 0) {
    await copyBtn.hover();
    await waitMs(300);
    const titleArea = window.locator('.post-title-area, .title-row, .post-header').first();
    if (await titleArea.count() > 0) {
      await titleArea.screenshot({ path: path.join(IMAGES_DIR, 'features-copy-title.png') });
      console.log('  ✓ features-copy-title.png');
    }
  }

  const themeBtn = window.locator('.theme-toggle, [title*="theme"], [title*="dark"], [title*="light"], button[title*="Theme"]');
  if (await themeBtn.count() > 0) {
    const toolbar = window.locator('.toolbar, .top-bar, #toolbar, header').first();
    if (await toolbar.count() > 0) {
      await toolbar.screenshot({ path: path.join(IMAGES_DIR, 'features-theme-toggle.png') });
      console.log('  ✓ features-theme-toggle.png');
    }
  }

  // Ingest panel screenshot — navigate to projects page
  const base = new URL(window.url()).origin;
  await window.goto(`${base}/ui/projects.html`);
  await window.waitForLoadState('domcontentloaded');
  await waitMs(500);
  await window.screenshot({ path: path.join(IMAGES_DIR, '03-ingest-panel.png') });
  console.log('  ✓ 03-ingest-panel.png');
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
    await navigateToMainApp();
    await captureMainAppScreens();
    await captureEditorScreens();
    await captureIssuesScreens();
    await captureSearchFilterScreens();
    await captureStagingScreens();
    await captureFeaturesScreens();
    console.log('\n✅  All screenshots saved to docs/user-guide/images/\n');
  } finally {
    await app.close();
  }
})();
