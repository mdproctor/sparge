// electron-tests/integration/python-server.integration.test.js
jest.setTimeout(30000);

const http = require('http');
const path = require('path');
const { PythonServer, findFreePort } = require('../../python-server');

const PYTHON_EXE    = process.env.PYTHON_EXE || 'python3';
const SERVER_SCRIPT = path.join(__dirname, '..', '..', 'server.py');

function getJson(port, route) {
  return new Promise((resolve, reject) => {
    http.get(`http://127.0.0.1:${port}${route}`, (res) => {
      let body = '';
      res.on('data', d => body += d);
      res.on('end', () => resolve(JSON.parse(body)));
    }).on('error', reject);
  });
}

test('happy path: spawnServer reaches healthy, /api/config returns JSON', async () => {
  const port   = await findFreePort();
  const server = new PythonServer({ pythonExe: PYTHON_EXE, serverScript: SERVER_SCRIPT });
  await server.spawnServer(port);
  expect(server._state).toBe('healthy');
  const config = await getJson(port, '/api/config');
  expect(config).toHaveProperty('server');
  await server.killServer();
  expect(server._state).toBe('idle');
});

test('crash recovery: SIGKILL → restarted event → healthy again', async () => {
  const port   = await findFreePort();
  const server = new PythonServer({ pythonExe: PYTHON_EXE, serverScript: SERVER_SCRIPT });
  await server.spawnServer(port);

  const restarted = new Promise(resolve => server.once('restarted', resolve));
  server._process.kill('SIGKILL');
  await restarted;

  expect(server._state).toBe('healthy');
  const config = await getJson(port, '/api/config');
  expect(config).toHaveProperty('server');
  await server.killServer();
});

test('graceful shutdown: killServer resolves, state is idle', async () => {
  const port   = await findFreePort();
  const server = new PythonServer({ pythonExe: PYTHON_EXE, serverScript: SERVER_SCRIPT });
  await server.spawnServer(port);
  await server.killServer();
  expect(server._state).toBe('idle');
});

test('fatal: 3 restarts exhausted → fatal event, no further attempts', async () => {
  const port   = await findFreePort();
  const server = new PythonServer({ pythonExe: PYTHON_EXE, serverScript: SERVER_SCRIPT });
  await server.spawnServer(port);

  const fatal = new Promise(resolve => server.once('fatal', resolve));
  const killLoop = () => {
    if (server._process && server._state !== 'fatal') {
      server._process.kill('SIGKILL');
      setTimeout(killLoop, 400);
    }
  };
  killLoop();
  await fatal;
  expect(server._state).toBe('fatal');
  // Clear any pending stability timer so Jest can exit cleanly.
  if (server._stabilityTimer) clearTimeout(server._stabilityTimer);
});
