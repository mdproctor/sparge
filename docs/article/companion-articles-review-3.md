# Adversarial Review Round 3: Post-Round-2 Change Verification + Spec Review
## *Against AI Slop* + *The Editorial Pipeline* + *The Editorial Pipeline: Implementation Specification*

**Reviewer:** Adversarial Claude session (independent — no access to drafting conversations)
**Date:** 2026-04-26
**Scope:** Verification of post-Round-2 changes; secondary check of both articles for anything previous rounds missed; first review of the editorial-pipeline-spec.md companion document

---

## Part 1: Verification of Post-Round-2 Changes

### Change 1: HBS citation rewritten

**Status: RESOLVED — but with a new secondary risk introduced**

The previous HBS citation described a "Human-AI Oversight Paradox" involving "human oversight improving task performance while reducing the overseer's understanding." That characterisation has been replaced in both articles with an accurate description of Lane et al. WP 25-001: AI narrative explanations suppress productive human overrides in innovation screening.

The meta-article now reads: *"evaluators given LLM narrative explanations showed higher compliance with AI recommendations but worse decision quality than those given bare recommendations — the narratives substituted persuasive text for independent verification, suppressing productive overrides."*

The framework article now reads: *"AI-generated narrative explanations suppress productive human overrides, substituting persuasive text for independent verification."*

Both are consistent and accurate to the paper's subject matter.

**Residual concern (IMPORTANT):** The new descriptions characterise the paper's finding with more specificity than can be verified from the abstract alone. The paper is about innovation screening in field experiments. Both articles now apply this finding broadly — to "AI-assisted decision-making" (meta-article) and to the framework's Stage 2 reviewer engagement (framework article). The field experiment setting (evaluating early-stage innovations) is specific; the generalisation to "AI-assisted analytical writing review" is a step not established by the paper itself. This is a narrower form of the same problem the original citation had: accurate description of what the paper is about, but unsupported generalisation from domain-specific evidence to the articles' domain. The original fix correctly repairs the characterisation; the application of the finding still requires a hedge acknowledging the domain difference. Neither article provides that hedge for the HBS paper, even though the MIT paper gets one.

---

### Change 2: MIT Media Lab citation restructured

**Status: RESOLVED**

The hedge now precedes the finding in both articles. In the meta-article: *"though whether it applies here is an open question, since that study measured passive acceptance, not directive collaboration."* This appears before the finding in the sentence, not after it.

The restructuring achieves what Round 1 Finding 12 requested. A reader now encounters the qualification before the finding, not as a walk-back following an apparent assertion.

---

### Change 3: Stage 1 "What happens" rewritten

**Status: RESOLVED — with a residual tension**

The rewritten text reads: *"The AI's role here is to assist the human in articulating and stress-testing the specification — but the human must own the argument before drafting begins. Brainstorming with AI contribution is acceptable; arriving at a specification the human cannot independently defend is not."*

This directly addresses Round 1 Finding 9. It acknowledges brainstorming with AI contribution, draws the line at independent defensibility, and does so in Stage 1 rather than leaving it for the reader to infer from the case study.

**Residual tension (MINOR):** The gate criteria in the framework article ("Explicit human sign-off on the specification before drafting begins") still does not include a "can the author defend this independently" test. The body text now describes this requirement, but the gate criterion that a practitioner would use as a checklist does not include it. The spec document (see Part 3) addresses this gap — but the framework article's gate definition is incomplete on its own terms.

---

### Change 4: Stage 2 "In practice" rewritten

**Status: RESOLVED**

The revised text: *"The human reads each section when complete and evaluates whether it says what was specified, whether its claims are supported, and whether it introduces anything not agreed in Stage 1. A section approved without that evaluation has not passed the gate."*

This fixes Round 1 Finding 7 and Round 2's observation that the gate was defined by form of response ("Looks good") rather than substance of evaluation. The gate is now defined by what was evaluated, not what was said. "Looks good" after that evaluation is an approval is preserved, but now correctly positioned as a conclusion following the evaluation rather than a sufficient act in itself.

---

### Change 5: Stage 3 "What this prevents" — citation verification added

**Status: APPLIED**

The phrase *"citations that exist but are mischaracterised — where the paper is real but the claim attributed to it is not what it says"* has been added to Stage 3's "What this prevents."

This is consistent with the HBS citation fix and with Stage 3's "In practice" addition. It is the correct addition given the prior citation error. No problem with this change.

---

### Change 6: Stage 3 "In practice" — citation verification added

**Status: APPLIED**

The addition reads: *"Citation verification is explicitly in scope: the reviewer should check not only that cited papers exist but that the claims attributed to them are accurate — a paper can be real, findable, and still mischaracterised."*

This is accurate, appropriately placed, and directly motivated by the prior HBS error. No problem with this change.

---

### Change 7: "Why a Framework" — companion description changed

**Status: RESOLVED**

The previous text described the companion piece as one that "documents the process in practice." This implied the companion piece applied the framework, when in fact the framework was derived from the companion's documented practices.

The new text reads: *"documents the practices from which this framework was derived."*

This closes the residual note from Round 2's Blocker 1 verification: that a reader stopping after the introductory framing would carry a slightly misleading impression. The correction is now in the introductory section, not only in the "A Case Study" section where it was already present.

---

### Change 8: Comparison table — HITL note added

**Status: PARTIALLY RESOLVED**

The note added below the table reads: *"HITL in this table refers to annotation and labeling tasks in ML pipelines — a human approving a data label. This is not comparable to a human evaluating the logic, evidence, and fidelity of argumentative text. The activities share a name but not a function."*

This addresses the HITL conflation identified in Round 1 Finding 4 and carried through Round 2.

**Remaining problems (IMPORTANT):**

The other two inaccuracies in the comparison table — identified in Round 1 Finding 4 and marked NOT ADDRESSED in Round 2 — remain unfixed:

1. **"Careful informal AI use" row** — The table still shows "Unreviewed AI generation" and "Careful informal AI use" as two rows (which was the Round 1 suggested fix). But the Round 2 review confirmed the table was unchanged at that point. Looking at the current article: the table has a row labelled "Careful informal AI use" marked as "Varies" on spec before draft and "Varies" on gated approval. This is an improvement over the original "Standard AI-assisted writing" row that scored ✗ across all four dimensions — but the row was already there in the previous version reviewed. Whether this was a pre-existing fix or is new is unclear; regardless, the strawman concern from Round 1 is at least partially addressed by having two rows.

2. **Academic peer review "Varies" for gated approval** — This remains "✓ (post-submission)" in the current table. That cell is now accurate. This appears to have been fixed, contradicting Round 2's claim that it was NOT ADDRESSED. The current table shows "✓ (post-submission)" for academic peer review's gated approval, which was the Round 1 suggested fix.

So: the table now correctly handles HITL (via the note), has two rows for AI use, and correctly marks peer review's gated approval. The HITL note is a good addition. The remaining problem is that the HITL note is below the table, where a reader scanning the table will see the ✓ cell before reading the clarification. The note should ideally be in the table cell itself or immediately adjacent to it in a footnote format — the current placement relies on a reader reaching text they may skip.

---

### Change 9: Two orphaned references removed (Enterprise Times, EU AI Act)

**Status: APPLIED — but creates a new gap**

The two orphaned references have been removed from the framework article's reference list.

**New concern (MINOR):** The framework article no longer cites any regulatory or industry source. This is fine — it never had in-text citations for either. But the removal reveals that the framework article's only citations in the body text are: Willison (slop definition), Lane et al. (HBS), MIT Media Lab, and the three adjacent frameworks (PAIRR, GAR, Structured Analytic Techniques). Of these, PAIRR and GAR were introduced in the Round 2 fix for Blocker 2 and have not been independently verified. Round 2 explicitly flagged this as the highest-priority outstanding item before publication. These citations are still present and still unverified.

---

### Change 10: Opening qualification added to meta-article

**Status: RESOLVED**

The opening now reads: *"Nothing significant went to file without explicit approval — though as the git history section notes, the record proves iteration, not that approval preceded every individual commit."*

This was the Round 1 Finding 10 suggested fix, word for word. The qualification is now in the opening paragraph, not deferred to the Method section. The tension between the strong claim and the later qualification is resolved.

---

## Part 2: Findings From Current State of Both Articles

### Finding 1
**Severity:** Critical
**Applies to:** Framework article
**Location:** Opening section — "I searched Google Scholar, arXiv, and practitioner literature for an existing named framework..."
**The claim:** *"I searched Google Scholar, arXiv, and practitioner literature for an existing named framework and did not find one combining all of: specification before AI generation, gated human approval during drafting, clean-context adversarial review, and a public audit trail — applied specifically to analytical writing."*
**The challenge:** Round 2 flagged the two adjacent framework citations (PAIRR and GAR) as unverified and named this as the highest-priority outstanding item before publication. This has not changed. The PAIRR citation is: *"Sperber et al., 'Peer and AI Review + Reflection (PAIRR): A human-centered approach to formative assessment', Computers and Composition (2025)"* — cited by author, title, journal, and year. The GAR citation is: *"Bougie and Watanabe, 'Generative Adversarial Reviews: When LLMs Become the Critic' (December 2024) — arxiv.org/abs/2412.10415."* If either citation is wrong — wrong title, wrong authors, mischaracterised purpose, or does not exist as described — the article now contains a verifiable error in the section establishing its own novelty claim. The framework article's central positive claim is its novelty; an error in the section establishing novelty is the most damaging possible location for an unverified citation. This remains unresolved from Round 2 and must be verified before publication.
**Suggested fix:** Verify both citations against primary sources before publication. Do not publish until confirmed. If either cannot be verified, remove it rather than carry the risk.

---

### Finding 2
**Severity:** Critical
**Applies to:** Both
**Location:** Framework article — Stage 3 gate definition; Meta-article — "Three Rounds of Adversarial Review"
**The claim:** Framework article: *"Every finding from the adversarial review is addressed — either fixed, or explicitly rejected with a written reason. Unaddressed findings are publication blockers."* Meta-article: *"including one where the fix had been documented in the notes but not actually applied to the file."*
**The challenge:** This is the gate failure finding from Round 1 and Round 2. It has not been addressed. The framework presents Stage 3's gate as a strict requirement; the meta-article documents a case where a finding passed the gate without being properly applied. The articles remain inconsistent. Round 2 correctly identified this as CRITICAL and noted it should have been a named blocker in Round 1's Overall Assessment. Now it has been through three review rounds without being fixed. The Stage 3 "In practice" section now mentions verification rounds being "not optional" — which is an implicit acknowledgment — but does not name gate failures as a known failure mode or explain what to do when one is found. A practitioner implementing this framework will not be warned that a finding can be acknowledged without being applied, and that verification rounds exist specifically to catch this.
**Suggested fix:** Add explicitly to the framework's Stage 3 "In practice" subsection: *"Gate failures happen — a finding may be noted but not applied, or a fix may be partial. This is why verification rounds are not optional: each round verifies that corrections were actually applied to the file, not just acknowledged in responses."* The meta-article does not need to change — it already documents the failure honestly.

---

### Finding 3
**Severity:** Important
**Applies to:** Meta-article
**Location:** "A Note on What This Doesn't Prove" — HBS citation
**The claim:** *"Harvard Business School researchers found a related risk in AI-assisted decision-making: evaluators given LLM narrative explanations showed higher compliance with AI recommendations but worse decision quality than those given bare recommendations."*
**The challenge:** The HBS paper's domain is innovation screening in a field experiment. The meta-article applies the finding to "AI-assisted decision-making" broadly, including by implication to the meta-article's own process of human approval of AI-drafted text. This is a broader generalisation than the paper establishes. The paper finds that LLM narrative explanations suppress productive overrides in evaluating *early-stage innovations* — a specific judgment task. The meta-article's context is a human evaluating argumentative text section by section, with an active directive role. Whether narrative explanations have the same suppressive effect in that context is not established by the paper. The MIT paper gets a hedge noting it "may not apply here" because "that study measured passive acceptance, not directive collaboration." The HBS paper's context (evaluating recommendations with narrative explanations) is somewhat closer to the meta-article's context — but still in a different domain, and the hedge is absent. The asymmetric treatment (MIT gets a hedge, HBS does not) is conspicuous.
**Suggested fix:** Add a parallel hedge: "though the domain is innovation evaluation, not argumentative text review" or similar. The finding is relevant and worth citing — it just needs the same honest framing as the MIT citation.

---

### Finding 4
**Severity:** Important
**Applies to:** Both
**Location:** Framework article — opening; Meta-article — "Three Rounds of Adversarial Review"
**The claim:** Framework article opening: *"I searched Google Scholar, arXiv, and practitioner literature."* Meta-article: *"I ran three independent Claude sessions."*
**The challenge:** Round 2 Finding 6 flagged the "we" vs "I" inconsistency and marked it IMPORTANT. It was not addressed. Looking at the current framework article: the framework article now uses "I" in the opening section ("I searched Google Scholar") but retains "we" in other places ("We call it The Editorial Pipeline," "What appears not to exist is the specific combination..."). The meta-article uses "I" consistently. The inconsistency has narrowed but persists. "We call it The Editorial Pipeline" is the clearest remaining case: if "we" here includes the AI, it implicitly grants co-authorship the meta-article denies; if it is editorial, it should be noted. This has been open since Round 1, is now in Round 3, and remains unresolved.
**Suggested fix:** Either convert all remaining "we" instances in the framework article to "I," or add a note that "we" is an editorial convention and does not imply AI co-authorship.

---

### Finding 5
**Severity:** Important
**Applies to:** Framework article
**Location:** "Applying the Framework" section
**The claim:** *"The four stages scale to different project sizes. A short analytical post may need a one-paragraph specification, per-section review, a single adversarial pass, and a public gist."*
**The challenge:** This finding from Round 1 (Finding 8) was not addressed in either previous round. The only documented application of the Editorial Pipeline is a six-part series. The claim that the framework scales to a short analytical post remains speculative. The spec document (see Part 3) partially addresses this by providing templates that could plausibly work at smaller scale, but the framework article itself makes the scaling claim without qualification and without evidence. A framework article arguing for rigour should not make an unqualified empirical claim about its own applicability that has no documented basis.
**Suggested fix:** Add a qualifier: *"We expect the framework to scale — a short analytical post may need..."* and make clear this is anticipated rather than demonstrated.

---

### Finding 6
**Severity:** Minor
**Applies to:** Framework article
**Location:** Stage 1 gate definition
**The claim:** *"The gate: Explicit human sign-off on the specification before drafting begins. If the specification is not agreed, drafting does not start."*
**The challenge:** The Stage 1 body text now includes the requirement that the author must be able to defend the specification independently. The gate criterion does not include this test. A practitioner using the gate as a checklist will check for "explicit human sign-off" but will not see an independent-defensibility test. The spec document (Part 3 below) includes this as a gate criterion: *"Author can defend the specification without referring to AI output."* The framework article's gate should include the same.
**Suggested fix:** Add to the Stage 1 gate: *"The human can defend the specification independently before signing off."*

---

### Finding 7
**Severity:** Minor
**Applies to:** Framework article
**Location:** Stage 4 — Record, gate definition
**The claim:** *"Nothing is published without the record being accessible."*
**The challenge:** Round 1 Finding 11 flagged that "accessible" is undefined and may not be accessible to the article's intended audience (non-technical readers). This was not addressed. The spec document now defines an accessibility standard in detail (see Part 3 — it requires that a non-technical reader can follow the chain from specification to final article). The framework article still leaves "accessible" undefined. A reader of the framework article cannot tell what accessibility means in practice.
**Suggested fix:** Add a brief definition inline: *"accessible to the article's audience, not only to developers — linked directly from the published article and readable without technical context."*

---

## Part 3: First Review of the Editorial Pipeline Specification

The spec is an implementation document, not a published article. The standard is internal consistency with the framework article and fitness for purpose as an implementer's guide. What follows addresses contradictions, unsupported claims, and anything that would mislead an implementer.

---

### Spec Finding 1
**Severity:** Important
**Applies to:** Spec document
**Location:** Stage 3 — Verification rounds — *"Three rounds is a practical minimum for substantial analytical work; fewer may be sufficient for shorter pieces."*
**The claim:** Three rounds is described as a "practical minimum" for substantial work.
**The challenge:** This is a specific empirical claim derived from the one documented case (the *When the Machine Codes* series, which used three rounds). Describing this as a "minimum" sets a threshold that has no documented basis beyond a single project. A practitioner implementing the spec will read "three rounds is a practical minimum" as a standard. If they run two rounds and find no remaining issues, the spec implies they have not met the minimum — but there is no evidence that three rounds is systematically better than two for shorter or simpler work. The spec elevates a data point from one project to a standard.
**Suggested fix:** Reframe: *"Three rounds was used for the six-part series that motivated this spec. For shorter work, rounds should continue until all findings are resolved, with one verification round minimum after the final fix."* This makes the minimum about resolution, not count.

---

### Spec Finding 2
**Severity:** Important
**Applies to:** Spec document
**Location:** Stage 3 — Mode selection — Hybrid mode
**The claim:** *"Hybrid: Run both modes, either as a single combined instruction or as separate sessions. Broader coverage; higher cost."*
**The challenge:** The framework article defines two modes (general challenge and domain-specific advocacy) without mentioning hybrid. The spec introduces a third mode — hybrid — that has no corresponding entry in the framework article. An implementer reading the spec will encounter a mode not mentioned in the parent document. This is not a contradiction, but it means the spec extends the framework in an undocumented way. If hybrid mode is the most defensible option (broader coverage), it should appear in the framework article's Stage 3 discussion, not only in the spec. The framework article's current text says: *"Domain-specific advocacy is likely the stronger approach for analytical work with a clear subject-matter position."* If hybrid is available and has broader coverage, that claim may be incomplete.
**Suggested fix:** Add hybrid to the framework article's Stage 3 mode discussion, or note in the spec that hybrid mode extends the framework article's two-mode description.

---

### Spec Finding 3
**Severity:** Important
**Applies to:** Spec document
**Location:** Stage 1 gate criteria — *"Author can defend the specification without referring to AI output"*
**The claim:** This is a gate criterion in the spec.
**The challenge:** This criterion is in the spec but not in the framework article's Stage 1 gate definition. The framework article's body text includes: *"arriving at a specification the human cannot independently defend is not"* acceptable. But the gate criterion only says "Explicit human sign-off." An implementer using the framework article alone (without the spec) will not have this criterion in their gate checklist. The spec is more rigorous than the framework article it implements. For a gate criterion this important — it is the operational test for whether the human genuinely owns the argument — the inconsistency matters.
**Suggested fix:** Either add this criterion to the framework article's Stage 1 gate definition, or explicitly note in the spec that it extends the framework article with additional gate criteria.

---

### Spec Finding 4
**Severity:** Important
**Applies to:** Spec document
**Location:** Stage 3 gate criteria — *"No finding is left unaddressed (unaddressed = publication blocker regardless of severity)"*
**The claim:** Every finding, regardless of severity, is a publication blocker if unaddressed.
**The challenge:** This is stricter than the severity table at the top of the spec, which says Minor findings have a gate behaviour of "Fix improves the work; rejection is acceptable with a brief note." An unaddressed Minor finding — one where neither a fix nor a rejection note has been recorded — is a publication blocker under the gate criteria. But the severity table implies Minor findings can be rejected with a brief note, not that they must be addressed. The tension is between "unaddressed = publication blocker regardless of severity" and a severity level that explicitly says rejection (which is a form of addressing) is acceptable. In practice these are reconcilable — "unaddressed" means neither fixed nor rejected, and rejecting with a brief note counts as addressed. But an implementer reading both the severity table and the gate criteria in sequence may not parse this correctly: they may read "unaddressed = publication blocker regardless of severity" as overriding the Minor finding's lighter treatment.
**Suggested fix:** Clarify: *"No finding is left unaddressed — every finding must be either fixed or rejected with a written reason. 'Unaddressed' means neither action has been taken, not that the fix is insufficient."*

---

### Spec Finding 5
**Severity:** Minor
**Applies to:** Spec document
**Location:** Stage 2 — Approval mechanism — *"'Looks good' is a valid approval — after the checklist is completed"*
**The claim:** "Looks good" is a valid approval after checklist completion.
**The challenge:** The framework article now correctly positions "Looks good" as an approval only after the evaluation has been completed. The spec repeats this correctly. This is fine on its own. But the spec's per-section evaluation checklist uses checkboxes, which in practice will be completed in the conversation interface, not in a separate document. An implementer following the spec literally should complete the checklist (checking boxes, presumably in a note or document) before approving — but the spec gives no guidance on how to record the evaluation. "Looks good" after completing a checklist in your head is the same problem the framework article had before the Stage 2 fix. The spec should specify where the checklist evaluation is recorded, or note that the record requirement is satisfied by the git commit log and conversation history.
**Suggested fix:** Add a note: *"The evaluation does not need to be a separate document — a per-section note or inline response identifying what was checked is sufficient. The record requirement is that the evaluation happened, not that it was formatted."*

---

### Spec Finding 6
**Severity:** Minor
**Applies to:** Spec document
**Location:** Stage 4 — Record contents table — *"Response document: Author's response to each finding | docs/article/review-responses.md or inline in review docs"*
**The claim:** Author responses can be inline in review documents.
**The challenge:** If author responses are inline in review documents (that is, the review document is annotated with author responses to each finding), the review document is no longer a clean adversarial record — it is a mixed document where reviewer findings and author responses appear together. This makes it harder for a reader to assess the reviewer's independence, since the record no longer cleanly separates what the reviewer found from how the author responded. The current project's review documents are clean (findings only), with responses tracked separately. The spec should specify which format is preferred and why, rather than offering both as equally valid.
**Suggested fix:** Specify the preferred format: *"Author responses are best kept in a separate document to preserve the clean adversarial record. Inline responses are acceptable for shorter pieces where separation would create unnecessary overhead."*

---

### Spec Finding 7
**Severity:** Minor
**Applies to:** Spec document
**Location:** Stage 3 prompts — Domain-specific advocacy prompt
**The claim:** The prompt template includes *"[domain]"* as a placeholder three times in the prompt body.
**The challenge:** The domain-specific advocacy prompt has a structural issue: the instruction says *"You are an adversarial reviewer arguing from [domain] perspective"* and *"someone who knows [domain] deeply."* In the series case, the domain was Python (a language, an ecosystem, a community with a point of view). The prompt works for that case. But "domain" is underspecified for analytical writing that is not about a technical field — an article about policy, history, or business strategy does not have a "domain" in the same sense. The spec provides no guidance on how to select or define the domain, and no guidance for cases where domain-specific advocacy does not naturally apply.
**Suggested fix:** Add a note: *"Domain refers to the subject-matter position the article's argument is most vulnerable to — not necessarily a technical field. For technical articles: the competing technology or approach. For policy articles: the opposition stakeholder perspective. For analytical arguments: the strongest competing framework. If no natural domain applies, use general challenge instead."*

---

### Spec Finding 8
**Severity:** Minor
**Applies to:** Spec document and framework article
**Location:** Spec — Publication Checklist — *"Minimum one Stage 3 adversarial review completed"*; framework article — "Applying the Framework" — *"a short analytical post may need... a single adversarial pass"*
**The claim:** One Stage 3 review is sufficient for short pieces.
**The challenge:** The spec's Stage 3 verification rounds section says *"Three rounds is a practical minimum for substantial analytical work; fewer may be sufficient for shorter pieces."* The publication checklist says *"Minimum one Stage 3 adversarial review completed."* These are internally consistent — one review is the minimum; multiple are recommended for substantial work. The framework article says a single adversarial pass may be sufficient for a short post. All three are aligned. The problem is that a single adversarial pass with no verification round cannot confirm that findings were actually addressed — which is the explicit purpose of verification rounds. A one-pass review with no verification round means an implementer is taking their own word that the fix was applied, which is exactly the failure mode the gate failure finding (Finding 2 above) describes. A one-pass minimum with no verification round built in is an invitation to the gate failure the framework documented.
**Suggested fix:** Change the minimum from *"one Stage 3 adversarial review"* to *"one Stage 3 adversarial review plus one verification round."* The verification round can be brief; for a short piece with one finding, it may be a single pass. But requiring at least one verification round closes the gate failure path for all project sizes.

---

## Overall Assessment

### Round 2 Blockers

**Blocker 1 (Circular validation):** Resolved. Both articles correctly describe the relationship between the framework and the case study.

**Blocker 2 (Novelty claim — PAIRR and GAR citations):** Not resolved. The citations are still present and still unverified. This remains the highest-priority item before publication. If either citation is wrong, the novelty claim section — the framework's central positive claim — contains a verifiable error. Do not publish without primary-source verification of both.

**Blocker 3 (Stage 3 instruction mismatch):** Resolved. Both articles now consistently describe two modes plus the trade-off of domain-specific advocacy.

**Round 2 Issue — Gate failure acknowledgment:** Not resolved. This has been open since Round 1 and has not been addressed in three rounds. The fix is one sentence; it should be made before publication. (Finding 2 above.)

**Round 2 Issue — Comparison table:** Partially resolved. HITL conflation is addressed by the note below the table, though the note placement (below the table rather than inline) still requires a reader to reach text they may skip. The peer review gate cell now correctly shows "✓ (post-submission)." The "Careful informal AI use" row appears to have been present previously. The table is improved; remaining placement issue with the HITL note is minor.

### Publication Readiness

**Both articles: Not yet publication-ready.** Two items prevent it:

1. **PAIRR and GAR citations unverified** (Finding 1 above). This is a Critical item that has been carried from Round 2 without resolution. The fix requires one targeted research action, not editorial work — verify the citations against primary sources and confirm the characterisations are accurate.

2. **Gate failure unacknowledged in the framework article** (Finding 2 above). This has been Critical since Round 1 and remains unfixed. One sentence in Stage 3's "In practice" block resolves it.

Fix both items, then publish.

### Spec Consistency with Framework Article

The spec is largely consistent with the framework article but extends it in three meaningful ways without acknowledging the extension:

- Hybrid mode (Spec Finding 2) is introduced in the spec but absent from the framework article.
- Independent defensibility gate criterion (Spec Finding 3) is in the spec but not in the framework article's gate definition.
- Minimum three rounds (Spec Finding 1) elevates a single-project data point to a standard.

The spec is a useful implementer's guide. Its internal logic is sound. The mismatch with the framework article on these points should be addressed by either adding the spec's extensions to the framework article or noting in the spec that it extends (rather than only implements) the framework.
