// electron-tests/unit/fetch-python.test.js
const { getDownloadUrl, getPlatformDir, PYTHON_VERSION, STANDALONE_TAG } = require('../../scripts/fetch-python');

describe('getDownloadUrl', () => {
  test('mac arm64 uses aarch64-apple-darwin tar.gz', () => {
    const url = getDownloadUrl('darwin', 'arm64');
    expect(url).toContain(STANDALONE_TAG);
    expect(url).toContain('aarch64-apple-darwin');
    expect(url).toContain('install_only');
    expect(url).toMatch(/\.tar\.gz$/);
  });

  test('mac x64 uses x86_64-apple-darwin tar.gz', () => {
    const url = getDownloadUrl('darwin', 'x64');
    expect(url).toContain('x86_64-apple-darwin');
    expect(url).toMatch(/\.tar\.gz$/);
  });

  test('windows x64 uses x86_64-pc-windows-msvc zip', () => {
    const url = getDownloadUrl('win32', 'x64');
    expect(url).toContain('x86_64-pc-windows-msvc');
    expect(url).toMatch(/\.zip$/);
  });

  test('linux x64 uses x86_64-unknown-linux-gnu tar.gz', () => {
    const url = getDownloadUrl('linux', 'x64');
    expect(url).toContain('x86_64-unknown-linux-gnu');
    expect(url).toMatch(/\.tar\.gz$/);
  });

  test('throws on unsupported platform', () => {
    expect(() => getDownloadUrl('freebsd', 'x64')).toThrow('Unsupported');
  });
});

describe('getPlatformDir', () => {
  test('darwin arm64 → mac-arm64', () => expect(getPlatformDir('darwin', 'arm64')).toBe('mac-arm64'));
  test('darwin x64 → mac-x64',     () => expect(getPlatformDir('darwin', 'x64')).toBe('mac-x64'));
  test('win32 x64 → win-x64',      () => expect(getPlatformDir('win32', 'x64')).toBe('win-x64'));
  test('linux x64 → linux-x64',    () => expect(getPlatformDir('linux', 'x64')).toBe('linux-x64'));
});
