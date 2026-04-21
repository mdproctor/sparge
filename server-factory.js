// server-factory.js
'use strict';
const { PythonServer } = require('./python-server');
const { JavaServer }   = require('./java-server');

function createServer({ env = process.env, isPackaged = false, resourcesPath = '', pythonExe = null, serverScript = null } = {}) {
  if (env.SPARGE_SERVER === 'python') {
    return new PythonServer({ pythonExe, serverScript });
  }
  return new JavaServer({ isPackaged, resourcesPath });
}

module.exports = { createServer };
