---
layout: post
title: "Phase 6: The JEP is gone"
date: 2026-04-21
type: phase-update
entry_type: note
subtype: diary
projects: [sparge]
tags: [Quarkus, Java, Python, migration, TDD, JEP, ingest, convert]
---

When Phase 5 finished, the JEP call count was 22. After six weeks of incremental porting, the number is zero. Not "approaching zero" — zero. We ran `grep -r "bridge.call"` across the entire server codebase and got back a comment in ProjectsResource and a docstring in StartupActivation. Both referencing the thing that no longer exists.

The JEP dependency is out of `pom.xml`. The Quarkus server builds and runs without Python anywhere near it.

---

## What Phase 6 actually was

I'd planned Phase 6 as "whatever's left." The 22 remaining JEP calls spanned seven groups, ranging from trivial (config GET/POST: three lines of Java) to substantial (the full convert pipeline: 1,570 lines of Python across two modules).

I kept it as one epic — four child issues — and let the complexity gradient do the work. Start with the easy wins, end with the hard ones.

**6a: config + search + static_resolve (4 calls).** A morning's work in total. ConfigResource reads from `SpargeConfig` directly. SearchResource filters `StateStore.getAll()` with Java string matching. StaticResource resolves paths with `Path.normalize()` and a traversal guard. The only interesting moment was discovering that `StartupActivation` needed to exist: Python's `bridge_init()` always activated the first project at startup, but Java's `ActiveProject` was only populated on an explicit POST to `/api/projects/{id}/activate`. SmokeTest broke the moment `ConfigResource` started checking `isActive()` — which was how I learned I needed a `@Observes StartupEvent` bean that reads `projects.json` and populates `ActiveProject` without any JEP call. Five lines of CDI; fixed the test permanently.

**6b: consolidate + staging (5 calls).** `Consolidate.java` is a port of `scripts/consolidate.py` — hash-based asset deduplication. Walk `assets/posts/*/`, SHA-256 every file, find hashes that appear in two or more different post folders, promote the first copy to `assets/global/`, delete the duplicates, update `.url-index.json`, rewrite HTML references in the cleaned directory. The TDD tests drove out a real bug: the initial implementation used `Files.readAllBytes()` for hashing, which loads entire image files into heap. The streaming `DigestInputStream` fix was obvious once the code review flagged it — not obvious before then.

The staging endpoints (`stagedGet`, `acceptStaged`) were nominally straightforward — `StateStore` already had `acceptStaged(slug, mdDir, postsDir)`. The TDD tests found a 415 error on `rejectStaged` and `acceptStaged` that had been silent with JEP: both endpoints lacked `@Consumes(WILDCARD)`, so JAX-RS was refusing requests without a `Content-Type` header. The Python bridge never saw JAX-RS content negotiation — the error was invisible until we had native endpoints. TDD caught it; the fix was one annotation.

---

## Phase 6c: the hard one

**6c: convert pipeline (6 calls).** This is where I was genuinely uncertain whether the port was tractable in a reasonable timeframe. `convert_post.py` is 659 lines. `md_validator.py` is 913 lines. Together they are the HTML-to-Markdown conversion pipeline — the core of what Sparge does.

The Python code even has migration notes in it: `# MIGRATION NOTE (Quarkus/Java): html2text has no direct Java equivalent. The closest is flexmark-java.` Someone (me, months ago) had already thought through this. It was both reassuring and slightly embarrassing.

`ConvertPost.java` ports the 7-phase pipeline: junk selector removal, DOM cleanup, code block extraction to placeholders, flexmark HTML→Markdown conversion, placeholder restoration with adaptive fence lengths, Markdown cleanup, YAML front matter. jsoup handles the DOM work. flexmark-java's `FlexmarkHtmlConverter` with `SETEXT_HEADINGS=false` replaces `html2text`. The key insight from the migration notes: `html2text`'s `protect_links=True` produces `[text](<url>)` with angle brackets, and the validator's regex patterns all depend on that format. Since we're porting *both* the converter and the validator, we can use Java-native link format throughout and update the validator to match.

TDD drove `ConvertPostTest.java` to 19 tests covering front matter generation, junk selector removal, code block preservation with adaptive fence lengths, heading format, image path fixing, and a live integration test against a real KIE post. The integration test caught something the unit tests couldn't: posts with sidecar JSON in a different directory than the HTML file (enriched copies), which required the `json_path` parameter to be passed explicitly.

`MdValidator.java` is 14 MD-only checks (pure regex against Markdown content) plus 5 cross-checks (comparing Markdown against the original HTML). The MD-only checks port nearly verbatim — Python regex patterns translate to Java `Pattern.compile()` with minor escaping differences. The cross-checks were trickier.

A code quality review of `MdValidator.java` caught three real correctness gaps. `crossCodeBlockCount` had the wrong threshold: I'd written `mdFences < htmlPres * 0.5` (warn if fewer than half the HTML code blocks appear in MD), but Python's version is stricter — warn when the *difference* exceeds 1 block, and ERROR if MD has zero fences when HTML has pre blocks. `crossHeadingMatch` compared the full heading text rather than the first four words, producing false positives on headings with minor formatting differences. `crossLastSectionPresent` was taking a raw 40-character substring without normalising URLs or punctuation, so it would fire on any post whose final paragraph contained a link. All three were fixed with new failing tests before the fixes. That's the discipline the review process enforces: catch the gap, write the test, fix the code, verify the test passes.

---

## Phase 6d: ingest

**6d: ingest pipeline (7 calls).** The Python ingest module (`scripts/ingest.py`) is 1,095 lines. It discovers blog post URLs via sitemap, WordPress REST, Blogger Atom, and RSS feeds; fetches and extracts article content; localises images; writes HTML and JSON sidecar files to disk; and runs the whole thing asynchronously with a cancellable job state.

`IngestService.java` is `@ApplicationScoped`. It owns a `java.net.http.HttpClient` (static, thread-safe, shared) and a single-thread `ExecutorService` for the background worker. `IngestJobState.java` is a plain POJO with `synchronized` methods for mutations and `volatile` fields for hot-path reads (`cancelled`, `running`). The concurrency test — 10 threads appending 10 entries each — was the right test to write first. It confirmed there was no data loss under contention before anything else was wired.

All parsing methods (`parseSitemapUrls`, `parseFeedLinks`, `parseWpRestLinks`, `extractMetadata`, `extractArticleHtml`) are `static` and package-private. This was a pattern we established in Phase 6c for `ConvertPost` and `MdValidator` and carried through — unit tests call the static methods directly with no CDI, no mocks, no `@QuarkusTest` overhead. The unit tests for `IngestServiceTest` run in under 50ms. The `@QuarkusTest` E2E tests for `IngestResourceTest` run in ~60s. Both are necessary; neither replaces the other.

One gotcha: jsoup's default HTML parser lowercases element names, which breaks XML sitemap parsing silently. `sitemap.xml` files use `<loc>`, `<urlset>`, and `<sitemap>` — all lowercase anyway — but namespace-prefixed elements (`<image:loc>`) lose their prefix with the HTML parser. The fix is `Jsoup.parse(xml, "", Parser.xmlParser())`. Undocumented in the main Jsoup javadoc; only mentioned in the `Parser` class docs. It took two failed attempts at sitemap parsing before the cause became clear.

---

## The final two

After closing Phase 6d, we ran `grep -r "bridge.call"` one more time and found two calls outside the original 22:

- `PostsResource.scan()` had a JEP fallback for the `cfg == null` case — a three-line safety net from Phase 5 that was never removed. Replaced with `return err(400, "no active project")`. Two lines.

- `ProjectsResource.activate()` still called `bridge.call("bridge.projects_activate", id)` as a "best-effort" Python state sync. The comment said "needed for `State.init_from_source()`." With all endpoints ported, nothing in the server reads Python state anymore. The JEP call came out; the method returns a native 200 with the project name and active ID.

Then we removed JEP from `pom.xml`. `mvn compile` passed. `mvn test` passed. 346 tests.

---

## The awkward epilogue

The Quarkus server is fully Python-free. The Electron app is not.

`npm start` still launches `python-server.js`, which spawns `python3 server.py`. Python is bundled into every Electron distribution as `resources/python/`. The Java server (`java-server.js`) requires `SPARGE_SERVER=java` to activate.

`java-server.js` still sets up `PYTHONHOME` and `DYLD_LIBRARY_PATH` for JEP — environment variables that are now meaningless because we removed JEP. They're harmless, but they're stale. That's Phase 1: flip the Electron default, strip the Python bundling, update `java-server.js`. The Quarkus JAR isn't packaged into the Electron distribution yet — that's also Phase 1 work.

The migration is done on the server side. The packaging is next.
