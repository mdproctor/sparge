# scripts/refine_replay.py
"""
Replay engine for accepted refinement rules.

Stored rules include a fence_index (position hint) and fingerprint
(sha256[:16] of normalised content) plus a content_sample for fuzzy
fallback. On replay, we locate the target fence with a ±2 slide and
≥85% similarity threshold, then apply the stored fix.
"""
import hashlib
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import List, Optional, Tuple


@dataclass
class RefinementRule:
    check: str
    fence_index: int
    fingerprint: str        # sha256[:16] of normalised fence content
    content_sample: str     # first 128 chars of normalised content (fuzzy fallback)
    fix: dict               # {'language': 'java'} or {'extracted_text': '...'}


# Matches opening fence (```lang or ```) + body + closing fence (```)
_FENCE_RE = re.compile(r'(?m)^(```+)(\w*)\n(.*?)^\1\s*$', re.DOTALL)


def _normalise(text: str) -> str:
    return re.sub(r'\s+', ' ', text.lower().strip())


def _fingerprint(text: str) -> str:
    return hashlib.sha256(_normalise(text).encode()).hexdigest()[:16]


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalise(a), _normalise(b)).ratio()


def _parse_fences(md: str) -> List[dict]:
    """Return list of fenced blocks: {index, start, end, language, content, full_match}."""
    results = []
    for i, m in enumerate(_FENCE_RE.finditer(md)):
        results.append({
            'index':      i,
            'start':      m.start(),
            'end':        m.end(),
            'language':   m.group(2),
            'content':    m.group(3),
            'full_match': m.group(0),
        })
    return results


def _find_fence(fences: List[dict], rule: RefinementRule, threshold: float = 0.85) -> Optional[dict]:
    """
    Locate the fence for a rule.
    1. Exact fingerprint at fence_index (no slide).
    2. Slide ±1, ±2: exact fingerprint match.
    3. Slide ±1, ±2: content_sample similarity ≥ threshold.
    Returns None if no match found.
    """
    by_index = {f['index']: f for f in fences}

    # Pass 1: exact fingerprint match with sliding
    for offset in [0, 1, -1, 2, -2]:
        candidate = by_index.get(rule.fence_index + offset)
        if candidate is not None and _fingerprint(candidate['content']) == rule.fingerprint:
            return candidate

    # Pass 2: fuzzy content_sample similarity
    for offset in [0, 1, -1, 2, -2]:
        candidate = by_index.get(rule.fence_index + offset)
        if candidate is not None and _similarity(candidate['content'], rule.content_sample) >= threshold:
            return candidate

    return None


def apply_language_tag(md: str, fence: dict, language: str) -> str:
    """Replace the opening ``` of a fence with ```<language>."""
    old_open = '```\n' if not fence['language'] else f'```{fence["language"]}\n'
    new_open = f'```{language}\n'
    old_block = fence['full_match']
    new_block = old_block.replace(old_open, new_open, 1)
    return md[:fence['start']] + new_block + md[fence['end']:]


def apply_prose_extraction(md: str, fence: dict, extracted_text: str) -> str:
    """Move prose lines out of a fenced code block, placing them before it."""
    lines = fence['content'].split('\n')
    prose_lines, code_lines = [], []
    for line in lines:
        stripped = line.strip()
        is_prose = (
            len(stripped) > 20
            and stripped and stripped[0].isupper()
            and ' ' in stripped
            and not stripped.startswith(('//', '*', '#', '@'))
        )
        if is_prose:
            prose_lines.append(line)
        else:
            code_lines.append(line)
    new_content = '\n'.join(code_lines)
    prose_block = '\n'.join(prose_lines) + '\n\n' if prose_lines else ''
    lang = fence['language']
    new_fence = f'```{lang}\n{new_content}```'
    return md[:fence['start']] + prose_block + new_fence + md[fence['end']:]


def replay(md: str, rules: List[RefinementRule]) -> Tuple[str, List[str]]:
    """
    Apply accepted rules to md. Returns (refined_md, conflicts).
    Rules applied in reverse fence_index order to preserve string offsets.
    """
    fences = _parse_fences(md)
    conflicts: List[str] = []
    current_md = md

    for rule in sorted(rules, key=lambda r: r.fence_index, reverse=True):
        fence = _find_fence(fences, rule)
        if fence is None:
            conflicts.append(f'{rule.check}@fence_{rule.fence_index}')
            continue

        if rule.check == 'language_tag_missing':
            language = rule.fix.get('language', '')
            if language:
                current_md = apply_language_tag(current_md, fence, language)
        elif rule.check == 'prose_in_code':
            extracted = rule.fix.get('extracted_text', '')
            current_md = apply_prose_extraction(current_md, fence, extracted)

        # Re-parse after each application so offsets stay accurate
        fences = _parse_fences(current_md)

    return current_md, conflicts
