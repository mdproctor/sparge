import os, subprocess, sys, time, urllib.request

def test_server_accepts_port_arg():
    port = 19876
    proc = subprocess.Popen(
        [sys.executable, 'server.py', '--port', str(port)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        cwd=os.path.join(os.path.dirname(__file__), '..')
    )
    try:
        for _ in range(30):
            try:
                resp = urllib.request.urlopen(
                    f'http://localhost:{port}/api/config', timeout=1
                )
                assert resp.status == 200
                return
            except Exception:
                time.sleep(0.5)
        raise AssertionError('Server did not start on port 19876')
    finally:
        proc.terminate()
        proc.wait(timeout=5)
