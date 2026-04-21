// electron-tests/integration/java-server.integration.test.js
jest.setTimeout(60000);

const http = require('http');
const { JavaServer, findFreePort } = require('../../java-server');

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
  const server = new JavaServer({ isPackaged: false });
  await server.spawnServer(port);
  expect(server._state).toBe('healthy');
  const config = await getJson(port, '/api/config');
  expect(config).toHaveProperty('server');
  await server.killServer();
  expect(server._state).toBe('idle');
});

test('crash recovery: SIGKILL → restarted event → healthy again', async () => {
  const port   = await findFreePort();
  const server = new JavaServer({ isPackaged: false });
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
  const server = new JavaServer({ isPackaged: false });
  await server.spawnServer(port);
  await server.killServer();
  expect(server._state).toBe('idle');
});

test('fatal: 3 restarts exhausted → fatal event, no further attempts', async () => {
  const port   = await findFreePort();
  const server = new JavaServer({ isPackaged: false });
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
  if (server._stabilityTimer) clearTimeout(server._stabilityTimer);
});
