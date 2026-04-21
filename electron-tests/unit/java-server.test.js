// electron-tests/unit/java-server.test.js
'use strict';
const { EventEmitter } = require('events');
const path             = require('path');
jest.mock('child_process');

const { spawn }      = require('child_process');
const { JavaServer } = require('../../java-server');

function makeMockProcess() {
  const proc  = new EventEmitter();
  proc.stdout = new EventEmitter();
  proc.stderr = new EventEmitter();
  proc.kill   = jest.fn((signal) => Promise.resolve().then(() => proc.emit('exit', null, signal)));
  return proc;
}

function makeServer() {
  const server   = new JavaServer({ isPackaged: false });
  server._pollFn = jest.fn().mockResolvedValue(undefined);
  return server;
}

beforeEach(() => jest.useFakeTimers());
afterEach(() => { jest.useRealTimers(); jest.clearAllMocks(); });

// ── Lifecycle (regression guards) ────────────────────────────────────────────

test('starts idle, reaches healthy after spawnServer', async () => {
  spawn.mockReturnValue(makeMockProcess());
  const server = makeServer();
  expect(server._state).toBe('idle');
  await server.spawnServer(19001);
  expect(server._state).toBe('healthy');
});

test('emits crashed then restarted after unexpected exit', async () => {
  const proc1 = makeMockProcess();
  const proc2 = makeMockProcess();
  spawn.mockReturnValueOnce(proc1).mockReturnValueOnce(proc2);

  const server = makeServer();
  await server.spawnServer(19002);

  const events = [];
  server.on('crashed',   () => events.push('crashed'));
  server.on('restarted', () => events.push('restarted'));

  proc1.emit('exit', 1, null);
  expect(server._state).toBe('crashed');
  await jest.advanceTimersByTimeAsync(1100);
  expect(events).toEqual(['crashed', 'restarted']);
  expect(server._state).toBe('healthy');
});

test('emits fatal after MAX_RESTARTS consecutive crashes', async () => {
  const procs = [0, 1, 2, 3].map(() => makeMockProcess());
  procs.forEach(p => spawn.mockReturnValueOnce(p));

  const server = makeServer();
  await server.spawnServer(19003);

  const events = [];
  server.on('fatal', () => events.push('fatal'));

  procs[0].emit('exit', 1, null);
  await jest.advanceTimersByTimeAsync(1100);
  procs[1].emit('exit', 1, null);
  await jest.advanceTimersByTimeAsync(2100);
  procs[2].emit('exit', 1, null);
  await jest.advanceTimersByTimeAsync(4100);
  procs[3].emit('exit', 1, null);

  expect(events).toContain('fatal');
  expect(server._state).toBe('fatal');
});

test('crash counter resets after stability period (60s)', async () => {
  const procs = [0, 1].map(() => makeMockProcess());
  procs.forEach(p => spawn.mockReturnValueOnce(p));

  const server = makeServer();
  await server.spawnServer(19004);

  procs[0].emit('exit', 1, null);
  await jest.advanceTimersByTimeAsync(1100);
  expect(server._crashCount).toBe(1);

  await jest.advanceTimersByTimeAsync(61000);
  expect(server._crashCount).toBe(0);
});

test('killServer sends SIGTERM and resolves', async () => {
  spawn.mockReturnValue(makeMockProcess());
  const server = makeServer();
  await server.spawnServer(19005);
  const killPromise = server.killServer();
  expect(server._process.kill).toHaveBeenCalledWith('SIGTERM');
  await killPromise;
  expect(server._state).toBe('idle');
});

test('getLogs returns captured stdout + stderr lines', async () => {
  const proc = makeMockProcess();
  spawn.mockReturnValue(proc);
  const server = makeServer();
  await server.spawnServer(19006);
  proc.stdout.emit('data', 'line one\nline two\n');
  proc.stderr.emit('data', 'error line\n');
  expect(server.getLogs()).toEqual(['line one', 'line two', 'error line']);
});

// ── Spawn environment — no JEP/Python env vars ───────────────────────────────

test('_doSpawn does not inject PYTHONHOME into child process environment', async () => {
  const saved = process.env.PYTHONHOME;
  delete process.env.PYTHONHOME;
  try {
    spawn.mockReturnValue(makeMockProcess());
    const server = makeServer();
    await server.spawnServer(19010);
    const [, , opts] = spawn.mock.calls[0];
    expect(opts.env).not.toHaveProperty('PYTHONHOME');
  } finally {
    if (saved !== undefined) process.env.PYTHONHOME = saved;
  }
});

test('_doSpawn does not inject DYLD_LIBRARY_PATH into child process environment', async () => {
  const saved = process.env.DYLD_LIBRARY_PATH;
  delete process.env.DYLD_LIBRARY_PATH;
  try {
    spawn.mockReturnValue(makeMockProcess());
    const server = makeServer();
    await server.spawnServer(19011);
    const [, , opts] = spawn.mock.calls[0];
    expect(opts.env).not.toHaveProperty('DYLD_LIBRARY_PATH');
  } finally {
    if (saved !== undefined) process.env.DYLD_LIBRARY_PATH = saved;
  }
});

test('_doSpawn does not inject LD_LIBRARY_PATH into child process environment', async () => {
  const saved = process.env.LD_LIBRARY_PATH;
  delete process.env.LD_LIBRARY_PATH;
  try {
    spawn.mockReturnValue(makeMockProcess());
    const server = makeServer();
    await server.spawnServer(19012);
    const [, , opts] = spawn.mock.calls[0];
    expect(opts.env).not.toHaveProperty('LD_LIBRARY_PATH');
  } finally {
    if (saved !== undefined) process.env.LD_LIBRARY_PATH = saved;
  }
});

// ── Spawn JVM args — minimal, no java.library.path ───────────────────────────

test('_doSpawn JVM args are exactly [-Dquarkus.http.port, -jar, jarPath]', async () => {
  spawn.mockReturnValue(makeMockProcess());
  const server = makeServer();
  await server.spawnServer(19013);
  const [cmd, args] = spawn.mock.calls[0];
  expect(cmd).toBe('java');
  expect(args).toHaveLength(3);
  expect(args[0]).toBe('-Dquarkus.http.port=19013');
  expect(args[1]).toBe('-jar');
  expect(args[2]).toMatch(/sparge-server-runner\.jar$/);
});

test('dev jar path resolves to sparge-server-runner.jar inside server/target', async () => {
  spawn.mockReturnValue(makeMockProcess());
  const server = makeServer(); // isPackaged: false
  await server.spawnServer(19015);
  const [, args] = spawn.mock.calls[0];
  expect(args[2]).toMatch(/server[/\\]target[/\\]sparge-server-runner\.jar$/);
});

test('packaged jar path resolves to sparge-server-runner.jar inside resourcesPath', async () => {
  spawn.mockReturnValue(makeMockProcess());
  const server = new JavaServer({ isPackaged: true, resourcesPath: '/fake/resources' });
  server._pollFn = jest.fn().mockResolvedValue(undefined);
  await server.spawnServer(19016);
  const [, args] = spawn.mock.calls[0];
  expect(args[2]).toBe(path.join('/fake/resources', 'sparge-server-runner.jar'));
});

test('_doSpawn JVM args contain no java.library.path flag', async () => {
  spawn.mockReturnValue(makeMockProcess());
  const server = makeServer();
  await server.spawnServer(19014);
  const [, args] = spawn.mock.calls[0];
  expect(args.join(' ')).not.toContain('java.library.path');
});
