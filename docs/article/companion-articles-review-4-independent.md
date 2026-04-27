# Adversarial Review Round 4: Verification Pass
## *Against AI Slop* + *The Editorial Pipeline* + *Editorial Pipeline Spec*

**Reviewer:** Adversarial Claude session (independent — no access to drafting conversations)
**Date:** 2026-04-26
**Scope:** Verify Round 3 fixes; brief secondary pass for material issues not previously surfaced.

---

## Round 3 Finding Verification

**Round 3 Finding 1 — Production revision note in spec**
Status: APPLIED
Evidence: The italicised self-referential note is absent from the hybrid mode section; the section now reads cleanly to "Broader coverage; higher cost." with no editorial commentary following.
New problem: None.

---

**Round 3 Finding 2 — No response documents**
Status: APPLIED
Evidence: `review-responses.md` exists, covers all findings across all rounds, and includes the note that it was compiled retrospectively.
New problem: The spec's Stage 4 record table was changed as part of this fix to make the response document conditional — "Required when any finding is rejected." In the original spec it was always required. This is a defensible change on the merits, but it reduces a requirement the articles couldn't meet at the time the finding was raised. A hostile reader may note that the spec was amended to accommodate a compliance gap rather than the gap being remediated against the original standard.

---

**Round 3 Finding 3 — HBS characterization requires verification**
Status: PARTIAL
Evidence: The response document records "confirmed from PDF in this session" with a paraphrase of the finding. The articles' characterization of the HBS paper — "evaluators given LLM narrative explanations showed higher compliance with AI recommendations but worse decision quality" — is unchanged.
New problem: The verification is author-reported, not evidence-recorded. The response document says the characterization is accurate but quotes no passage from the paper that supports it. The spec's citation verification protocol requires that "the specific claim we attribute to the paper is supported by the paper's actual content." A verifier reading the response document cannot confirm the verification was adequate — there is no quoted evidence. This matters particularly because the HBS paper's title ("The Narrative AI Advantage?") signals the paper may be more equivocal than the citation implies. The verification happened in the same session that produced the articles; that is author self-verification, not independent verification.

---

**Round 3 Finding 4 — PAIRR and GAR require verification**
Status: PARTIAL
Evidence: The response document records verification "from PDF" (PAIRR) and "from arXiv abstract" (GAR). Full bibliographic details are in the articles.
New problem: Same as Finding 3: the verification is author-reported with no quoted supporting evidence in the record. A reader checking Stage 4 compliance cannot confirm the citations are accurate from the response document alone. GAR's characterization — "uses LLM agents to simulate peer reviewers of manuscripts" — is verifiable from an abstract, but the verification record does not demonstrate this. PAIRR's characterization — "combines peer and AI review for student writing" — similarly needs the quoted evidence that the abstract supports it.

---

**Round 3 Finding 5 — Spec unlinked from framework article**
Status: PARTIAL
Evidence: The framework article's "Why a Framework" section now reads: "An implementation guide — with specification templates, per-section evaluation checklists, adversarial review prompts, and a citation verification protocol — is available as a [companion specification document](../docs/article/editorial-pipeline-spec.md)."
New problem: The link uses a relative path (`../docs/article/editorial-pipeline-spec.md`). If the framework article is published at a URL such as `/articles/the-editorial-pipeline/`, this path resolves to `/articles/docs/article/editorial-pipeline-spec.md` — which does not exist. The spec is in the repository at `docs/article/editorial-pipeline-spec.md` relative to the repo root, not relative to `/articles/`. The link will be broken in publication unless the URL is corrected to an absolute path (the GitHub repository URL or a published URL for the spec). This should be a named publication blocker.

---

**Round 3 Finding 6 — HITL row creates confused signal**
Status: PARTIAL
Evidence: The HITL row has been removed from the comparison table. The note below now explains why: "Human-in-the-loop (HITL) approval in ML pipelines — a human approving a data label — is not included here. Approving a label and evaluating the logic, evidence, and fidelity of argumentative text are different activities that share a name but not a function."
New problem: The paragraph immediately following the table and note reads: "The Editorial Pipeline combines practices that exist separately — HITL approval, adversarial challenge, public audit — and applies them specifically to analytical writing." Having just told the reader that HITL annotation is not comparable to Stage 2 approval and that the two activities "share a name but not a function," the article then describes Stage 2 as "HITL approval" — using the term it just distanced itself from. A reader who absorbed the note will be confused: the note said HITL isn't the same thing; the paragraph says Stage 2 IS HITL approval. The fix was applied to the table but not to the paragraph that follows it.

---

**Round 3 Finding 7 — Domain-specific advocacy scope**
Status: APPLIED
Evidence: Stage 3 now reads: "Domain-specific advocacy is likely the stronger approach for finding weaknesses in domain-specific claims... For structural, logical, or evidence-quality problems not tied to the subject-matter position, general challenge may be necessary in addition — which is why the hybrid mode exists."
New problem: None.

---

**Round 3 Finding 8 — "No article text" ambiguous in spec**
Status: APPLIED
Evidence: Stage 1 gate criteria now reads: "No article prose has been drafted before this point. Brainstorming output, outlines, and specification drafts generated during Stage 1 do not count as article text — they are specification artefacts."
New problem: None.

---

**Round 3 Finding 9 — "We welcome that"**
Status: APPLIED
Evidence: Meta-article closing paragraph now reads "I welcome that."
New problem: None.

---

**Round 3 Finding 10 — GAR distinction not stated**
Status: APPLIED
Evidence: GAR description now reads: "focused on approximating academic reviewer judgments rather than structured adversarial challenge of a predetermined argument from a clean context."
New problem: None.

---

**Round 3 Finding 11 — Spec minimum verification round inconsistency**
Status: APPLIED
Evidence: Framework article Stage 3 "In practice" now includes: "At minimum, one verification round should be run after all findings from the initial review are addressed — to confirm that corrections were applied to the file and not just acknowledged."
New problem: None.

---

## Secondary Pass — New Findings

Three full rounds have covered this ground thoroughly. Raising only Important issues.

**Secondary Finding A: Post-table paragraph contradicts the HITL note**
**Severity:** Important
**Applies to:** Framework article
**Location:** "Comparison to Existing Approaches" — paragraph following the table and note
**The claim:** "The Editorial Pipeline combines practices that exist separately — HITL approval, adversarial challenge, public audit — and applies them specifically to analytical writing."
**The challenge:** The note immediately above this paragraph states that HITL annotation and Stage 2 approval "share a name but not a function" — that is, they are not the same activity. The note was added to explain why HITL was excluded from the table. The paragraph then uses "HITL approval" to describe Stage 2 — the activity the note just said is not HITL. A reader who absorbed the note has been told Stage 2 is not HITL; the paragraph then says Stage 2 is HITL approval. This is a direct contradiction introduced by the Finding 6 fix, which removed HITL from the table but left the paragraph unchanged.
**Suggested fix:** Replace "HITL approval" in this paragraph with "gated human approval" or "section-by-section human approval" to avoid reintroducing the term the note just excluded.

---

**Secondary Finding B: Spec link will break at publication**
**Severity:** Important
**Applies to:** Framework article
**Location:** "Why a Framework" section
**The claim:** `[companion specification document](../docs/article/editorial-pipeline-spec.md)`
**The challenge:** This is a relative path from the article file's location in the repository. When the framework article is published as a blog post (e.g., at `/articles/the-editorial-pipeline/`), the relative path `../docs/article/editorial-pipeline-spec.md` resolves to `/articles/docs/article/editorial-pipeline-spec.md` — not to the spec. The link will be broken on publication. The correct target is either the GitHub repository URL for the spec file, or a published URL if the spec is hosted separately.
**Suggested fix:** Replace the relative path with an absolute URL before publication — either the GitHub file URL (`https://github.com/mdproctor/sparge/blob/main/docs/article/editorial-pipeline-spec.md`) or a published URL. Add this as a named publication blocker until the correct URL is confirmed.

---

**Secondary Finding C: Citation verification evidence is not in the record**
**Severity:** Important
**Applies to:** Review-responses.md, all articles
**Location:** Round 2 new concern (HBS); Round 3 Findings 3 and 4
**The claim:** The response document records for three citations: "confirmed from PDF in this session" (HBS), "confirmed from PDF" (PAIRR), "confirmed from arXiv abstract" (GAR).
**The challenge:** The spec's citation verification protocol requires: "the specific claim we attribute to the paper is supported by the paper's actual content — abstract at minimum; full text where the claim is specific or load-bearing." For a reader to verify this, they need to see the relevant passage from the paper — or at minimum a quote confirming the characterization. "Confirmed from PDF" is a declaration, not evidence. The verification was author-conducted, not independent, and no supporting quotes are recorded. This means the Stage 4 record does not allow a reader to follow "the chain: specification → draft → review findings → responses → final article" at the citation verification step — the chain breaks at "I checked it." Three citations, all load-bearing, all author-verified with no recorded evidence.
**Suggested fix:** Add to the response document, under each citation entry, the relevant quoted passage from the paper that confirms the characterization. Even one sentence per citation would make the verification legible to a reader. For HBS: quote the finding about compliance and decision quality. For PAIRR: quote the abstract's description of the framework's scope. For GAR: quote the abstract's description of the simulation approach.

---

## Overall Assessment

**Not yet publication-ready.** Three issues require resolution before the articles go live.

**Blocker 1 — Post-table HITL paragraph contradiction (Secondary Finding A).** This is a one-line fix that was created by the Finding 6 fix. Change "HITL approval" to "gated human approval" in the paragraph following the comparison table. It is a small edit but leaves the article internally contradictory if left as-is.

**Blocker 2 — Spec link broken at publication (Secondary Finding B).** The relative path `../docs/article/editorial-pipeline-spec.md` will not resolve correctly once the framework article is published. This should be a named publication blocker: "Spec link must be updated to absolute URL before publishing." It cannot be resolved until the spec's published URL is known.

**Blocker 3 — Citation verification not evidenced in the record (Secondary Finding C).** Three load-bearing citations were verified by the author with no quoted supporting evidence in the response document. The spec's own citation verification standard requires evidence. Adding brief quoted passages from each paper closes this gap and makes the Stage 4 record self-contained.

Findings 3 and 4 (PARTIAL) are the underlying issue behind Blocker 3 — the verifications were done but not documented. Findings 5 (PARTIAL) is Blocker 2. Finding 6 (PARTIAL) is Blocker 1.

Everything else is solid. Nine of eleven Round 3 fixes are cleanly applied. The articles are coherent, the structural and circularity issues from prior rounds are genuinely resolved, and the core argument about process rigour is credibly made. The remaining blockers are all resolvable — they are documentation and URL gaps, not argument problems.
