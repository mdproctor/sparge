// electron-tests/unit/preload.test.js
// preload.js calls Electron APIs (contextBridge) which aren't available in Jest.
// We verify the API surface by reading the source.
const fs  = require('fs');
const src = fs.readFileSync(require.resolve('../../preload.js'), 'utf8');

test('exposes getVersion',         () => expect(src).toContain('getVersion'));
test('exposes onUpdateAvailable',  () => expect(src).toContain('onUpdateAvailable'));
test('exposes onUpdateDownloaded', () => expect(src).toContain('onUpdateDownloaded'));
test('exposes installUpdate',      () => expect(src).toContain('installUpdate'));
test('uses exposeInMainWorld',     () => expect(src).toContain('exposeInMainWorld'));
