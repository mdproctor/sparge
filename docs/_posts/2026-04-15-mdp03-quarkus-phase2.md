---
layout: post
title: "Phase 2: Porting state.py — 368 lines, 27 edge cases, one JSON file"
date: 2026-04-15
type: phase-update
entry_type: note
subtype: diary
projects: [sparge]
tags: [Quarkus, Java, Python, migration, Jackson, TDD, state-management]
typora-root-url: /Users/mdproctor/claude/sparge/docs
---

`state.py` is where Sparge tracks everything that happens to a post: when the
HTML was last scanned, what issues were found, whether the Markdown was
generated, whether it's been reviewed. 368 lines, one JSON file on disk,
called from everywhere.

It's the most interesting port so far — not because the logic is complex (most
of it isn't), but because it surfaces real design differences between Python
and Java.

## The deep merge problem

Python's `update()` does a shallow-merge at the top level and a deep-merge
for `html`, `md`, and `assets` sub-dicts:

```python
def update(slug: str, patch: dict):
    state = _load()
    entry = state.setdefault(slug, {'slug': slug})
    for key, val in patch.items():
        if key in ('html', 'md', 'assets') and isinstance(val, dict):
            entry.setdefault(key, {}).update(val)  # deep merge
        else:
            entry[key] = val                       # overwrite
    _save(state)
```

`isinstance(val, dict)` is free in Python. In Java, the `patch` is
`Map<String, Object>` and the values are `Object`. Deep-merging requires
explicit type dispatch:

```java
private static void mergeInto(ObjectNode entry, Map<String, Object> patch) {
    for (var kv : patch.entrySet()) {
        String key = kv.getKey();
        Object val = kv.getValue();
        if ((key.equals("html") || key.equals("md") || key.equals("assets"))
                && val instanceof Map) {
            // deep merge into existing sub-object
            ObjectNode sub = entry.has(key) ? (ObjectNode) entry.get(key)
                                            : MAPPER.createObjectNode();
            for (var sv : ((Map<String, Object>) val).entrySet())
                sub.set(sv.getKey(), toJsonNode(sv.getValue()));
            entry.set(key, sub);
        } else {
            entry.set(key, toJsonNode(val));  // overwrite
        }
    }
}
```

The `toJsonNode(Object)` helper dispatches on `Boolean`, `Integer`, `String`,
`List`, `Map` — ten lines of code that Python gets for free from its dynamic
type system. Not a hardship, but worth naming as a genuine difference.

## Stale detection and why TDD mattered

![Stale detection decision tree — 4 edge cases TDD surfaced](/blog-images/stale-detection.png)

MD is stale when the HTML hash changed since generation. Four conditions must
all be true. The Python version:

```python
def _is_stale(entry: dict) -> bool:
    html_hash = entry.get('html', {}).get('hash')
    md_hash   = entry.get('md',   {}).get('html_hash')
    generated = entry.get('md',   {}).get('generated_at')
    return bool(generated and html_hash and md_hash and html_hash != md_hash)
```

```java
// Java
private static boolean isStale(ObjectNode entry) {
    String htmlHash = entry.path("html").path("hash").asText(null);
    String mdHash   = entry.path("md").path("html_hash").asText(null);
    String genAt    = entry.path("md").path("generated_at").asText(null);
    return genAt != null && !genAt.isEmpty()
        && htmlHash != null && !htmlHash.isEmpty()
        && mdHash   != null && !mdHash.isEmpty()
        && !htmlHash.equals(mdHash);
}
```

The extra `!isEmpty()` checks are because Jackson's `asText(null)` returns
`null` for missing JSON nodes but returns `""` for JSON `null` values. Without
them, a post where `generated_at` is explicitly `null` in JSON would
incorrectly compute as not-stale. We wrote four JUnit tests for the four
combinations before writing the implementation. They caught this immediately.

## The dismiss/undismiss interaction

The most intricate piece: when you dismiss an HTML issue, it disappears from
the active list. When the scanner runs again, dismissed issues stay filtered
(if still detected) or auto-clear (if the underlying problem was fixed).

```python
detected_types = {i['type'] for i in issues}

# Auto-clear dismissals for types no longer detected
for itype in list(dismissed.keys()):
    if itype not in detected_types:
        del dismissed[itype]

# Active = detected minus dismissed
active_issues = [i for i in issues if i['type'] not in dismissed]
```

The Java port follows the same logic exactly. What TDD gave us here: we wrote
the "dismissed issue stays filtered" test and the "dismissal auto-clears" test
before the implementation. Both failed in the naive version (which just set
issues without filtering). The tests made the requirements explicit before a
line of production code existed.

```java
// Auto-clear stale dismissals
Set<String> toRemove = new HashSet<>();
dismissed.fieldNames().forEachRemaining(t -> {
    if (!detected.contains(t)) toRemove.add(t);
});
toRemove.forEach(dismissed::remove);

// Active = detected minus dismissed
ArrayNode active = MAPPER.createArrayNode();
for (var i : issues) {
    String t = i.containsKey("type") ? i.get("type").toString() : "";
    if (!dismissed.has(t)) active.add(toJsonNode(i));
}
```

## Synchronization

Python's GIL means you don't think about thread safety for in-memory state.
Java doesn't have that. Every state-mutating method is `synchronized`, and
`load()` reads fresh from disk every time — no in-memory cache. Slightly slower
than Python's approach, but each write is immediately durable and concurrent
reads always see consistent state. Given the state file is a few hundred KB
and reads take microseconds, it's the right trade.

## The test suite

27 JUnit tests in `StateStoreTest`, all written before the implementation:

- 4 for basic get/getAll
- 4 for stale detection edge cases
- 4 for update() deep-merge behaviour
- 6 for dismiss/undismiss/setHtmlIssues interactions
- 2 for markMdGenerated (with real temp HTML files for hashing)
- 1 for markEnriched
- 5 for the full staged workflow (stage → accept and stage → reject with real files)

The staged workflow tests use `@TempDir` to create actual `.md.staged` files
and verify they're promoted or deleted correctly. Tests that involve file
operations are the ones most likely to mask bugs in pure unit tests — having
them with real files caught two path-construction issues during development.

JEP call count: **32 → 27**. Phase 3 tackles the HTML manipulation layer:
BeautifulSoup to Jsoup.
