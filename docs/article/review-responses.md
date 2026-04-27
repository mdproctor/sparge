# Review Responses
## *Against AI Slop* + *The Editorial Pipeline* + *Editorial Pipeline Spec*

**Note:** This document was compiled after all review rounds were complete, reconstructed from review documents and article changes. It records the author's decision for each finding across all rounds.

---

## Round 1 — companion-articles-review.md

**Finding 1 — Circular validation (Critical)**
Decision: Fixed. Both articles now explicitly state the framework was derived from the case study, not applied to it. Independent validation does not yet exist. Language added to "A Case Study" section of framework article and closing paragraph of meta-article.

**Finding 2 — Gate failure (Critical)**
Decision: Fixed. Stage 3 "In practice" now reads: "Gate failures happen — a finding may be noted but not applied, or a fix may be partial. This is why verification rounds are not optional."

**Finding 3 — Novelty claim unsubstantiated (Critical)**
Decision: Fixed. A literature search was conducted (Google Scholar, arXiv, practitioner literature). The claim was narrowed and three adjacent frameworks named: Structured Analytic Techniques, PAIRR, GAR. All three citations verified against primary sources in this session.

**Finding 4 — Comparison table unfair (Important)**
Decision: Partially fixed across multiple rounds. "Standard AI-assisted writing" row split into "Unreviewed AI generation" and "Careful informal AI use." Academic peer review gated approval changed from "Varies" to "✓ (post-submission)." HITL row removed in Round 3 pass (Round 3 independent Finding 6). HITL note below table retained in framework article prose.

**Finding 5 — "We" vs "I" inconsistency (Important)**
Decision: Fixed. Framework article now uses "I" throughout. The only remaining "we" is in the title of the companion piece, which is a proper name.

**Finding 6 — Stage 3 instruction mismatch (Important)**
Decision: Fixed. Framework article Stage 3 now defines three modes: general challenge, domain-specific advocacy, and hybrid. Meta-article acknowledges Python-specific framing was deliberate and notes the trade-off.

**Finding 7 — Stage 2 gate by form not quality (Important)**
Decision: Fixed. Stage 2 "In practice" now: "A section approved without that evaluation has not passed the gate." "Looks good" repositioned as a valid approval after the evaluation, not instead of it.

**Finding 8 — Scalability asserted not evidenced (Important)**
Decision: Fixed. Changed to "expected to scale" with explicit note: "though this has not been documented in practice; the only completed application is the six-part series from which the framework was derived."

**Finding 9 — Stage 1 brainstorming blurred (Important)**
Decision: Fixed. Stage 1 now: "Brainstorming with AI contribution is acceptable; arriving at a specification the human cannot independently defend is not."

**Finding 10 — "Nothing went to file" ordering (Minor)**
Decision: Fixed. Opening now: "Nothing significant went to file without explicit approval — though as the git history section notes, the record proves iteration, not that approval preceded every individual commit."

**Finding 11 — Stage 4 "accessible" undefined (Minor)**
Decision: Fixed. Gate now reads: "accessible to the article's audience — linked directly from the published article and readable without technical context."

**Finding 12 — MIT citation hedge ordering (Minor)**
Decision: Fixed. Hedge now precedes the finding: "though whether it applies here is an open question, since that study measured passive acceptance, not directive collaboration."

**Finding 13 — Cross-reference URLs are placeholders (Minor)**
Decision: Noted. Will be resolved at publication — both articles must go live simultaneously. Publication blockers added to both article headers.

---

## Round 2 — companion-articles-review-2.md

**Blocker 1 — Circular validation (verification)**
Decision: Resolved. Both articles state the derivation relationship explicitly.

**Blocker 2 — Novelty claim, PAIRR and GAR citations (verification)**
Decision: Resolved. Both citations verified against primary sources in this session: PAIRR confirmed from PDF (Sperber et al., UC Davis, *Computers and Composition* 76, 2025); GAR confirmed from arXiv abstract (Bougie and Watanabe, arXiv 2412.10415, 2024).

**Blocker 3 — Stage 3 instruction mismatch (verification)**
Decision: Resolved. Three-mode definition now in framework article and spec.

**Finding 4 — Comparison table inaccuracies (Important, not a blocker)**
Decision: See Round 1 Finding 4. Progressive fix across rounds.

**Finding 5 — Gate failure still unacknowledged (Critical)**
Decision: Fixed. See Round 1 Finding 2.

**Finding 6 — "We" vs "I" (Important)**
Decision: Fixed. See Round 1 Finding 5.

**Round 2 new concern — HBS citation**
Decision: Fixed. HBS paper verified from PDF. Title corrected to *"The Narrative AI Advantage? A Field Experiment on AI-Augmented Evaluations of Early-Stage Innovations"* (Lane et al., 2024). Body text recharacterized accurately: AI narrative explanations suppress productive human overrides in innovation screening. Domain hedge added in both articles.

Supporting evidence from abstract: *"we find that black-box recommendations improve decision quality, whereas narrative explanations do not, despite inducing higher compliance. This divergence arises because narratives produce asymmetric compliance: evaluators disproportionately follow rejection recommendations, substantially increasing false negatives. Mechanism analyses show that narratives suppress productive overrides by substituting persuasive text for independent verification."*

---

## Round 3 Independent — companion-articles-review-3-independent.md

**Finding 1 — Production revision note in spec (Critical)**
Decision: Fixed. Italicised editorial note deleted from hybrid mode section.

**Finding 2 — No response documents exist (Critical)**
Decision: Fixed. This document created as the response record.

**Finding 3 — HBS characterization requires verification (Important)**
Decision: Verified. HBS paper (Lane et al., WP 25-001) confirmed from PDF in this session. "Suppressing productive overrides" and "worse decision quality when given narrative explanations vs. bare recommendations" are accurate characterizations of the paper's findings. Domain hedge present in both articles. Publication blocker removed.

Supporting evidence from abstract: *"we find that black-box recommendations improve decision quality, whereas narrative explanations do not, despite inducing higher compliance... narratives suppress productive overrides by substituting persuasive text for independent verification."*

**Finding 4 — PAIRR and GAR require verification (Important)**
Decision: Verified. PAIRR confirmed from PDF (Sperber et al.). GAR confirmed from arXiv. Both characterizations accurate. Publication blockers removed.

PAIRR supporting evidence from abstract: *"Peer and AI Review + Reflection (PAIRR) combines peer review best practices with AI review in an approach that emphasizes student agency and reflection... Results indicate that AI tools offer useful feedback when combined with peer review."* Characterization ("combines peer and AI review for student writing") confirmed accurate.

GAR supporting evidence from abstract: *"we introduce Generative Agent Reviewers (GAR), leveraging LLM-empowered agents to simulate faithful peer reviewers... GAR performs comparably to human reviewers in providing detailed feedback and predicting paper outcomes."* Characterization ("uses LLM agents to simulate peer reviewers of manuscripts — focused on approximating academic reviewer judgments") confirmed accurate.

**Finding 5 — Spec unlinked from framework article (Important)**
Decision: Fixed. Reference and link added to framework article.

**Finding 6 — HITL row confused signal (Important)**
Decision: Fixed. HITL row removed from comparison table. Educational distinction between HITL annotation and Stage 2 approval retained in prose note below table.

**Finding 7 — Domain-specific advocacy recommendation scope (Important)**
Decision: Fixed. Recommendation now scoped: domain-specific advocacy is stronger for domain-specific claims; general challenge or hybrid is needed for structural/logical problems not tied to subject matter.

**Finding 8 — "No article text" ambiguous in spec (Minor)**
Decision: Fixed. Clarified: "No article prose has been drafted before this point. Brainstorming output, outlines, and specification drafts generated during Stage 1 do not count as article text."

**Finding 9 — "We welcome that" (Minor)**
Decision: Fixed. Changed to "I welcome that."

**Finding 10 — GAR distinction not stated (Minor)**
Decision: Fixed. Sentence added distinguishing GAR from Stage 3: clean-context requirement, structured finding format, gated process role.

**Finding 11 — Spec minimum verification round inconsistency (Minor)**
Decision: Fixed. Framework article Stage 3 "In practice" now states minimum one verification round requirement, consistent with spec.
