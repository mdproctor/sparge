// electron-tests/unit/python-server.test.js
const { EventEmitter } = require('events');
jest.mock('child_process');

const { spawn }        = require('child_process');
const { PythonServer } = require('../../python-server');

function makeMockProcess() {
  const proc    = new EventEmitter();
  proc.stdout   = new EventEmitter();
  proc.stderr   = new EventEmitter();
  proc.kill     = jest.fn((signal) => Promise.resolve().then(() => proc.emit('exit', null, signal)));
  return proc;
}

function makeServer() {
  const server    = new PythonServer({ pythonExe: 'python3', serverScript: 'server.py' });
  server._pollFn  = jest.fn().mockResolvedValue(undefined); // inject mock poll
  return server;
}

beforeEach(() => jest.useFakeTimers());
afterEach(() => { jest.useRealTimers(); jest.clearAllMocks(); });

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
  await jest.advanceTimersByTimeAsync(1100); // BACKOFF_MS[0] = 1000ms
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

  procs[0].emit('exit', 1, null); // crash 1
  await jest.advanceTimersByTimeAsync(1100);
  expect(server._crashCount).toBe(1);

  await jest.advanceTimersByTimeAsync(61000); // stability period expires
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
