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
    name:      'Docs Fixture',
    serve_root: fixtureRoot,
    posts_dir:  'posts',
    md_dir:     'md',
  });

  console.log('  project created:', JSON.stringify(project));

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

  // Open new project form — button is "+ New Project" (id="btn-toggle-form")
  const newBtn = window.locator('#btn-toggle-form');
  if (await newBtn.count() > 0) {
    await newBtn.first().click();
    await waitMs(400);
    // Form is in #new-form-wrap
    const form = window.locator('#new-form-wrap');
    if (await form.count() > 0) {
      await form.first().screenshot({ path: path.join(IMAGES_DIR, '02-new-project-form.png') });
      console.log('  ✓ 02-new-project-form.png');
    }
    // Close form — click toggle again
    await newBtn.first().click();
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

  // Post list — actual selector is #post-list or #nav
  await shot('#post-list', '04-post-list-mixed-states.png');

  // Config panel — button text is "⚙ Config", no title attr; opens #cfg-overlay
  const configBtn = window.locator('button:has-text("Config")');
  if (await configBtn.count() > 0) {
    await configBtn.first().click();
    await waitMs(400);
    // Panel is #cfg-panel inside #cfg-overlay
    const panel = window.locator('#cfg-panel');
    if (await panel.count() > 0) {
      await panel.first().screenshot({ path: path.join(IMAGES_DIR, '02-config-panel.png') });
      console.log('  ✓ 02-config-panel.png');
    }
    await window.keyboard.press('Escape');
    await waitMs(200);
  }

  // Click first post to open split pane — post items use class .pi and data-slug
  const postRow = window.locator('.pi').first();
  if (await postRow.count() > 0) {
    await postRow.click();
    await waitMs(800);
    await window.screenshot({ path: path.join(IMAGES_DIR, '05-split-pane-open.png') });
    console.log('  ✓ 05-split-pane-open.png');

    // Action buttons bar — #post-action-bar
    const actionBar = window.locator('#post-action-bar');
    if (await actionBar.count() > 0) {
      await actionBar.first().screenshot({ path: path.join(IMAGES_DIR, '05-action-buttons.png') });
      console.log('  ✓ 05-action-buttons.png');
    }

    // Post metadata — #nav-stats contains counts/stats
    const metaEl = window.locator('#nav-stats');
    if (await metaEl.count() > 0) {
      await metaEl.first().screenshot({ path: path.join(IMAGES_DIR, '05-post-metadata.png') });
      console.log('  ✓ 05-post-metadata.png');
    }
  }
}

async function captureEditorScreens() {
  console.log('\n[Editor screens]');

  const posts = await api('GET', '/api/posts');
  const cleanSlug  = posts.find(p => p.slug === 'intro-to-sparge')?.slug  || posts[0]?.slug;
  const issueSlug  = posts.find(p => p.slug === 'cloud-architecture')?.slug || posts[1]?.slug;
  const javaSlug   = posts.find(p => p.slug === 'java-virtual-threads')?.slug;
  const devopsSlug = posts.find(p => p.slug === 'devops-best-practices')?.slug;

  // Scan + generate MD for clean post — endpoint is /scan (not /scan-html)
  await api('POST', `/api/posts/${cleanSlug}/scan`);
  await waitMs(1000);
  await api('POST', `/api/posts/${cleanSlug}/generate-md`);
  await waitMs(500);

  // Navigate to clean post
  const cleanRow = window.locator(`[data-slug="${cleanSlug}"]`).first();
  if (await cleanRow.count() > 0) {
    await cleanRow.click();
    await waitMs(600);
  }

  // HTML panel — left pane is #html-panel
  const htmlPane = window.locator('#html-panel').first();
  if (await htmlPane.count() > 0) {
    await htmlPane.screenshot({ path: path.join(IMAGES_DIR, '06-html-editor.png') });
    console.log('  ✓ 06-html-editor.png');
  }

  // MD panel — right pane is #md-panel
  const mdPane = window.locator('#md-panel').first();
  if (await mdPane.count() > 0) {
    await mdPane.screenshot({ path: path.join(IMAGES_DIR, '07-md-editor.png') });
    console.log('  ✓ 07-md-editor.png');
  }

  // Scan issue post and navigate to it
  if (issueSlug) {
    await api('POST', `/api/posts/${issueSlug}/scan`);
    await waitMs(800);
    const issueRow = window.locator(`[data-slug="${issueSlug}"]`);
    if (await issueRow.count() > 0) {
      await issueRow.click();
      await waitMs(600);
      // Click first issue to trigger highlight — issues are in #html-issue-list .irow
      const firstIssue = window.locator('#html-issue-list .irow.clickable').first();
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
    await api('POST', `/api/posts/${devopsSlug}/scan`);
    await api('POST', `/api/posts/${devopsSlug}/generate-md`);
    await waitMs(800);
    await api('POST', `/api/posts/${devopsSlug}/stage`, { content: '# DevOps Best Practices\n\nThis is a staged draft for the documentation demo.\n\n## Continuous Integration\n\nRun your full test suite on every commit.\n' });
    await waitMs(300);
  }

  // Java post for validation issues screenshot
  if (javaSlug) {
    await api('POST', `/api/posts/${javaSlug}/scan`);
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

  // Open issues panel — button is #btn-issues with title "Show/hide issue panel"
  const issuesPanelBtn = window.locator('#btn-issues');
  if (await issuesPanelBtn.count() > 0) {
    await issuesPanelBtn.first().click();
    await waitMs(300);
  }

  // Issues panel is #issue-panel
  const issuesPanel = window.locator('#issue-panel');
  if (await issuesPanel.count() > 0) {
    await issuesPanel.first().screenshot({ path: path.join(IMAGES_DIR, '08-issues-panel.png') });
    console.log('  ✓ 08-issues-panel.png');

    // Hover to reveal dismiss button — issues are .irow.clickable in #html-issue-list
    const issueItem = window.locator('#html-issue-list .irow.clickable').first();
    if (await issueItem.count() > 0) {
      await issueItem.hover();
      await waitMs(200);
      await issuesPanel.first().screenshot({ path: path.join(IMAGES_DIR, '08-dismiss-flow.png') });
      console.log('  ✓ 08-dismiss-flow.png');

      // Click issue to highlight in editor
      await issueItem.click();
      await waitMs(300);
      const htmlPane = window.locator('#html-panel').first();
      if (await htmlPane.count() > 0) {
        await htmlPane.screenshot({ path: path.join(IMAGES_DIR, '08-issue-highlighted.png') });
        console.log('  ✓ 08-issue-highlighted.png');
      }
    }
  }

  // Issue breakdown stats — #html-breakdown or nav-stats breakdown
  const breakdown = window.locator('#html-breakdown, #md-breakdown');
  if (await breakdown.count() > 0 && await breakdown.first().isVisible()) {
    await breakdown.first().screenshot({ path: path.join(IMAGES_DIR, '08-issue-breakdown.png') });
    console.log('  ✓ 08-issue-breakdown.png');
  }
}

async function captureSearchFilterScreens() {
  console.log('\n[Search and filter screens]');

  // There is no text search input — filtering uses .fb buttons in .filter-zone
  // Click an active filter button to show filtered state
  const filterBtn = window.locator('.filter-zone .fb').first();
  if (await filterBtn.count() > 0) {
    // Screenshot the filter zone (which shows All/HTML-issues/MD-issues buttons)
    const filterZone = window.locator('.filter-zone');
    if (await filterZone.count() > 0) {
      await filterZone.first().screenshot({ path: path.join(IMAGES_DIR, '09-filter-buttons.png') });
      console.log('  ✓ 09-filter-buttons.png');
    }

    // Click "HTML⚠" filter to show filtered list
    const htmlFilter = window.locator('.filter-zone .fb:has-text("HTML")');
    if (await htmlFilter.count() > 0) {
      await htmlFilter.first().click();
      await waitMs(400);
      await window.screenshot({ path: path.join(IMAGES_DIR, '09-search-active.png') });
      console.log('  ✓ 09-search-active.png');
      // Reset to All
      const allFilter = window.locator('.filter-zone .fb:has-text("All")');
      if (await allFilter.count() > 0) await allFilter.first().click();
      await waitMs(300);
    }
  }

  // Post list screenshot after reset
  const postList = window.locator('#post-list').first();
  if (await postList.count() > 0) {
    await postList.screenshot({ path: path.join(IMAGES_DIR, '09-filtered-list.png') });
    console.log('  ✓ 09-filtered-list.png');
  }

  // Author select (scope dropdown)
  const scopeEl = window.locator('#author-select');
  if (await scopeEl.count() > 0) {
    const filterZone = window.locator('.filter-zone');
    if (await filterZone.count() > 0) {
      await filterZone.first().screenshot({ path: path.join(IMAGES_DIR, 'features-search-scope.png') });
      console.log('  ✓ features-search-scope.png');
    }
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
      // MD panel is #md-panel
      const mdPane = window.locator('#md-panel').first();
      if (await mdPane.count() > 0) {
        await mdPane.screenshot({ path: path.join(IMAGES_DIR, '10-staged-state.png') });
        console.log('  ✓ 10-staged-state.png');
      }
      // Staging actions — "Review Staged" button is #btn-staged
      const stagingActions = window.locator('#btn-staged');
      if (await stagingActions.count() > 0 && await stagingActions.first().isVisible()) {
        await stagingActions.first().screenshot({ path: path.join(IMAGES_DIR, '10-accept-reject.png') });
        console.log('  ✓ 10-accept-reject.png');
      }
    }
  } else {
    console.log('  (no staged post found — skipping staging screenshots)');
  }
}

async function captureFeaturesScreens() {
  console.log('\n[Features screenshots]');

  // Divider between html-panel and md-panel is #divider
  const divider = window.locator('#divider');
  if (await divider.count() > 0) {
    await divider.first().screenshot({ path: path.join(IMAGES_DIR, 'features-drag-divider.png') });
    console.log('  ✓ features-drag-divider.png');
  }

  // Copy title button — .pi-copy inside post list items
  const copyBtn = window.locator('.pi-copy').first();
  if (await copyBtn.count() > 0) {
    await copyBtn.hover();
    await waitMs(300);
    // Screenshot a post list item to show copy button
    const piItem = window.locator('.pi').first();
    if (await piItem.count() > 0) {
      await piItem.screenshot({ path: path.join(IMAGES_DIR, 'features-copy-title.png') });
      console.log('  ✓ features-copy-title.png');
    }
  }

  // Theme toggle — #btn-editor-theme (in edit sidebar); toolbar is in the app header
  const toolbar = window.locator('#topbar, header').first();
  if (await toolbar.count() > 0) {
    await toolbar.screenshot({ path: path.join(IMAGES_DIR, 'features-theme-toggle.png') });
    console.log('  ✓ features-theme-toggle.png');
  }

  // Ingest panel screenshot — navigate to projects page
  const base = new URL(window.url()).origin;
  await window.goto(`${base}/ui/projects.html`);
  await window.waitForLoadState('domcontentloaded');
  await waitMs(500);
  await window.screenshot({ path: path.join(IMAGES_DIR, '03-ingest-panel.png') });
  console.log('  ✓ 03-ingest-panel.png');
}

// ── missing screenshots ────────────────────────────────────────────────────

// Directly inject HTML issues into the project state.json on disk.
// This avoids running a live scan so screenshots are deterministic
// and don't depend on network access or enriched HTML being present on disk.
function injectHtmlIssues(projectsDir, projectId, slug, issues) {
  const statePath = path.join(projectsDir, projectId, 'state.json');
  if (!fs.existsSync(statePath)) {
    console.log(`  [warn] state.json not found at ${statePath}`);
    return;
  }
  const state = JSON.parse(fs.readFileSync(statePath, 'utf8'));
  if (!state[slug]) {
    console.log(`  [warn] slug ${slug} not found in state.json`);
    return;
  }
  state[slug].html = state[slug].html || {};
  state[slug].html.issues = issues;
  state[slug].html.scanned_at = new Date().toISOString();
  fs.writeFileSync(statePath, JSON.stringify(state, null, 2));
  console.log(`  [inject] wrote ${issues.length} HTML issue(s) for ${slug} into state.json`);
}

// Inject staged MD info into state.json and write the MD files to disk
function injectStagedMd(projectsDir, projectId, fixtureRoot, slug, mdContent, stagedContent) {
  const statePath  = path.join(projectsDir, projectId, 'state.json');
  const mdDir      = path.join(fixtureRoot, 'md');
  const mdFile     = path.join(mdDir, `${slug}.md`);
  const stagedFile = path.join(mdDir, `${slug}.md.staged`);

  fs.mkdirSync(mdDir, { recursive: true });
  fs.writeFileSync(mdFile,     mdContent,     'utf8');
  fs.writeFileSync(stagedFile, stagedContent, 'utf8');

  if (!fs.existsSync(statePath)) {
    console.log(`  [warn] state.json not found at ${statePath}`);
    return;
  }
  const state = JSON.parse(fs.readFileSync(statePath, 'utf8'));
  if (!state[slug]) {
    console.log(`  [warn] slug ${slug} not found in state.json`);
    return;
  }
  const now = new Date().toISOString();
  state[slug].md = state[slug].md || {};
  state[slug].md.generated_at = now;
  state[slug].md.staged        = stagedContent;
  state[slug].md.staged_at     = now;
  fs.writeFileSync(statePath, JSON.stringify(state, null, 2));
  console.log(`  [inject] wrote staged MD for ${slug} into state.json + md/ dir`);
}

async function captureMissingScreenshots() {
  console.log('\n[Missing screenshots]');

  // Projects live at ~/sparge-projects (or whatever ~/.sparge/config.json says)
  // For tests we rely on the default; the fixture project ID is always 'docs-fixture'
  const projectsDir  = path.join(os.homedir(), 'sparge-projects');
  const projectId    = 'docs-fixture';
  const fixtureRoot  = path.join(os.tmpdir(), 'sparge-docs-fixture');

  const posts     = await api('GET', '/api/posts');
  const issueSlug  = posts.find(p => p.slug === 'cloud-architecture')?.slug;
  const devopsSlug = posts.find(p => p.slug === 'devops-best-practices')?.slug;

  // ── 1. Inject HTML issues directly into state.json for cloud-architecture ─
  // Inject state directly rather than running a live scan, so screenshots are
  // deterministic and don't depend on network access or enriched HTML on disk.
  if (issueSlug) {
    injectHtmlIssues(projectsDir, projectId, issueSlug, [
      {
        type:     'external_image',
        check:    'external_image',
        level:    'WARN',
        detail:   'Image not localised: https://cdn.example.com/diagrams/cloud-architecture.png',
        selector: 'div:nth-of-type(2) > img',
      },
      {
        type:     'missing_image_signal',
        check:    'missing_image_signal',
        level:    'WARN',
        detail:   'Text signals missing image: "As shown above, services communicate..."',
        selector: 'div:nth-of-type(2) > p:nth-of-type(2)',
      },
    ]);

    // Reload the page so the UI picks up the updated state
    await navigateToMainApp();

    // Click the cloud-architecture post row
    const issueRow = window.locator(`[data-slug="${issueSlug}"]`);
    if (await issueRow.count() > 0) {
      await issueRow.click();
      await waitMs(800);
    }

    // Open the issues panel — ensure it's visible
    const issuesPanelBtn = window.locator('#btn-issues');
    if (await issuesPanelBtn.count() > 0) {
      const panel   = window.locator('#issue-panel');
      const isHidden = await panel.first().evaluate(el => el.classList.contains('hidden')).catch(() => true);
      if (isHidden) {
        await issuesPanelBtn.first().click();
        await waitMs(400);
      }
    }

    const htmlPane    = window.locator('#html-panel').first();
    const issuesPanel = window.locator('#issue-panel').first();

    // 06-issue-highlight.png — click first clickable HTML issue → highlight in HTML pane
    const firstIssue = window.locator('#html-issue-list .irow.clickable').first();

    if (await firstIssue.count() > 0) {
      await firstIssue.click();
      await waitMs(600);
      if (await htmlPane.count() > 0) {
        await htmlPane.screenshot({ path: path.join(IMAGES_DIR, '06-issue-highlight.png') });
        console.log('  ✓ 06-issue-highlight.png');
      }

      // 08-issue-highlighted.png — same highlighted state, screenshot html pane again
      if (await htmlPane.count() > 0) {
        await htmlPane.screenshot({ path: path.join(IMAGES_DIR, '08-issue-highlighted.png') });
        console.log('  ✓ 08-issue-highlighted.png');
      }
    } else {
      console.log('  ✗ 06-issue-highlight.png — no clickable HTML issue rows found');
      console.log('  ✗ 08-issue-highlighted.png — no clickable HTML issue rows found');
    }

    // 08-dismiss-flow.png — hover over first issue row (shows hover styling), screenshot panel
    if (await issuesPanel.count() > 0) {
      const anyIssueRow = window.locator('#html-issue-list .irow').first();
      if (await anyIssueRow.count() > 0) {
        await anyIssueRow.hover();
        await waitMs(300);
        await issuesPanel.screenshot({ path: path.join(IMAGES_DIR, '08-dismiss-flow.png') });
        console.log('  ✓ 08-dismiss-flow.png');
      } else {
        console.log('  ✗ 08-dismiss-flow.png — no issue rows in panel');
      }
    }
  }

  // 08-issue-breakdown.png — click the "HTML issues" expandable stat row to reveal breakdown
  const expandableRow = window.locator('.srow.expandable').first();
  if (await expandableRow.count() > 0) {
    const breakdownEl = window.locator('#html-breakdown').first();
    const alreadyOpen = await breakdownEl.evaluate(el => el.style.display !== 'none').catch(() => false);
    if (!alreadyOpen) {
      await expandableRow.click();
      await waitMs(400);
    }
    const navStats = window.locator('#nav-stats').first();
    if (await navStats.count() > 0) {
      await navStats.screenshot({ path: path.join(IMAGES_DIR, '08-issue-breakdown.png') });
      console.log('  ✓ 08-issue-breakdown.png');
    } else {
      console.log('  ✗ 08-issue-breakdown.png — #nav-stats not found');
    }
  } else {
    console.log('  ✗ 08-issue-breakdown.png — no expandable stat row found');
  }

  // ── 2. Inject staged MD for devops post and capture accept/reject buttons ─
  if (devopsSlug) {
    const savedMd = '# DevOps Best Practices\n\nAutomate everything. Test on every commit.\n\n## Continuous Integration\n\nRun your full test suite on every commit.\n';
    const stagedMd = '# DevOps Best Practices\n\nThis is a staged draft for review.\n\n## Continuous Integration\n\nRun your full test suite on every commit.\n\n## Continuous Delivery\n\nEvery passing build should be deployable to production.\n';

    injectStagedMd(projectsDir, projectId, fixtureRoot, devopsSlug, savedMd, stagedMd);

    // Reload the page so staged state is reflected in the UI
    await navigateToMainApp();

    // Navigate to the devops post
    const devopsRow = window.locator(`[data-slug="${devopsSlug}"]`);
    if (await devopsRow.count() > 0) {
      await devopsRow.click();
      await waitMs(800);
    }

    // Click "Review Staged" button to open the diff modal
    const reviewStagedBtn = window.locator('#btn-staged');
    const btnVisible = await reviewStagedBtn.count() > 0 && await reviewStagedBtn.first().isVisible();

    if (btnVisible) {
      await reviewStagedBtn.first().click();
      await waitMs(2000);

      // The modal opens by adding class 'open'
      const diffModal = window.locator('#diff-modal');
      const modalOpen = await diffModal.first().evaluate(el => el.classList.contains('open')).catch(() => false);

      if (modalOpen) {
        // Screenshot the diff footer which contains Reject + Accept buttons
        const diffFtr = window.locator('#diff-ftr').first();
        if (await diffFtr.count() > 0) {
          await diffFtr.screenshot({ path: path.join(IMAGES_DIR, '10-accept-reject.png') });
          console.log('  ✓ 10-accept-reject.png');
        }
        // Close the modal
        const diffClose = window.locator('#diff-close');
        if (await diffClose.count() > 0 && await diffClose.first().isVisible()) {
          await diffClose.first().click();
          await waitMs(300);
        }
      } else {
        console.log('  ✗ 10-accept-reject.png — diff modal did not open');
      }
    } else {
      console.log('  ✗ 10-accept-reject.png — #btn-staged not visible');
    }
  } else {
    console.log('  ✗ 10-accept-reject.png — devops-best-practices post not found');
  }
}

// ── main ───────────────────────────────────────────────────────────────────

(async () => {
  console.log('\n📸  Sparge docs — missing screenshots\n');
  fs.mkdirSync(IMAGES_DIR, { recursive: true });

  app    = await electron.launch({ args: [path.join(ROOT, 'main.js')] });
  window = await app.firstWindow();
  await window.waitForLoadState('domcontentloaded');
  await waitMs(2000);

  try {
    await captureProjectsScreen();
    await setupFixtureProject();
    await navigateToMainApp();
    await captureMissingScreenshots();
    console.log('\n✅  Missing screenshots captured to docs/user-guide/images/\n');
  } finally {
    await app.close();
  }
})();
