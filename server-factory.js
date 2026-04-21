// server-factory.js
'use strict';
const { JavaServer } = require('./java-server');

function createServer({ env = process.env, isPackaged = false, resourcesPath = '' } = {}) {
  return new JavaServer({ isPackaged, resourcesPath });
}

module.exports = { createServer };
