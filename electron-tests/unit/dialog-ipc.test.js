const fs   = require('fs');
const path = require('path');

const mainSrc    = fs.readFileSync(path.join(__dirname, '..', '..', 'main.js'), 'utf8');
const preloadSrc = fs.readFileSync(path.join(__dirname, '..', '..', 'preload.js'), 'utf8');

describe('main.js dialog:openDir handler', () => {
  test('dialog is imported from electron', () => {
    expect(mainSrc).toMatch(/const\s*\{[^}]*dialog[^}]*\}\s*=\s*require\('electron'\)/);
  });

  test('dialog:openDir ipcMain handler is registered', () => {
    expect(mainSrc).toContain("'dialog:openDir'");
  });

  test('handler calls showOpenDialog with openDirectory property', () => {
    expect(mainSrc).toContain('showOpenDialog');
    expect(mainSrc).toContain("'openDirectory'");
  });

  test("handler uses app.getPath('home') as fallback defaultPath", () => {
    expect(mainSrc).toContain("app.getPath('home')");
  });

  test('handler returns null on cancel', () => {
    expect(mainSrc).toContain('canceled');
    expect(mainSrc).toContain('null');
  });
});

describe('preload.js openDir', () => {
  test('exposes openDir via contextBridge', () => {
    expect(preloadSrc).toContain('openDir');
  });

  test('openDir invokes dialog:openDir channel', () => {
    expect(preloadSrc).toContain("'dialog:openDir'");
  });
});
