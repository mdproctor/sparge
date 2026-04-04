"""
Shared fixtures and path setup for Sparge tests.
"""
import sys
from pathlib import Path

import pytest

# Make sparge/scripts/ importable as 'scripts.*'
MIGRATOR_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(MIGRATOR_ROOT / 'scripts'))
sys.path.insert(0, str(MIGRATOR_ROOT / 'tests'))

# Also make the parent scripts/ available (md_validator, convert_post, etc.)
REPO_ROOT = MIGRATOR_ROOT.parent
sys.path.insert(0, str(REPO_ROOT / 'scripts'))


@pytest.fixture(scope='session')
def mock_blog_server():
    """Session-scoped mock blog available to all test modules."""
    from fixtures.mock_blog import start_mock_blog
    server, url = start_mock_blog()
    yield url
    server.shutdown()
