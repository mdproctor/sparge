// electron-tests/unit/refine-panel.test.js
const fs   = require('fs');
const path = require('path');

const src = fs.readFileSync(path.join(__dirname, '..', '..', 'ui', 'index.html'), 'utf8');

describe('refine panel — HTML structure', () => {
  test('#refine-panel element exists', () => {
    expect(src).toContain('id="refine-panel"');
  });

  test('#refine-suggestion-list element exists', () => {
    expect(src).toContain('id="refine-suggestion-list"');
  });

  test('#btn-add-all exists with onclick addAllSuggestions', () => {
    expect(src).toContain('id="btn-add-all"');
    expect(src).toContain('onclick="addAllSuggestions()"');
  });

  test('#btn-remove-all exists with onclick removeAllSuggestions', () => {
    expect(src).toContain('id="btn-remove-all"');
    expect(src).toContain('onclick="removeAllSuggestions()"');
  });

  test('#btn-accept-refined starts disabled', () => {
    expect(src).toMatch(/id="btn-accept-refined"[^>]*disabled/);
  });

  test('#ph-refine-badge badge element exists', () => {
    expect(src).toContain('ph-refine-badge');
  });
});

describe('refine panel — JavaScript functions', () => {
  test('toggleSuggestion function defined', () => {
    expect(src).toContain('function toggleSuggestion(');
  });

  test('addAllSuggestions function defined', () => {
    expect(src).toContain('function addAllSuggestions(');
  });

  test('removeAllSuggestions function defined', () => {
    expect(src).toContain('function removeAllSuggestions(');
  });

  test('acceptRefined function defined', () => {
    expect(src).toContain('function acceptRefined(');
  });

  test('renderRefinePanel function defined', () => {
    expect(src).toContain('function renderRefinePanel(');
  });

  test('refreshRefineDiff function defined', () => {
    expect(src).toContain('function refreshRefineDiff(');
  });

  test('openRefinePanel function defined', () => {
    expect(src).toContain('function openRefinePanel(');
  });

  test('closeRefinePanel function defined', () => {
    expect(src).toContain('function closeRefinePanel(');
  });
});

describe('refine panel — accept flow wiring', () => {
  test('acceptRefined POSTs to /refine/accept', () => {
    expect(src).toContain('/refine/accept');
  });

  test('refreshRefineDiff POSTs to /refine with accepted_checks', () => {
    expect(src).toContain('accepted_checks');
  });

  test('renderPanelBadges includes refinement badge logic', () => {
    expect(src).toContain('replay_conflicts');
    expect(src).toContain('✨ Refined');
  });

  test('enterRefineMode calls renderRefinePanel and openRefinePanel', () => {
    expect(src).toContain('renderRefinePanel()');
    expect(src).toContain('openRefinePanel()');
  });

  test('exitRefineMode calls closeRefinePanel', () => {
    expect(src).toContain('closeRefinePanel()');
  });
});

describe('refine panel — CSS', () => {
  test('.refine-row.removed has opacity 0.4', () => {
    expect(src).toMatch(/\.refine-row\.removed\s*\{[^}]*opacity:\s*0\.4/);
  });

  test('#refine-panel.hidden has display none', () => {
    expect(src).toMatch(/#refine-panel\.hidden\s*\{[^}]*display:\s*none/);
  });
});
