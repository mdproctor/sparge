---
layout: post
title: "Phase 4: Porting 16 HTML issue detectors from BeautifulSoup to Jsoup"
date: 2026-04-15
type: phase-update
entry_type: note
subtype: diary
projects: [sparge]
tags: [Quarkus, Java, Python, migration, Jsoup, BeautifulSoup, TDD]
typora-root-url: /Users/mdproctor/claude/sparge/docs
---

Phase 4 is the scan pipeline — `scan_html.py`, 780 lines, 16 issue detectors,
the most-used operation in the whole application. Every time you click Scan in
the editor, this code runs. Porting it removes three more JEP bridge calls and
makes the scan endpoint entirely Java-backed.

![16 HTML issue detectors — scan_html.py ported to ScanHtml.java](/blog-images/scan-issues.png)

The 16 detectors span four categories: image issues (lazy-load artefacts,
tracking pixels, missing files), embed issues (empty iframes, unreplaced Gists),
code block issues (no newlines, linenumber tables, span-tokenised DRL), and text
issues (WordPress chrome, html2text adjacency). Each one has a type, a severity
(ERROR or WARN), a human-readable detail string, and a CSS selector targeting
the problematic element for in-browser highlighting.

## BeautifulSoup to Jsoup — the API is remarkably similar

The first question when porting DOM manipulation Python is always: what's the
Java equivalent of BeautifulSoup? The answer is Jsoup, and it's a closer match
than you might expect.

![BeautifulSoup vs Jsoup — the API comparison](/blog-images/bs4-jsoup.png)

CSS selector syntax is identical — `.entry-header`, `img[src]`,
`script[src*=gist]` all work in both libraries. The attribute API differs only
in name: `img.get('src', '')` becomes `img.attr("src")` (which returns `""` for
absent attributes rather than requiring a default). Class lists are
`img.get('class', [])` in Python versus `img.classNames()` returning a
`Set<String>` in Java.

The one genuine difference: text node handling. BeautifulSoup's `next_sibling`
returns a `NavigableString` for text; Jsoup's `nextSibling()` returns a `Node`
which might be a `TextNode`. In practice this is one `instanceof` check:

```python
# Python
sib = tag.next_sibling
if isinstance(sib, NavigableString) and sib and not sib[0].isspace():
    adjacent_char = sib[0]
```

```java
// Java
Node sib = tag.nextSibling();
if (sib instanceof TextNode tn) {
    String text = tn.getWholeText();
    if (!text.isEmpty() && !Character.isWhitespace(text.charAt(0))) {
        char adjacent = text.charAt(0);
```

Java 16+ pattern matching (`instanceof TextNode tn`) makes this concise.
Everything else in the scan logic is a near-literal translation.

## The CSS selector generator

One of the more interesting pieces in `scan_html.py` is `_selector()` — it
generates a CSS selector for any element so the browser can highlight it in the
HTML editor. The logic walks up to 6 levels up the DOM tree, using
`:nth-of-type()` when siblings share the same tag name.

```python
# Python — _selector()
def _selector(tag: Tag) -> Optional[str]:
    if tag.get('id'):
        return f'#{tag["id"]}'
    parts = []
    el = tag
    for _ in range(6):
        parent = el.parent
        siblings = [s for s in parent.children
                    if isinstance(s, Tag) and s.name == el.name]
        if len(siblings) > 1:
            idx = siblings.index(el) + 1
            parts.append(f'{el.name}:nth-of-type({idx})')
        else:
            parts.append(el.name)
        el = parent
    parts.reverse()
    return ' > '.join(parts)
```

```java
// Java — ScanHtml.selector()
public static String selector(Element el) {
    if (el.hasAttr("id") && !el.id().isEmpty()) return "#" + el.id();
    List<String> parts = new ArrayList<>();
    Element current = el;
    for (int depth = 0; depth < 6; depth++) {
        Element parent = current.parent();
        if (parent == null) break;
        String tag = current.tagName();
        if (tag.equals("html") || tag.equals("body") || tag.equals("article")) break;
        List<Element> siblings = parent.children().stream()
                .filter(e -> e.tagName().equals(tag))
                .collect(Collectors.toList());
        if (siblings.size() > 1) {
            parts.add(tag + ":nth-of-type(" + (siblings.indexOf(current) + 1) + ")");
        } else {
            parts.add(tag);
        }
        current = parent;
    }
    Collections.reverse(parts);
    return String.join(" > ", parts);
}
```

The logic is identical. Jsoup's `parent.children()` returns direct child
elements (not all descendants), matching BS4's `[s for s in parent.children
if isinstance(s, Tag)]`. The stream filter replaces the list comprehension.

## Three-layer TDD

The user requirement for Phase 4 was explicit: unit tests, integration tests,
end-to-end tests, happy paths. Here's how we structured it:

![Three-layer TDD for Phase 4 — unit, integration, E2E](/blog-images/tdd-pyramid.png)

**Unit tests** were written first. Before `ScanHtml.java` existed, we wrote 49
tests covering every detector with at least: a happy path (issue IS detected),
a negative path (clean HTML is NOT flagged), and a level check (ERROR vs WARN).
The helper:

```java
private static Element article(String html) {
    return Jsoup.parse("<article>" + html + "</article>").selectFirst("article");
}

private static List<ScanHtml.Issue> scan(String html) {
    return ScanHtml.checkAll(article(html));
}
```

Each test is two or three lines. No file I/O, no JVM overhead, runs in under 5ms.

**Integration tests** scan real HTML files from the KIE archive:

```java
@Test
@EnabledIf("kieArchivePresent")
void scanSinglePostReturnsValidIssueList() throws Exception {
    Path post = Files.list(KIE_POSTS)
            .filter(p -> p.toString().endsWith(".html"))
            .findFirst().orElseThrow();

    List<ScanHtml.Issue> issues = ScanHtml.scanPost(post, KIE_POSTS);

    assertNotNull(issues);
    for (ScanHtml.Issue issue : issues) {
        assertTrue(issue.level().equals("ERROR") || issue.level().equals("WARN"));
    }
}
```

`@EnabledIf("kieArchivePresent")` skips the test on CI or fresh machines where
the archive isn't present. The point of these tests is to exercise real content
— synthetic snippets don't exercise every detector combination that 577
production posts produce.

**E2E tests** run the full Quarkus server in-process via `@QuarkusTest` and
make real HTTP calls with RestAssured. The one wrinkle: `@QuarkusTest` starts
the server but never calls `/api/projects/{id}/activate` via HTTP. Java's
`ActiveProject` CDI singleton is only populated by that endpoint call — without
it, `activeProject.getConfig()` returns null and the scan falls back to the
(now-removed) bridge.

The fix is a `@BeforeEach`:

```java
@BeforeEach
void activateProject() {
    if (!kieArchivePresent()) return;
    given().when().get("/api/projects")
            .then().statusCode(200)
            .extract().jsonPath()
            .<List<Map<String,Object>>>getList("$")
            .stream().findFirst().ifPresent(project -> {
                String id = (String) project.get("id");
                given().contentType("application/json")
                       .when().post("/api/projects/" + id + "/activate")
                       .then().statusCode(200);
            });
}
```

This is a useful pattern for any `@QuarkusTest` that exercises authenticated or
session-stateful endpoints: activate/login/setup in `@BeforeEach`, test the
thing, don't assume any state is inherited from the server's own startup.

## What was easy

Most detectors are simple attribute checks — exactly the kind of thing where
Python and Java look nearly identical:

```python
# Python — check_unreplaced_gists
for script in article.find_all('script', src=True):
    src = script.get('src', '') or ''
    if 'gist.github.com' in src:
        issues.append(_issue('unreplaced_gist', 'ERROR', ...))
```

```java
// Java — checkUnreplacedGists
for (Element script : article.select("script[src]")) {
    String src = script.attr("src");
    if (src.contains("gist.github.com"))
        issues.add(issue("unreplaced_gist", "ERROR", ...));
}
```

`find_all('script', src=True)` becomes `select("script[src]")` — the CSS
attribute presence selector does the same thing. The logic fits in two lines in
both languages.

## What was harder

The WordPress chrome detector has two detection paths: CSS selector-based (known
class names) and text-pattern-based (short paragraphs matching regex patterns
like "by Mark Proctor" or "Leave a Reply"). Both are straightforward in
isolation; the combination is what requires care.

The Python constants file (`constants.py`) already had a migration note:
"TRACKING_DOMAINS → Set&lt;String&gt;, CSS_JUNK_SELECTORS → List&lt;String&gt;, etc."
— whoever wrote that comment was thinking ahead. `SpargeConstants.java` is a
direct implementation of that note.

The `suspicious_code_content` detector is subtle. It looks for
HTML-encoded markup inside code blocks — `&lt;table&gt;` inside `<pre><code>`.
The check is on `code.outerHtml()` (which includes the encoded entities as-is),
not on `code.text()` (which would decode them). This matters because BS4's
`str(code)` and Jsoup's `code.outerHtml()` both preserve the raw HTML source
with entities intact.

## Where we are

JEP call count: **26 → 23**. The scan endpoint is fully Java-backed. The enrich
step (YouTube thumbnails, Gist inlining) still calls Python — that's Phase 5.
dismiss and undismiss now call `StateStore.dismissHtmlCheck()` and
`StateStore.undismissHtmlCheck()` directly in Java, eliminating two more bridge
calls.

Phase 5 is `enrich.py`. After that the conversion pipeline, then ingest. Each
phase removes more JEP calls. The call count is the migration metric — it will
reach zero.
