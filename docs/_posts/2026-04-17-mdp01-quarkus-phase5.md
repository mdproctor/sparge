---
layout: post
title: "Phase 5: Porting Python's HTTP enrichment pipeline to Java"
date: 2026-04-17
type: phase-update
entry_type: note
subtype: diary
projects: [sparge]
tags: [Quarkus, Java, Python, migration, HttpClient, Jsoup, TDD]
typora-root-url: /Users/mdproctor/claude/sparge/docs
---

Phase 5 is `enrich.py` — 350 lines that transform a raw blog post HTML file
into an archive-ready version. YouTube iframes become thumbnail figures.
GitHub Gist `<script>` tags become inlined `<pre><code>` blocks. SyntaxHighlighter
brush classes become standard `language-X` classes. Unlabelled code blocks
get language hints from content heuristics. Leftover iframes get archive-note
wrappers. None of this sounds complicated — but it's the first phase where
Java has to make real HTTP calls, parse JSON, and build DOM elements from
scratch rather than just querying them.

![The enrichment pipeline — 6 operations on a single Jsoup Document](/blog-images/enrich-pipeline.png)

The pipeline runs once per post, the first time it's scanned. After that the
enriched copy is cached on disk and subsequent scans read from it directly.
Order matters: YouTube iframes must be replaced before the embed fallback
wrapper runs, or you'd wrap a figure you just created. Code class normalisation
must run before language detection, or you'd try to detect languages on `<pre>`
elements that already have correct `language-X` classes from the normaliser.

## The Python code — what we're porting

The Python module exposes six public functions and an orchestrator:

```python
def replace_youtube_embeds(article, assets_dir, session) -> dict
def replace_gist_embeds(article, github_token, session)  -> dict
def normalise_code_classes(article)                       -> dict
def detect_code_languages(article)                        -> dict
def replace_embed_fallbacks(article)                      -> dict
def enrich_post(html_path, enriched_path, assets_dir, github_token) -> dict
```

The first two take a `requests.Session` — the Python HTTP client. The
last four are pure DOM transforms. This distinction drives the Java design:
pure transforms become `static` methods; HTTP-dependent methods become
instance methods on a class that owns an `HttpClient`.

## The biggest shift: HTTP clients

![Python requests vs Java HttpClient — side-by-side API comparison](/blog-images/http-comparison.png)

In Python, `requests` is the de-facto HTTP library. Its `Session` object
handles connection pooling, headers, and timeouts with a simple API:

```python
# Python — download YouTube thumbnail
session = requests.Session()
resp = session.get(url, timeout=15)
if resp.status_code == 200 and resp.content:
    dest.write_bytes(resp.content)
```

Java's built-in `java.net.http.HttpClient` (added in Java 11) is the modern
equivalent. It's slightly more ceremonial but equally capable:

```java
// Java — download YouTube thumbnail
HttpRequest req = HttpRequest.newBuilder(URI.create(url)).build();
HttpResponse<byte[]> resp = http.send(req, HttpResponse.BodyHandlers.ofByteArray());
if (resp.statusCode() == 200 && resp.body().length > 0) {
    Files.write(dest, resp.body());
}
```

The key difference: Python's `requests` raises exceptions on network errors
by default; Java's `HttpClient.send()` throws checked exceptions that you
must handle. Both libraries use connection pooling by default. Neither
requires external dependencies — `requests` is bundled with most Python
installs; `HttpClient` is in the JDK.

For the Gist API, headers become a slightly longer builder chain:

```python
# Python — GitHub API call with optional auth header
headers = {'Accept': 'application/vnd.github+json'}
if github_token:
    headers['Authorization'] = f'Bearer {github_token}'
resp = session.get(url, headers=headers, timeout=30)
```

```java
// Java — GitHub API call with optional auth header
HttpRequest.Builder b = HttpRequest.newBuilder(URI.create(url))
        .header("Accept", "application/vnd.github+json");
if (token != null && !token.isEmpty())
    b.header("Authorization", "Bearer " + token);
HttpResponse<String> resp = http.send(b.build(), HttpResponse.BodyHandlers.ofString());
```

The builder pattern in Java is more verbose but explicit about what's
happening. The `BodyHandlers` selection (`ofByteArray()` for images,
`ofString()` for JSON) makes the return type clear at the call site —
something Python's typeless response object doesn't do.

## Testing HTTP without Mockito

The hardest testing question in Phase 5 is: how do you test methods that
make real HTTP calls without actually making HTTP calls?

The obvious Java answer is Mockito — mock the `HttpClient`, stub the
response, verify the call. But mocking `HttpClient` is genuinely painful.
The interface hierarchy involves `HttpRequest`, `HttpResponse<T>` with its
generics, `BodyHandler`, and more. Getting Mockito to return a sensible
`HttpResponse<byte[]>` takes more boilerplate than the actual test.

Instead, we used a simpler pattern: **package-private method overrides via
subclassing**. The HTTP calls in `Enricher` are extracted into two tiny
helper methods:

```java
// In Enricher.java — package-private, overrideable in tests
byte[] fetchUrl(String url) {
    HttpRequest req = HttpRequest.newBuilder(URI.create(url)).build();
    HttpResponse<byte[]> resp = http.send(req, HttpResponse.BodyHandlers.ofByteArray());
    return resp.statusCode() == 200 && resp.body().length > 0 ? resp.body() : null;
}

String fetchJson(String url, String token) {
    // ... builder, send, return body or null
}
```

The test file defines an inner `MockEnricher` that overrides both methods:

```java
static class MockEnricher extends Enricher {
    final Map<String, byte[]> urlBytes = new HashMap<>();
    final Map<String, String> urlJson  = new HashMap<>();
    int fetchCallCount = 0;

    void mockBytes(String url, byte[] bytes) { urlBytes.put(url, bytes); }
    void mockJson(String url, String json)   { urlJson.put(url, json); }

    @Override byte[] fetchUrl(String url) {
        fetchCallCount++;
        return urlBytes.get(url);  // returns null if URL not mocked
    }

    @Override String fetchJson(String url, String token) {
        return urlJson.get(url);
    }
}
```

Usage in a test is four lines:

```java
@Test
void youtubeEmbedReplacedWithFigure(@TempDir Path tempDir) throws Exception {
    MockEnricher e = new MockEnricher();
    e.mockBytes("https://img.youtube.com/vi/dQw4w9WgXcQ/maxresdefault.jpg",
                new byte[]{1, 2, 3});
    Path assets = Files.createDirectories(tempDir.resolve("assets"));

    Element a = article("<iframe src=\"https://www.youtube.com/embed/dQw4w9WgXcQ\"></iframe>");
    int count = e.replaceYoutubeEmbeds(a, assets);

    assertEquals(1, count);
    assertEquals("yt_dQw4w9WgXcQ.jpg", a.selectFirst("img").attr("src"));
    assertTrue(Files.exists(assets.resolve("yt_dQw4w9WgXcQ.jpg")));
}
```

No Mockito. No `@ExtendWith`. No `@Mock` annotations. The test is a plain
JUnit test that happens to use a subclass. The `fetchCallCount` field lets
you assert that the cache hit path doesn't re-download a thumbnail that
already exists:

```java
@Test
void existingThumbnailNotReDownloaded(@TempDir Path tempDir) throws Exception {
    MockEnricher e = new MockEnricher();
    Files.write(assets.resolve("yt_existing.jpg"), new byte[]{9, 8, 7});

    e.replaceYoutubeEmbeds(a, assets);  // should not call fetchUrl at all

    assertEquals(0, e.fetchCallCount, "cache hit — no HTTP call");
}
```

This pattern generalises to any class with external dependencies you want
to control in tests. The trade-off vs Mockito: you can't verify specific
arguments or call counts beyond what you instrument yourself. The benefit:
zero framework overhead, readable setup, and tests that run in 10ms.

## Building DOM elements: Jsoup as a builder

Python's BeautifulSoup enrichment code builds HTML as a string, then parses
it back:

```python
fig_html = (
    f'<figure class="video-embed">'
    f'<a href="{watch_url}" target="_blank" rel="noopener">'
    f'<img src="{thumb_src}" alt="YouTube video" style="max-width:100%">'
    f'<figcaption>&#9654; Watch on YouTube</figcaption>'
    f'</a></figure>'
)
iframe.replace_with(BeautifulSoup(fig_html, 'html.parser').find('figure'))
```

This works but has two problems: f-string building bypasses HTML escaping
(a URL with a `"` in it would break the attribute), and the parse-then-find
dance is inelegant.

Jsoup has a proper element builder API. You construct the tree directly:

```java
Element fig = new Element("figure").addClass("video-embed");
Element a   = new Element("a")
        .attr("href", watchUrl)
        .attr("target", "_blank")
        .attr("rel", "noopener");
a.appendChild(new Element("img")
        .attr("src", thumbName != null ? thumbName : "")
        .attr("alt", "YouTube video")
        .attr("style", "max-width:100%"));
a.appendChild(new Element("figcaption").text("\u25B6 Watch on YouTube"));
fig.appendChild(a);
iframe.replaceWith(fig);
```

Every `attr()` call goes through Jsoup's encoding — you can pass a raw URL
and it will be escaped correctly in the output. `.text()` encodes HTML
entities. There's no string-then-parse round-trip; the element is constructed
directly and inserted into the existing document tree. The resulting HTML is
identical to the Python version.

The same pattern applies to archive-note fallback figures, Gist figure
captions, and the error figures on API failure. Every `replaceWith()` call
uses a Jsoup-built element rather than a parsed string.

## URL parsing: URI vs urlparse

Python's `urlparse` is one of those standard library modules that you don't
think about until you have to port it. Java's equivalent is `java.net.URI`.
The API is different enough to require care.

```python
# Python — extract YouTube video ID from embed URL
parsed = urlparse(url)
host = parsed.netloc.lower().replace('www.', '')
if '/embed/' in parsed.path:
    return parsed.path.split('/embed/')[-1].split('/')[0].split('?')[0]
```

```java
// Java — extract YouTube video ID from embed URL
URI uri = URI.create(url);
String host = uri.getHost() != null
        ? uri.getHost().toLowerCase().replace("www.", "") : "";
String path = uri.getPath() != null ? uri.getPath() : "";
if (path.contains("/embed/")) {
    String[] parts = path.split("/embed/");
    if (parts.length > 1) {
        String id = parts[1].split("/")[0].split("\\?")[0];
        return id.isEmpty() ? null : id;
    }
}
```

The Java version is longer because `URI.create()` throws if the URL is
malformed (wrap in try-catch), and `getHost()` / `getPath()` can return null
(guard with `!= null`). Python's `urlparse` never throws — it just returns
empty strings. Both behaviours are defensible; Java's forces you to think
about the error case at the call site.

The query string is another difference. Python's `parse_qs` returns a dict
of lists: `qs['v'][0]`. Java's `URI.getRawQuery()` returns the raw query
string: `"v=abc&t=1"` — you split on `&` and find the `v=` prefix. More
primitive, equally effective.

One gotcha: `URI.create()` requires a valid URI. YouTube embed URLs are
always valid, but Gist script `src` attributes occasionally contain
malformed values in the wild. The try-catch around `URI.create()` is
genuinely necessary, not defensive paranoia.

## Porting Python constants: dicts become static maps

Python's brush map is a plain dict:

```python
_BRUSH_MAP = {
    'jscript': 'javascript', 'js': 'javascript',
    'csharp': 'csharp', 'c#': 'csharp',
    'c++': 'cpp', 'cplusplus': 'cpp',
    'plain': 'plaintext', 'text': 'plaintext',
    'shell': 'bash', 'sh': 'bash',
    'drl': 'drl',
}
```

Java's `Map.of()` goes up to 10 pairs. This map has 11. The solution is
a static initialiser block:

```java
private static final Map<String, String> BRUSH_MAP;
static {
    Map<String, String> m = new LinkedHashMap<>();
    m.put("jscript", "javascript"); m.put("js", "javascript");
    m.put("csharp",  "csharp");     m.put("c#", "csharp");
    m.put("c++",     "cpp");        m.put("cplusplus", "cpp");
    m.put("plain",   "plaintext");  m.put("text", "plaintext");
    m.put("shell",   "bash");       m.put("sh",  "bash");
    m.put("drl",     "drl");
    BRUSH_MAP = Collections.unmodifiableMap(m);
}
```

`LinkedHashMap` preserves insertion order. `Collections.unmodifiableMap`
makes it immutable. The result behaves identically to the Python dict for
all uses in `normaliseCodeClasses`.

A subtlety worth noting: the Python regex `r'\bbrush\s*:\s*(\w+)\b'`
captures the language token with `\w+` — which means `brush:c#` would
capture `c` not `c#`, since `#` is not a word character. The entries
`'c#': 'csharp'` and `'c++': 'cpp'` in the brush map are technically
dead code in Python (they'd never match via the brush regex). They're
in the map for direct class name lookup — if a `<pre>` somehow has `c#`
as a class name. We ported them faithfully even though they'll rarely fire.

## Language patterns: preserving order

The language detection patterns are a list of `(language, [patterns])`
tuples in Python:

```python
_LANG_PATTERNS: list[tuple[str, list[str]]] = [
    ('java',   [r'\bpublic\s+class\b', ...]),
    ('xml',    [r'<\?xml\s', r'xmlns=']),
    ('drl',    [r'\brule\s+"', r'\bwhen\b.*\bthen\b', r'\bend\b']),
    # ...
]
```

Order matters — the first matching language wins. In Java, `Map` doesn't
guarantee order, so `Map<String, List<String>>` would be wrong. The
equivalent is `List<Map.Entry<String, List<String>>>`:

```java
private static final List<Map.Entry<String, List<String>>> LANG_PATTERNS = List.of(
    Map.entry("java",  List.of("\\bpublic\\s+class\\b", ...)),
    Map.entry("xml",   List.of("<\\?xml\\s", "xmlns=")),
    Map.entry("drl",   List.of("\\brule\\s+\"", "\\bwhen\\b.*\\bthen\\b", "\\bend\\b")),
    // ...
);
```

`List.of()` preserves insertion order. `Map.entry()` is an immutable key-value
pair. The detection loop is a direct translation of the Python:

```java
outer:
for (Map.Entry<String, List<String>> entry : LANG_PATTERNS) {
    for (String pattern : entry.getValue()) {
        if (Pattern.compile(pattern, Pattern.MULTILINE | Pattern.CASE_INSENSITIVE)
                   .matcher(text).find()) {
            detected = entry.getKey();
            break outer;
        }
    }
}
```

Python's `any(re.search(p, text, re.MULTILINE | re.IGNORECASE) for p in patterns)`
becomes a double loop with a labelled break. `break outer` exits both loops
simultaneously — the Java equivalent of Python's `break` breaking out of
the inner `any()` generator and the outer `for` loop.

One note on pre-compiling: this code compiles the same 21 patterns on every
call to `detectCodeLanguages`. For a bulk enrichment run over 577 posts this
adds up. The patterns could be pre-compiled to `List<Map.Entry<String,
List<Pattern>>>`. We didn't do it — premature optimisation — but it's a
clear next step if profiling shows it matters.

## JSON parsing: Jackson without the annotations

Gist inlining requires parsing the GitHub API response — a JSON object with
nested `files`, each with `content` and `language` fields. Python does this
with `.json()` on the response object, which returns a plain dict:

```python
data = resp.json()
files = data.get('files', {})
for fname, fdata in files.items():
    content  = fdata.get('content', '')
    language = (fdata.get('language') or 'text').lower()
```

In Java, Quarkus includes Jackson. You don't need `@JsonDeserialize` or
mapping classes for a one-off parse — just use the tree API:

```java
JsonNode root  = new ObjectMapper().readTree(json);
JsonNode files = root.path("files");
if (!files.isMissingNode() && files.fields().hasNext()) {
    Map.Entry<String, JsonNode> first = files.fields().next();
    String filename = first.getKey();
    String content  = first.getValue().path("content").asText("");
    String language = first.getValue().path("language").asText("text").toLowerCase();
    // ...
}
```

`path()` returns a `MissingNode` instead of throwing if the key doesn't exist
— safe to chain. `asText("")` returns the string value or the default.
`isMissingNode()` is the null check. The Jackson tree API is the right tool
for ad-hoc JSON navigation without binding to a type; `@JsonDeserialize` into
a class is right when you have a fixed, known schema.

The Python equivalent of `(fdata.get('language') or 'text').lower()` — use
`'text'` if the field is `None` *or* an empty string — needs two calls in
Java:

```java
String lang = first.getValue().path("language").asText("text");
if (lang.isEmpty()) lang = "text";
lang = lang.toLowerCase();
```

`asText("text")` only fires the default for missing nodes, not for an empty
string value. Python's `or` coerces both null and empty to the fallback. Worth
knowing when porting null-or-empty patterns.

## What was easy

The four pure DOM transforms — `normaliseBrToNewlines`, `normaliseCodeClasses`,
`detectCodeLanguages`, `replaceEmbedFallbacks` — are near-literal translations.
No HTTP, no JSON, no file I/O. The only API differences are:

- `br.replace_with('\n')` → `br.replaceWith(new TextNode("\n"))`
- `pre.get('class', [])` → `pre.classNames()` (returns `Set<String>`, never null)
- `code['class'] = new_list` → `code.classNames(newSet)`

Each one is two lines of lookup in the Jsoup docs. The logic itself is
unchanged. TDD made this fast: write the test with the BS4 semantics in mind,
make the Java method satisfy it, done.

The `replaceEmbedFallbacks` method is particularly clean in Java because Jsoup's
element builder handles HTML escaping automatically. In Python you have to call
`html.escape(src)` before interpolating into an f-string. In Java, setting an
attribute via `.attr("href", src)` encodes the value for you. The Java version
is safer by default.

## What was harder

**URL parsing edge cases.** `youtubeVideoId()` handles four URL shapes: embed
paths, `youtu.be` short links, watch URLs with `?v=`, and `youtube-nocookie.com`
embeds. Each has slightly different URI structure. Python's `urlparse` does the
heavy lifting; Java requires manual string splitting after `URI.getPath()`. The
logic is equivalent but getting the null guards right takes a test for each
case.

**Gist script parsing.** `gist.github.com/user/gistid.js` (two path segments)
and `gist.github.com/gistid.js` (one path segment, no user) are both valid.
Python's `parts = parsed.path.strip('/').split('/')` handles both. Java's
`URI.getPath().split("/")` produces leading empty strings if the path starts
with `/` — you need `.replaceAll("^/+", "")` first. A minor gotcha that costs
15 minutes if you don't already know it.

**The Map type mismatch.** `Enricher.enrich()` returns `Map<String, Integer>`.
`StateStore.markEnriched()` takes `Map<String, Object>`. These are not
assignment-compatible in Java — generic types are invariant. The solution:
`new HashMap<>(enrichStats)` with the target type providing inference context.
Java infers `HashMap<String, Object>` and the copy constructor accepting
`Map<? extends K, ? extends V>` does the widening. It compiles, it's correct,
and it looks like it shouldn't work — which is exactly the kind of thing you
should write a comment for.

## The testing pyramid in practice

![Three-layer TDD for Phase 5 — unit, integration, E2E](/blog-images/tdd-pyramid.png)

Phase 5 adds 32 new tests across three layers:

**28 unit tests** cover each enrichment method with multiple inputs: happy
path, failure/fallback, non-matching input, caching behaviour. The `MockEnricher`
inner class supplies all HTTP responses. No network, no file system beyond
`@TempDir`. Tests run in under 200ms total.

**2 integration tests** enrich real KIE archive HTML files. The first enriches
one post and asserts the output file exists and the stats map has the right
keys. The second enriches 10 posts in sequence and asserts all outputs are
written. These run `@EnabledIf("kieArchivePresent")` — they skip on CI or
fresh machines, run locally. Their value is exercising the real content
combinations that 577 posts produce, not just the synthetic snippets in
unit tests.

**2 E2E tests** fire the scan endpoint via `@QuarkusTest` and RestAssured,
triggering enrichment as a side effect of scan. These prove the plumbing:
`PostsResource.scan()` calls `Enricher.enrich()` via the right path,
`StateStore.markEnriched()` is called with the stats, and the endpoint
returns a valid 200 response with the expected fields.

The integration and E2E tests both fail in the JEP-less CI environment —
they need the KIE archive and the Python bridge to be available. This is
the same limitation as previous phases. The unit tests are CI-safe and
catch correctness issues; the integration tests catch behavioural issues
with real content.

## The subagent-driven implementation

Phase 5 used the same subagent-driven development process as Phase 4: a
fresh Claude subagent per task, spec compliance review after each task,
code quality review after spec passes. Eight tasks, eight implementer
dispatches, sixteen review dispatches (spec + quality per task).

The main benefit shows up on the HTTP tasks (Tasks 5 and 6). A single-session
implementation would carry context from the pure DOM tasks into the HTTP
tasks, potentially conflating the two. Fresh-context subagents arrive clean:
they read the task, read the existing files, implement the specific thing,
commit. No accumulated assumptions from six previous tasks.

The review process caught one real bug: `fetchJson()` was returning `""`
(empty string) for a 200 response with an empty body, while `fetchUrl()`
returned `null` in the same case. The inconsistency was caught in code review,
not testing — because the tests mocked successful responses. A test for
"empty body" was not in scope but the reviewer noticed the asymmetry. Fixed
before merge with an `&& !body.isEmpty()` check.

## Comparing the approaches

Two sessions in, a pattern is clear: Python is better at the exploratory,
ad-hoc phase. Java is better at the production, maintainable phase.

| | Python (`enrich.py`) | Java (`Enricher.java`) |
|---|---|---|
| HTTP calls | `requests.get(url, timeout=15)` — one line | Builder + send + handler type — 4 lines |
| JSON parsing | `resp.json()['files']['Foo.java']['content']` | `root.path("files").fields().next().getValue().path("content").asText("")` |
| DOM building | f-string + `BS4(html).find()` | Element builder API, safe by default |
| Type safety | none — runtime errors only | compile-time — `Map<String, Integer>` is caught |
| Testing HTTP | `patch('enrich.requests')` | `MockEnricher` subclass |
| Null safety | `or 'text'` catches both None and `""` | Two separate checks |
| Error messages | Stack trace into dynamic dict | Compile error with type name |

The Python code is shorter in every row. The Java code is more explicit in
every row. "Shorter" wins during development. "More explicit" wins at 3am
during an incident.

## Where we are

JEP call count: **23 → 22**. One bridge function removed:
`bridge.post_enrich_only`. The scan endpoint no longer reaches into Python
for enrichment — it's entirely Java from HTTP receive to enriched HTML output.

```
Phase 0 (JEP bridge):              35 calls — DONE
Phase 1 (config/home):             35 → 32  — DONE
Phase 2 (state.py):                32 → 27  — DONE
Phase 3 (html_utils, code blocks): 27 → 26  — DONE
Phase 4 (scan_html, scan_assets):  26 → 23  — DONE
Phase 5 (enrich.py):               23 → 22  — DONE ← here
Phase 6 (???):                     22 → ?   — next
```

The remaining 22 calls cover the convert pipeline (Markdown generation,
validation), the ingest pipeline (URL discovery, scraping), staging workflow,
and the search endpoint. Each is a self-contained Python module. Phase 6
will be whichever of those the data suggests is highest-value to port next.

The JEP count is dropping. The Python codebase is shrinking. The Java tests
are growing. At some point the crossover happens and the Python code becomes
the minority. That's the direction we're headed.
