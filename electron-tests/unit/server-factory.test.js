// electron-tests/unit/server-factory.test.js
'use strict';
jest.mock('../../java-server');

const { JavaServer }   = require('../../java-server');
const { createServer } = require('../../server-factory');

beforeEach(() => jest.clearAllMocks());

// ── Always Java ───────────────────────────────────────────────────────────────

test('returns JavaServer when SPARGE_SERVER is unset', () => {
  createServer({ env: {} });
  expect(JavaServer).toHaveBeenCalledTimes(1);
});

test('returns JavaServer when SPARGE_SERVER=java (legacy value)', () => {
  createServer({ env: { SPARGE_SERVER: 'java' } });
  expect(JavaServer).toHaveBeenCalledTimes(1);
});

test('returns JavaServer for any unrecognised SPARGE_SERVER value', () => {
  createServer({ env: { SPARGE_SERVER: 'foobar' } });
  expect(JavaServer).toHaveBeenCalledTimes(1);
});

test('SPARGE_SERVER=python is ignored — Python opt-out removed, always Java', () => {
  createServer({ env: { SPARGE_SERVER: 'python' } });
  expect(JavaServer).toHaveBeenCalledTimes(1);
});

// ── Parameter forwarding ──────────────────────────────────────────────────────

test('passes isPackaged and resourcesPath to JavaServer', () => {
  createServer({ env: {}, isPackaged: true, resourcesPath: '/res' });
  expect(JavaServer).toHaveBeenCalledWith({ isPackaged: true, resourcesPath: '/res' });
});
