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

class PythonServer extends EventEmitter {
  constructor({ pythonExe, serverScript }) {
    super();
    this._pythonExe    = pythonExe;
    this._serverScript = serverScript;
    this._port         = null;
    this._process      = null;
    this._state        = 'idle';
    this._logs         = [];
    this._crashCount   = 0;
    this._stabilityTimer = null;
    this._pollFn       = pollUntilReady; // injectable for tests
  }

  getPort() { return this._port; }
  getLogs() { return [...this._logs]; }

  async spawnServer(port) {
    this._port  = port;
    this._state = 'starting';
    this._doSpawn();
    await this._pollFn(port);
    this._state = 'healthy';
    this._resetStabilityTimer();
  }

  _doSpawn() {
    this._process = spawn(this._pythonExe, [this._serverScript, '--port', String(this._port)]);
    this._process.stdout.on('data', d => this._appendLog(d.toString()));
    this._process.stderr.on('data', d => this._appendLog(d.toString()));
    this._process.on('exit', (code, signal) => this._onExit(code, signal));
  }

  _appendLog(text) {
    const lines = text.split('\n').filter(l => l.length > 0);
    this._logs.push(...lines);
    if (this._logs.length > LOG_BUFFER_SIZE) this._logs = this._logs.slice(-LOG_BUFFER_SIZE);
  }

  _resetStabilityTimer() {
    if (this._stabilityTimer) clearTimeout(this._stabilityTimer);
    this._stabilityTimer = setTimeout(() => { this._crashCount = 0; }, STABILITY_RESET_MS);
  }

  _onExit(code, signal) {
    if (this._state === 'idle') return;
    this._state = 'crashed';
    this.emit('crashed', { code, signal });
    this._crashCount++;
    if (this._crashCount > MAX_RESTARTS) {
      this._state = 'fatal';
      this.emit('fatal', { logs: this.getLogs() });
      return;
    }
    const delay = BACKOFF_MS[Math.min(this._crashCount - 1, BACKOFF_MS.length - 1)];
    setTimeout(() => this._restart(), delay);
  }

  async _restart() {
    this._state = 'restarting';
    this._doSpawn();
    try {
      await this._pollFn(this._port);
      this._state = 'healthy';
      this.emit('restarted');
      this._resetStabilityTimer();
    } catch (_) {
      // _onExit will handle the next failure
    }
  }

  async killServer() {
    this._state = 'idle';
    if (this._stabilityTimer) clearTimeout(this._stabilityTimer);
    if (!this._process) return;
    return new Promise((resolve) => {
      const timer = setTimeout(() => { this._process.kill('SIGKILL'); resolve(); }, 3000);
      this._process.once('exit', () => { clearTimeout(timer); resolve(); });
      this._process.kill('SIGTERM');
    });
  }
}

module.exports = { PythonServer, findFreePort, pollUntilReady };
