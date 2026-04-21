import pytest
from scripts.refine_replay import (
    _normalise, _fingerprint, _similarity,
    _parse_fences, _find_fence, apply_language_tag, replay,
    RefinementRule,
)

MD_SIMPLE = """\
# Hello

```
System.out.println("hello");
int x = 1;
```

Some text.

```java
already tagged
```
"""

MD_PROSE_IN_CODE = """\
# Post

```
This is a sentence about the code.
Another sentence here, describing what happens.
A third prose sentence in the block.
System.out.println("hi");
```
"""

def test_normalise_collapses_whitespace():
    assert _normalise("  Hello   World\n") == "hello world"

def test_fingerprint_is_16_chars():
    assert len(_fingerprint("some content")) == 16

def test_fingerprint_same_for_equivalent_content():
    assert _fingerprint("  Hello ") == _fingerprint("hello")

def test_similarity_identical():
    assert _similarity("hello world", "hello world") == pytest.approx(1.0)

def test_similarity_empty():
    assert _similarity("", "") == pytest.approx(1.0)

def test_parse_fences_finds_two():
    fences = _parse_fences(MD_SIMPLE)
    assert len(fences) == 2
    assert fences[0]['index'] == 0
    assert fences[0]['language'] == ''
    assert fences[1]['language'] == 'java'

def test_parse_fences_content_correct():
    fences = _parse_fences(MD_SIMPLE)
    assert 'System.out.println' in fences[0]['content']

def test_find_fence_exact_index():
    fences = _parse_fences(MD_SIMPLE)
    fp = _fingerprint(fences[0]['content'])
    rule = RefinementRule('language_tag_missing', 0, fp, fences[0]['content'][:128], {'language': 'java'})
    found = _find_fence(fences, rule)
    assert found is not None
    assert found['index'] == 0

def test_find_fence_slides_on_mismatch():
    """If fence_index is off by 1, fuzzy sliding still finds it."""
    fences = _parse_fences(MD_SIMPLE)
    fp = _fingerprint(fences[0]['content'])
    # Rule says fence_index=1 but content matches fence 0
    rule = RefinementRule('language_tag_missing', 1, fp, fences[0]['content'][:128], {'language': 'java'})
    found = _find_fence(fences, rule)
    assert found is not None
    assert found['index'] == 0

def test_find_fence_returns_none_on_no_match():
    fences = _parse_fences(MD_SIMPLE)
    rule = RefinementRule('language_tag_missing', 99, 'deadbeef00000000', 'completely different', {'language': 'java'})
    assert _find_fence(fences, rule) is None

def test_apply_language_tag_adds_language():
    fences = _parse_fences(MD_SIMPLE)
    result = apply_language_tag(MD_SIMPLE, fences[0], 'java')
    assert '```java\n' in result
    # Original untagged fence is gone
    assert result.count('```\n') < MD_SIMPLE.count('```\n')

def test_replay_applies_language_tag_rule():
    fences = _parse_fences(MD_SIMPLE)
    fp = _fingerprint(fences[0]['content'])
    rule = RefinementRule('language_tag_missing', 0, fp, fences[0]['content'][:128], {'language': 'java'})
    result, conflicts = replay(MD_SIMPLE, [rule])
    assert conflicts == []
    assert '```java\n' in result

def test_replay_conflict_on_no_match():
    rule = RefinementRule('language_tag_missing', 99, 'deadbeef00000000', 'no match', {'language': 'java'})
    result, conflicts = replay(MD_SIMPLE, [rule])
    assert len(conflicts) == 1
    assert 'language_tag_missing' in conflicts[0]
    assert result == MD_SIMPLE  # unchanged
