---
layout: post
title: "Phase 0: Quarkus speaks Python (via JEP)"
date: 2026-04-15
type: phase-update
entry_type: note
subtype: diary
projects: [sparge]
tags: [Quarkus, JEP, Java, Python, migration]
---

Phase 0 is done. Quarkus is handling all 35 API endpoints, every call
delegated to Python via JEP.

## What we built

The architecture is straightforward in principle: a `bridge.py` module in
`scripts/` exposes all the Python handler logic as JSON-returning functions.
The Quarkus server calls them through JEP's `SharedInterpreter`. Every
JAX-RS resource is two lines: call the bridge, wrap the result.

```java
@GET
public Response list(@QueryParam("author") String author) {
    return BridgeResponse.of(bridge.call("bridge.posts_list",
                                         author != null ? author : ""));
}
```

This is Phase 0 — no porting, just translation. The interesting parts are
what we learned along the way.

## The thread that broke everything

The first version of `PythonBridge` used `synchronized`:

```java
public synchronized String call(String function, Object... args) {
    return (String) interp.invoke(function, args);
}
```

Looks right. Prevents concurrent calls. In practice, every HTTP request hung
indefinitely — no error, no timeout, no stack trace.

The cause: JEP's `SharedInterpreter` is thread-affinite. It must be called
from the exact thread that created it. `@PostConstruct` runs on a Quarkus
startup thread; HTTP requests arrive on Vert.x worker threads. `synchronized`
prevents two threads from calling JEP simultaneously. It does nothing for
ownership. The worker thread acquires the lock and calls `interp.invoke()`,
which waits for the GIL from the owner thread — long since idle. Deadlock.
Indefinitely.

The fix is a dedicated daemon thread that owns the interpreter for its entire
lifetime. HTTP threads submit tasks via a `LinkedBlockingQueue` and block on
a `CompletableFuture` with a 30-second timeout:

```java
private record Task(String function, Object[] args, CompletableFuture<String> result) {}
private final LinkedBlockingQueue<Task> queue = new LinkedBlockingQueue<>();

public String call(String function, Object... args) {
    CompletableFuture<String> future = new CompletableFuture<>();
    queue.offer(new Task(function, args, future));
    return future.get(30, TimeUnit.SECONDS);
}
```

The timeout matters. Without it, a hung call becomes a hung test suite.
I found this the hard way: a subagent spent 90 minutes in the integration
test loop before I killed it and read the logs.

## PYTHONHOME is not DYLD_LIBRARY_PATH

To load JEP you need `DYLD_LIBRARY_PATH` pointing at `libpython3.12.dylib`.
That's what JEP needs to link. It is not what Python needs to run.

The first Python call after startup produced:

```
Fatal Python error: Failed to import encodings module
ModuleNotFoundError: No module named 'encodings'
```

`DYLD_LIBRARY_PATH` tells the OS dynamic linker where to find the shared
library. Once CPython is loaded, it needs `PYTHONHOME` to find its own
standard library — `encodings`, `codecs`, `io`, everything required before
any import can work. Two independent environment variables, two different
problems.

One side effect: if you `export PYTHONHOME=.../python3.12` in your shell
before spawning the JVM, that setting bleeds into every `python3` command
you run in the same shell. System Python 3.13 trying to load Python 3.12's
stdlib fails with the same `encodings` error. I spent some time confused by
this until I noticed `echo $PYTHONHOME`.

## lxml is missing from the bundled Python

The bundled CPython at `resources/python/mac-arm64/` does not include `lxml`.
The system Python does. `BeautifulSoup(content, 'xml')` — used by the sitemap
ingest code to discover post URLs — raised `FeatureNotFound`. The exception
was silently caught. The discover call returned zero URLs instead of twenty,
and the integration test failed with a confusing assertion about URL count
rather than any Python exception.

Fix: one pip install into the bundled interpreter.

## JAX-RS boolean @QueryParam silently ignores "1"

The generate-md endpoint takes `?dry=1`. The Python server checks
`params.get('dry') == '1'`. The JAX-RS version used
`@QueryParam("dry") @DefaultValue("false") boolean dry`. Works perfectly for
`?dry=true`. For `?dry=1` — which is what the UI and the tests actually
send — it silently evaluates to false. No error, no 400, just wrong behaviour.

JAX-RS boolean parsing accepts `"true"` and `"false"`, case-insensitive, and
nothing else. Received the parameter as `String` and parsed manually.

## Two catches from code review

Claude's code quality pass on the bridge implementation caught two things I
hadn't noticed.

First: path injection via string interpolation. The original `PythonBridge.init()`
built the Python `sys.path.insert` call by concatenating a Java string directly
into the Python statement. Single quotes in a path — a macOS username like
`user's docs` — would break it. The fix is `interp.set()`, which passes the
Java string as a Python variable without any escaping:

```java
interp.set("_sparge_root", repoRootPath);
interp.exec("sys.path.insert(0, _sparge_root)");
```

Second: the initial `bridge.py` used bare imports in `bridge_init()`:

```python
from convert_post import convert_post as _cp  # silently fails
```

`sys.path` was set to the repo root, not `scripts/`. The bare name
`convert_post` wasn't findable. The `ImportError` was caught and swallowed.
Every `_can_*` flag stayed `False`, all optional features disabled, no error
anywhere. Fix: package-qualify everything — `from scripts.convert_post import`.

## API tests pass; Playwright tests surface a different story

All API-level integration tests pass against Quarkus. The Playwright tests —
hardcoded to `localhost:9000`, testing JavaScript behaviour in a browser — now
run (playwright is installed on this machine) and fail on pre-existing JavaScript
bugs: a save button that stays permanently disabled after the first save, a
dirty-detection edge case. These aren't Quarkus failures. They were masked
before by the tests skipping when no server was running.

Phase 1 is porting `sparge_home.py` and `config.py`. First real Java code,
first JEP call removed.
