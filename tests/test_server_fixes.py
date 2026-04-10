# tests/test_server_fixes.py
import os, json, pathlib, shutil, subprocess, sys, time, urllib.request


def _start_server(port):
    proc = subprocess.Popen(
        [sys.executable, 'server.py', '--port', str(port)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        cwd=os.path.join(os.path.dirname(__file__), '..')
    )
    for _ in range(30):
        try:
            urllib.request.urlopen(f'http://localhost:{port}/api/config', timeout=1)
            return proc
        except Exception:
            time.sleep(0.5)
    proc.terminate()
    raise AssertionError(f'Server did not start on port {port}')


def test_projects_create_default_serve_root_is_home():
    """POST /api/projects without serve_root must default to home dir."""
    port = 19878
    proc = _start_server(port)
    test_id = None
    try:
        resp = urllib.request.urlopen(
            urllib.request.Request(
                f'http://localhost:{port}/api/projects',
                data=json.dumps({'name': 'test-default-root-19878'}).encode(),
                headers={'Content-Type': 'application/json'},
                method='POST',
            ), timeout=5
        )
        data = json.loads(resp.read())
        assert 'id' in data
        test_id = data['id']
        config_path = pathlib.Path.home() / 'sparge-projects' / test_id / 'config.json'
        assert config_path.exists(), f"config.json not found at {config_path}"
        config = json.loads(config_path.read_text())
        assert config['serve_root'] == str(pathlib.Path.home()), (
            f"Expected home dir, got: {config['serve_root']}"
        )
    finally:
        proc.terminate()
        proc.wait(timeout=5)
        if test_id:
            test_dir = pathlib.Path.home() / 'sparge-projects' / test_id
            if test_dir.exists():
                shutil.rmtree(test_dir)


def test_save_cfg_import_is_available():
    """save_cfg must be importable from scripts.config as 'save'."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))
    from config import save
    assert callable(save)
