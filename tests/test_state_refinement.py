import pytest
from pathlib import Path


@pytest.fixture
def store(tmp_path):
    import scripts.state as st
    state_file = tmp_path / 'state.json'
    state_file.write_text('{}')
    st.set_state_file(state_file)
    st.update('test-slug', {
        'slug': 'test-slug',
        'title': 'Test',
        'date': '2026-01-01',
        'author': 'a',
        'original_url': 'http://x',
    })
    return st


def test_set_md_suggestions_stored(store):
    suggestions = [{'check': 'language_tag_missing', 'level': 'WARN', 'detail': '2 fences'}]
    store.set_md_suggestions('test-slug', suggestions)
    p = store.get('test-slug')
    assert p['md']['suggestions'] == suggestions


def test_set_refinement_stored(store):
    accepted = [{'check': 'language_tag_missing', 'fence_index': 0, 'fingerprint': 'abc', 'content_sample': 'x', 'fix': {'language': 'java'}}]
    store.set_refinement('test-slug', accepted, [])
    p = store.get('test-slug')
    assert p['refinement']['accepted'] == accepted
    assert p['refinement']['replay_conflicts'] == []
    assert 'refined_at' in p['refinement']


def test_clear_refinement(store):
    store.set_refinement('test-slug', [{'check': 'x'}], ['c1'])
    store.clear_refinement('test-slug')
    p = store.get('test-slug')
    assert p['refinement']['accepted'] == []
    assert p['refinement']['replay_conflicts'] == []
