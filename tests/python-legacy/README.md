# python-legacy

Holding area for pytest tests whose Python modules have been ported to Java.

These tests are **never run in CI** (excluded by `pytest.ini`). They exist for
cross-checking: if a specific Java port needs verifying, run them directly:

    pytest tests/python-legacy/test_sparge_home.py -v

Do not delete them until the final phase (when Python is fully removed).
