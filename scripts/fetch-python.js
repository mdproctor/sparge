// scripts/fetch-python.js
'use strict';
const https  = require('https');
const fs     = require('fs');
const path   = require('path');
const crypto = require('crypto');
const { execSync } = require('child_process');

const PYTHON_VERSION = '3.12.10';
const STANDALONE_TAG = '20250409';
const BASE_URL = 'https://github.com/astral-sh/python-build-standalone/releases/download';

const PLATFORM_MAP = {
  'darwin-arm64': { dir: 'mac-arm64', arch: 'aarch64-apple-darwin',     ext: 'tar.gz' },
  'darwin-x64':   { dir: 'mac-x64',   arch: 'x86_64-apple-darwin',      ext: 'tar.gz' },
  'win32-x64':    { dir: 'win-x64',   arch: 'x86_64-pc-windows-msvc-shared',   ext: 'zip'    },
  'linux-x64':    { dir: 'linux-x64', arch: 'x86_64-unknown-linux-gnu', ext: 'tar.gz' },
};

function _key(platform, arch) { return `${platform}-${arch}`; }

function getPlatformDir(platform, arch) {
  const info = PLATFORM_MAP[_key(platform, arch)];
  if (!info) throw new Error(`Unsupported platform: ${_key(platform, arch)}`);
  return info.dir;
}

function getDownloadUrl(platform, arch) {
  const info = PLATFORM_MAP[_key(platform, arch)];
  if (!info) throw new Error(`Unsupported platform: ${_key(platform, arch)}`);
  const filename = `cpython-${PYTHON_VERSION}+${STANDALONE_TAG}-${info.arch}-install_only_stripped.${info.ext}`;
  return `${BASE_URL}/${STANDALONE_TAG}/${filename}`;
}

function sha256File(filePath) {
  return crypto.createHash('sha256').update(fs.readFileSync(filePath)).digest('hex');
}

function download(url, dest) {
  return new Promise((resolve, reject) => {
    const file = fs.createWriteStream(dest);
    const request = (u) => https.get(u, (res) => {
      if (res.statusCode === 301 || res.statusCode === 302) return request(res.headers.location);
      if (res.statusCode !== 200) { reject(new Error(`HTTP ${res.statusCode} for ${u}`)); return; }
      res.pipe(file);
      file.on('finish', () => file.close(resolve));
    }).on('error', reject);
    request(url);
  });
}

async function fetchAndVerify(url, tmpDir) {
  const filename     = path.basename(url);
  const archivePath  = path.join(tmpDir, filename);
  const checksumPath = archivePath + '.sha256';
  console.log(`Downloading ${url}`);
  await download(url, archivePath);
  await download(url + '.sha256', checksumPath);
  const expected = fs.readFileSync(checksumPath, 'utf8').trim().split(/\s+/)[0];
  const actual   = sha256File(archivePath);
  if (actual !== expected) throw new Error(`Checksum mismatch: expected ${expected}, got ${actual}`);
  console.log('Checksum OK');
  return archivePath;
}

function extract(archivePath, destDir, ext) {
  fs.mkdirSync(destDir, { recursive: true });
  if (ext === 'tar.gz') {
    execSync(`tar -xzf "${archivePath}" -C "${destDir}" --strip-components=1`);
  } else {
    execSync(`powershell -Command "Expand-Archive -Path '${archivePath}' -DestinationPath '${destDir}' -Force"`);
  }
}

async function main() {
  const platform = process.platform;
  const arch     = process.arch;
  const info     = PLATFORM_MAP[_key(platform, arch)];
  if (!info) { console.log(`Platform ${_key(platform, arch)} not supported — skipping`); return; }

  const projectRoot = path.join(__dirname, '..');
  const destDir     = path.join(projectRoot, 'resources', 'python', info.dir);
  const tmpDir      = path.join(projectRoot, 'resources', '_tmp');

  const marker = path.join(destDir, 'bin', platform === 'win32' ? 'python.exe' : 'python3');
  if (fs.existsSync(marker)) { console.log(`Python already at ${destDir} — skipping`); return; }

  fs.mkdirSync(tmpDir, { recursive: true });
  const archivePath = await fetchAndVerify(getDownloadUrl(platform, arch), tmpDir);
  extract(archivePath, destDir, info.ext);

  // Install Python dependencies into the bundled runtime
  const pipExe = platform === 'win32'
    ? path.join(destDir, 'Scripts', 'pip.exe')
    : path.join(destDir, 'bin', 'pip3');
  const reqFile = path.join(projectRoot, 'requirements.txt');
  if (fs.existsSync(reqFile)) {
    console.log('Installing Python dependencies...');
    execSync(`"${pipExe}" install -r "${reqFile}" --quiet`, { stdio: 'inherit' });
    console.log('Dependencies installed.');
  }

  fs.rmSync(tmpDir, { recursive: true, force: true });
  console.log(`Python installed to ${destDir}`);
}

if (require.main === module) {
  main().catch(err => { console.error(err); process.exit(1); });
}

module.exports = { getDownloadUrl, getPlatformDir, sha256File, PYTHON_VERSION, STANDALONE_TAG };
