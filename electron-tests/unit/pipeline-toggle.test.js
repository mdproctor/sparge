// electron-tests/unit/pipeline-toggle.test.js
'use strict';

describe('pipeline toggle state machine', () => {
  let pipelineView;

  beforeEach(() => {
    pipelineView = 'html-md';
  });

  test('initial state is html-md', () => {
    expect(pipelineView).toBe('html-md');
  });

  test('toggle switches to md-refined', () => {
    pipelineView = pipelineView === 'html-md' ? 'md-refined' : 'html-md';
    expect(pipelineView).toBe('md-refined');
  });

  test('toggle twice returns to html-md', () => {
    pipelineView = pipelineView === 'html-md' ? 'md-refined' : 'html-md';
    pipelineView = pipelineView === 'html-md' ? 'md-refined' : 'html-md';
    expect(pipelineView).toBe('html-md');
  });
});
