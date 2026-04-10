const { computeStoredPath } = require('../../ui/browse-utils');

describe('computeStoredPath', () => {
  test('selected inside serve_root → returns relative path', () => {
    expect(computeStoredPath('/srv/blog/legacy/posts', '/srv/blog'))
      .toBe('legacy/posts');
  });

  test('selected is serve_root itself → returns dot', () => {
    expect(computeStoredPath('/srv/blog', '/srv/blog')).toBe('.');
  });

  test('selected outside serve_root → returns absolute path', () => {
    expect(computeStoredPath('/other/dir/posts', '/srv/blog'))
      .toBe('/other/dir/posts');
  });

  test('no serve_root set (null) → returns absolute path', () => {
    expect(computeStoredPath('/any/path', null)).toBe('/any/path');
  });

  test('no serve_root set (empty string) → returns absolute path', () => {
    expect(computeStoredPath('/any/path', '')).toBe('/any/path');
  });

  test('trailing slashes are normalised', () => {
    expect(computeStoredPath('/srv/blog/posts/', '/srv/blog/'))
      .toBe('posts');
  });

  test('deeply nested path returns full relative chain', () => {
    expect(computeStoredPath('/srv/blog/a/b/c', '/srv/blog'))
      .toBe('a/b/c');
  });
});
