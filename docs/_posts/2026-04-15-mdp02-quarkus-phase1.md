---
layout: post
title: "Phase 1: When Python's mutable dict becomes a Java record"
date: 2026-04-15
type: phase-update
entry_type: note
subtype: diary
projects: [sparge]
tags: [Quarkus, Java, Python, migration, Jackson, TDD]
typora-root-url: /Users/mdproctor/claude/sparge/docs
---

Sparge is a blog migration tool — it ingests HTML posts from live blog URLs,
enriches them, and converts them to Jekyll Markdown. The server side is a
Python HTTP server: ~1,000 lines handling 35 API endpoints, backed by a
handful of scripts that do the real work. It runs embedded inside an Electron
desktop app, bundled with its own CPython runtime.

I'm migrating it to Quarkus. Not because it's broken — v1.0.0 shipped last
week and works fine — but because a real migration of a real production
codebase, documented as it happens, is a more useful story than any synthetic
example. The goal is Quarkus Native: a single binary with no Python dependency,
~50ms startup instead of ~2s, and meaningfully lower memory.

## The strategy: JEP bridge, module by module

The migration is incremental. The first phase — [covered previously] —
established the JEP bridge: Quarkus handles all 35 HTTP endpoints but delegates
every call to Python via JEP (Java Embedded Python), which embeds CPython
in-process via JNI. Zero subprocess overhead. The Quarkus server is live and
handling traffic; Python is still doing all the work.

From here, each phase ports one or two Python modules to Java. When a module
is ported, the JEP bridge calls that delegated to it are removed. I'm tracking
JEP call count as the public metric — it starts at 35 and drops to zero when
the migration is complete.

![Migration phases and architecture — JEP call count dropping phase by phase](/blog-images/migration-architecture.png)

The diagram shows the full picture: four phases complete, two more to go, then
Quarkus Native. The test strategy pairs with this — JUnit tests are written
mirroring the existing Python tests before the implementation exists. When
Python is gone, the JUnit tests are still green. The Python tests move to a
`tests/python-legacy/` holding area rather than being deleted; they can be run
directly to cross-check a specific port.

This series documents each phase as it happens: what the Python code does, what
decisions go into the Java design, what's straightforward, and what isn't.

## Phase 1: the config layer

The first real port is the config layer — two small modules that everything
else depends on.

`sparge_home.py` has one job: read `~/.sparge/config.json` to find where
project data lives, creating the config with defaults if it's absent.

`config.py` is more interesting. It owns a module-level mutable dict — `cfg`
— that the rest of the codebase imports directly. When a project switches,
`set_config_path()` is called, which reloads from disk and mutates `cfg`
in-place. Every other module that imported `cfg` sees the new values
immediately, because they hold a reference to the same object.

```python
# Every module does this
from scripts.config import cfg

# Later, when a project activates:
def _activate_project(project_id: str):
    set_config_path(proj_dir / 'config.json')  # mutates cfg in-place
    POSTS_DIR = cfg['_posts_dir']              # other modules see the update
```

This is idiomatic Python. It's also the kind of pattern that requires real
thought to port to Java.

## The mutable dict problem

![Python cfg dict vs Java ResolvedConfig record — side-by-side comparison](/blog-images/config-comparison.png)

The instinct is to reach for a `HashMap<String, Object>`. It works, but you
lose all type safety, you're constantly casting, and you have no idea what keys
belong there without reading the code.

I went with a Java record instead. The `raw` field is what makes it practical
— it's the original `ObjectNode` parsed from disk. `save()` just writes it
back. All the resolved `Path` fields are computed at load time and never
persisted; they're derived views. Python's `save()` strips `_`-prefixed keys
to separate computed from persistent. Java's record never mixes them in the
first place.

```java
public record ResolvedConfig(
    String     projectName,
    Path       serveRoot,
    Path       postsDir,     // computed — not stored
    Path       assetsDir,    // computed — not stored
    Path       mdDir,        // computed — not stored
    Path       enrichedDir,
    String     githubToken,
    ObjectNode raw           // the original JSON — for round-trip save
) {}
```

```python
# Python — save strips computed '_' keys at write time
def save(c: dict):
    clean = {k: v for k, v in c.items() if not k.startswith('_')}
    _cfg_path.write_text(json.dumps(clean, indent=2))
```

```java
// Java — raw already contains only persistent fields
public static void save(Path configPath, ObjectNode raw) throws Exception {
    MAPPER.writerWithDefaultPrettyPrinter().writeValue(configPath.toFile(), raw);
}
```

The path resolution logic is identical in both languages:

```python
# Python
def _res(p: str) -> Path:
    path = Path(p)
    return path if path.is_absolute() else root / path
```

```java
// Java
static Path resolve(Path serveRoot, String p) {
    Path path = Path.of(p);
    return path.isAbsolute() ? path : serveRoot.resolve(path);
}
```

Same rules: absolute paths pass through, relative paths join to `serve_root`.
The test suite for path resolution is seven assertions — four relative-path
cases and three absolute-path cases. All seven were written as failing JUnit
tests before the implementation existed.

## Mirroring the Python tests in JUnit

Before writing a line of implementation, we mirrored all 13 existing Python
tests in JUnit. Here's what that looks like for the tilde-expansion case:

```python
# Python
def test_tilde_expansion_in_projects_dir(tmp_path, monkeypatch):
    monkeypatch.setenv('HOME', str(tmp_path))
    (tmp_path / '.sparge').mkdir()
    (tmp_path / '.sparge/config.json').write_text(
        json.dumps({'projects_dir': '~/custom-projects'})
    )
    importlib.reload(sparge_home)
    result = sparge_home.get_projects_dir()
    assert result == tmp_path / 'custom-projects'
```

```java
// Java
@Test
void expandsTildeInProjectsDir(@TempDir Path home) throws IOException {
    Path spargeDir = home.resolve(".sparge");
    Files.createDirectories(spargeDir);
    Files.writeString(spargeDir.resolve("config.json"),
            "{\"projects_dir\": \"~/custom-projects\"}");
    SpargeHome spargeHome = new SpargeHome(home);  // package-private testable constructor
    assertEquals(home.resolve("custom-projects"), spargeHome.getProjectsDir());
}
```

Python redirects the global `HOME` via `monkeypatch.setenv` and
`importlib.reload`. Java uses a package-private constructor that accepts any
home directory — no module-level state to redirect. The test is simpler and
doesn't require cleanup.

All 13 tests passed on first implementation run. JEP call count: **35 → 32**.
The pattern for the rest of the migration is established: immutable records for
config, Jackson `ObjectNode` for persistence, testable constructors with
`@TempDir` for isolation. Phase 2 applies these patterns to the most complex
module in the codebase.
