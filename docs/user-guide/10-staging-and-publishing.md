---
layout: doc
title: Staging &amp; Publishing
section: Reference
order: 10
---

# Staging & Publishing

The staging workflow lets you review your Markdown edits before committing to them. *Staging* is Sparge's draft system — it saves a copy of your edits alongside the published version so you can compare and decide.

## Staging your edits

After editing the Markdown in the editor, click **Stage**. Sparge writes your edited content to a `.staged` file alongside the current `.md` file. The editor switches to show the staged content.

![Markdown editor showing staged state with Accept and Reject buttons visible](images/10-staged-state.png)
*When a post is staged, the editor shows the staged content and displays Accept and Reject buttons.*

A staged post is indicated in the post list. You can leave posts staged for as long as you like — stage multiple posts, review them all, then accept them one by one.

## Accepting and rejecting

![Accept and Reject staged buttons](images/10-accept-reject.png)
*Accept promotes the staged draft to published. Reject discards it.*

**Accept staged** — promotes the staged content to the published `.md` file and deletes the `.staged` file. Sparge re-validates the accepted content and updates the MD issues.

**Reject staged** — deletes the `.staged` file and restores the previous published content. Your edits are discarded.

> **Note:** Accepting staged content triggers re-validation. If new issues are found in the accepted content, they'll appear in the Issues Panel.

## Publishing

In Sparge, *publishing* means your final Markdown file is ready to copy to your Jekyll (or other static site generator) publishing repository. Sparge writes Markdown to your configured **MD directory** — copy from there to your blog repo to publish.

> **Tip:** Mark a post as **Reviewed** (✓) once you've accepted the staged Markdown and are happy with it. Use the Reviewed filter to track your remaining work.

## Typical end-to-end workflow

1. Scan the post — fix any HTML issues
2. Generate MD — review the generated Markdown
3. Edit the Markdown if needed
4. Stage your edits
5. Accept the staged version
6. Mark as Reviewed
7. Copy the `.md` file to your publishing repository
