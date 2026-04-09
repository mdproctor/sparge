// electron-tests/unit/python-server-utils.test.js
jest.mock('http');
jest.mock('net');

const http = require('http');
const net  = require('net');
const { findFreePort, pollUntilReady } = require('../../python-server');

describe('findFreePort', () => {
  test('returns the port assigned by the OS', async () => {
    const mockServer = {
      listen:  jest.fn((port, host, cb) => cb()),
      address: jest.fn(() => ({ port: 54321 })),
      close:   jest.fn((cb) => cb()),
      on:      jest.fn(),
    };
    net.createServer.mockReturnValue(mockServer);
    const port = await findFreePort();
    expect(port).toBe(54321);
    expect(mockServer.listen).toHaveBeenCalledWith(0, '127.0.0.1', expect.any(Function));
  });
});

describe('pollUntilReady', () => {
  beforeEach(() => jest.useFakeTimers());
  afterEach(() => jest.useRealTimers());

  test('resolves when server responds 200', async () => {
    const mockRes = { statusCode: 200, resume: jest.fn() };
    http.get.mockImplementation((_url, cb) => {
      cb(mockRes);
      return { on: jest.fn(), setTimeout: jest.fn(), destroy: jest.fn() };
    });
    await expect(pollUntilReady(9876, { intervalMs: 200, timeoutMs: 5000 })).resolves.toBeUndefined();
  });

  test('rejects after timeout when server never responds', async () => {
    http.get.mockImplementation((_url, _cb) => ({
      on: (ev, fn) => { if (ev === 'error') fn(new Error('ECONNREFUSED')); },
      setTimeout: jest.fn(),
      destroy: jest.fn(),
    }));
    const promise = pollUntilReady(9876, { intervalMs: 50, timeoutMs: 200 });
    jest.advanceTimersByTime(300);
    await expect(promise).rejects.toThrow('did not start');
  });
});
