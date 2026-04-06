"""
Shared fixtures and path setup for sparge tests.
"""
import sys
from pathlib import Path

import pytest

# Make sparge/scripts/ importable as 'scripts.*' and directly
SPARGE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(SPARGE_ROOT / 'scripts'))
sys.path.insert(0, str(SPARGE_ROOT / 'tests'))

# Keep MIGRATOR_ROOT as alias for compatibility
MIGRATOR_ROOT = SPARGE_ROOT


@pytest.fixture(scope='session')
def mock_blog_server():
    """Session-scoped mock blog available to all test modules."""
    from fixtures.mock_blog import start_mock_blog
    server, url = start_mock_blog()
    yield url
    server.shutdown()
