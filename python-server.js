// python-server.js
'use strict';
const { spawn }        = require('child_process');
const http             = require('http');
const net              = require('net');
const { EventEmitter } = require('events');

const MAX_RESTARTS       = 3;
const STABILITY_RESET_MS = 60_000;
const BACKOFF_MS         = [1000, 2000, 4000];
const LOG_BUFFER_SIZE    = 200;

function findFreePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.listen(0, '127.0.0.1', () => {
      const { port } = server.address();
      server.close(() => resolve(port));
    });
    server.on('error', reject);
  });
}

function pollUntilReady(port, { intervalMs = 200, timeoutMs = 15000 } = {}) {
  return new Promise((resolve, reject) => {
    const deadline = Date.now() + timeoutMs;
    const attempt = () => {
      if (Date.now() >= deadline) {
        reject(new Error(`Server did not start within ${timeoutMs}ms`));
        return;
      }
      const req = http.get(`http://127.0.0.1:${port}/api/config`, (res) => {
        res.resume();
        if (res.statusCode === 200) resolve();
        else setTimeout(attempt, intervalMs);
      });
      req.on('error', () => setTimeout(attempt, intervalMs));
      req.setTimeout(intervalMs, () => { req.destroy(); });
    };
    attempt();
  });
}

// PythonServer class — fully implemented in Task 5
class PythonServer extends EventEmitter {}

module.exports = { PythonServer, findFreePort, pollUntilReady };
