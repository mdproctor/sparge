// electron-tests/unit/server-factory.test.js
'use strict';
jest.mock('../../python-server');
jest.mock('../../java-server');

const { PythonServer } = require('../../python-server');
const { JavaServer }   = require('../../java-server');
const { createServer } = require('../../server-factory');

beforeEach(() => jest.clearAllMocks());

// ── Default: Java ─────────────────────────────────────────────────────────────

test('returns JavaServer when SPARGE_SERVER is unset', () => {
  createServer({ env: {} });
  expect(JavaServer).toHaveBeenCalledTimes(1);
  expect(PythonServer).not.toHaveBeenCalled();
});

test('returns JavaServer when SPARGE_SERVER=java (legacy opt-in, now just default)', () => {
  createServer({ env: { SPARGE_SERVER: 'java' } });
  expect(JavaServer).toHaveBeenCalledTimes(1);
  expect(PythonServer).not.toHaveBeenCalled();
});

test('returns JavaServer for any unrecognised SPARGE_SERVER value', () => {
  createServer({ env: { SPARGE_SERVER: 'foobar' } });
  expect(JavaServer).toHaveBeenCalledTimes(1);
  expect(PythonServer).not.toHaveBeenCalled();
});

// ── Explicit Python opt-out ───────────────────────────────────────────────────

test('returns PythonServer when SPARGE_SERVER=python', () => {
  createServer({ env: { SPARGE_SERVER: 'python' }, pythonExe: 'python3', serverScript: 'server.py' });
  expect(PythonServer).toHaveBeenCalledTimes(1);
  expect(JavaServer).not.toHaveBeenCalled();
});

// ── Parameter forwarding ──────────────────────────────────────────────────────

test('passes isPackaged and resourcesPath to JavaServer', () => {
  createServer({ env: {}, isPackaged: true, resourcesPath: '/res' });
  expect(JavaServer).toHaveBeenCalledWith({ isPackaged: true, resourcesPath: '/res' });
});

test('passes pythonExe and serverScript to PythonServer', () => {
  createServer({ env: { SPARGE_SERVER: 'python' }, pythonExe: 'python3', serverScript: '/srv.py' });
  expect(PythonServer).toHaveBeenCalledWith({ pythonExe: 'python3', serverScript: '/srv.py' });
});
