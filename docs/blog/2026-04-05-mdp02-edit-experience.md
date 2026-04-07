---
typora-root-url: ../..
---

# Sparge — the edit experience

**Date:** 2026-04-05
**Type:** phase-update

---

## What I was trying to achieve: an editor worth using

Sparge could review posts. What it couldn't do was edit them comfortably. The HTML editor was a plain `<textarea>` — workable for short changes, unusable for a post where the entire article body was on a single line. "What is a Rule Engine" from 2006 was one long string. You couldn't navigate it, couldn't find a paragraph, couldn't make a targeted fix.

I brought Claude in for a proper edit experience.

## CodeMirror and a redesigned layout

We added CodeMirror — syntax highlighting for both HTML and Markdown, line numbers, proper indentation. That solved the editor itself. But the layout still put the editor inside one of the review panels, which meant losing the HTML view or the MD view while editing.

The redesign I wanted: enter edit mode and the nav sidebar becomes edit controls — Save, Discard, Back to review. The middle panel becomes the CodeMirror editor. The right panel becomes a live preview, updated as you type and scroll-synced with the editor.

Claude and I built the whole thing in one session. HTML edits preview in an iframe via `srcdoc`. Markdown edits render through `marked.js`. The scroll sync uses a percentage-based position so editor and preview stay aligned regardless of content length.

[![Sparge edit mode — click to enlarge](/assets/blog/sparge-edit-mode-thumb.jpg)](../../assets/blog/sparge-edit-mode.png)
*Three-partition edit mode: edit controls on the left, CodeMirror in the middle, live preview on the right.*

## The prettify bug

The single-line HTML problem needed fixing independently of the editor. The solution was to prettify the HTML before loading it into CodeMirror — BeautifulSoup's `prettify()` adds newlines and indentation without changing what renders.

I made the change and immediately the Markdown view started showing garbled text: em dashes and curly quotes turning into `ÃÂÃÂ¢ÃÂÃÂÃÂÃÂ`. The symptom pointed everywhere except the actual cause — file encoding, browser charset, database issues. The actual cause was one word: `lxml`.

BeautifulSoup with the `lxml` parser does charset sniffing. When it sees `<meta charset="utf-8">` in the HTML, it re-encodes the Python string to UTF-8 bytes internally, then serialises those bytes as Latin-1. Every non-ASCII character double-encoded. The fix was switching to `html.parser`, which treats the input string as-is with no charset magic.

```python
# ❌ double-encodes non-ASCII via <meta charset> sniffing
content = BeautifulSoup(raw, 'lxml').prettify()

# ✅ treats str as-is
content = BeautifulSoup(raw, 'html.parser').prettify()
```

One word. Several hours of debugging to find it.
