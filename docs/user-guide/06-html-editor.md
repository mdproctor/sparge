---
layout: doc
title: The HTML Editor
section: Editors
order: 6
---

# The HTML Editor

The left pane in the split-pane view is the HTML editor. It shows the *enriched* version of your post's HTML — the version that Sparge's pipeline operates on.

## The editor

![CodeMirror HTML editor with syntax highlighting](images/06-html-editor.png)
*The HTML editor: CodeMirror with full HTML syntax highlighting and line numbers.*

The editor is a full [CodeMirror](https://codemirror.net/) instance with HTML syntax highlighting. Edit the HTML directly here to fix issues that Sparge can't auto-correct.

> **Note:** You're editing the *enriched copy* of the HTML, not the original source. The original HTML in your posts directory is never modified.

## Saving and reverting

Click **Save** to write your changes to the enriched copy. Click **Revert** to discard your edits and restore the last saved version. After saving, click **Scan** to re-check the HTML with your changes applied.

## Issue highlighting

![HTML editor with a problematic element highlighted](images/06-issue-highlight.png)
*Clicking an issue in the Issues Panel jumps to and highlights the relevant element in the editor.*

When you click an issue in the **Issues Panel**, the editor scrolls to and highlights the HTML element that caused the issue. This makes it easy to locate and fix problems in long posts.

## Autosync scroll

The HTML and Markdown editors scroll together. As you scroll through the HTML on the left, the Markdown editor on the right follows proportionally, keeping the corresponding content in view.
