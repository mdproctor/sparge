# The Editorial Pipeline: Implementation Specification

**Companion to:** *The Editorial Pipeline: A Framework for Rigorous AI-Assisted Writing*
**Purpose:** Defines each stage with enough precision to implement as a tool, checklist system, or guided application. Where the framework article explains *why*, this document specifies *what exactly*.

---

## Severity Levels

Used in all review findings. Defined here once; referenced throughout.

| Level | Definition | Gate behaviour |
|---|---|---|
| **Critical** | Publication blocker. The claim is false, the logic is circular, or the evidence directly contradicts the assertion. | Must be fixed or explicitly rejected with written reason before publication. |
| **Important** | Significant weakness that undermines credibility if unaddressed. | Should be fixed. Rejection requires written justification. |
| **Minor** | Precision issue, framing problem, or potential misread. | Fix improves the work; rejection is acceptable with a brief note. |

---

## Stage 1 — Specify

### Inputs required before this stage begins
- A topic or thesis the author proposes to argue

### Process
1. Author proposes the argument in one sentence.
2. AI assists in expanding: key claims, required evidence, scope boundaries, what would falsify the argument.
3. AI challenges the specification before accepting it — identifying weaknesses, gaps, or unsupported assumptions.
4. Author revises until they can defend the specification independently.
5. Author explicitly signs off.

### Specification template

```
Title: [working title]
Thesis: [one sentence — the argument]
Audience: [who this is written for]
Scope:
  - In: [what the argument covers]
  - Out: [what it explicitly does not claim]
Key claims:
  1. [claim] — evidence required: [what would support this]
  2. [claim] — evidence required: [what would support this]
  ...
What would falsify this argument: [honest statement]
Agreed: [author sign-off — date and explicit approval]
```

### Gate criteria
- [ ] Specification completed using template above
- [ ] AI has challenged the specification (at least one challenge round)
- [ ] Author can defend the specification without referring to AI output
- [ ] Author has explicitly signed off
- [ ] No article prose has been drafted before this point. Brainstorming output, outlines, and specification drafts generated during Stage 1 do not count as article text — they are specification artefacts.

---

## Stage 2 — Draft and Gate

### Process
1. AI generates one section at a time against the specification.
2. Human evaluates the section against the checklist below.
3. Human explicitly approves or requests revision.
4. Approved sections are committed to the draft file.
5. Rejected or revised sections are not committed until approved.

### Per-section evaluation checklist

For each section, the human must evaluate:
- [ ] Does this section say what was specified for it?
- [ ] Are all claims supported by cited evidence or stated as assertion?
- [ ] Does it introduce any claim, framing, or scope not agreed in Stage 1?
- [ ] Is the claim strength proportional to the evidence (not overclaimed)?
- [ ] Is this the human's argument, or has the AI introduced its own framing?

A section approved without completing this evaluation has not passed the gate.

### Approval mechanism
- Explicit positive response after evaluation = approved
- Revision request = not approved; section is revised and re-evaluated
- No response = not approved; default is revision, not publication
- "Looks good" is a valid approval — *after* the checklist is completed. The evaluation does not need to be a separate document — a per-section note or inline response identifying what was checked is sufficient. The record requirement is that the evaluation happened, not that it was formatted.

### Gate criteria
- [ ] Every section has been explicitly approved
- [ ] No section reached the draft file without human decision
- [ ] All approvals followed evaluation against the checklist above

---

## Stage 3 — Challenge

### Review session setup
- New conversation with no access to the drafting session
- No prior context about the argument's development
- Explicit adversarial instruction: the reviewer's goal is to find weaknesses, not to help

### Mode selection

**General challenge:** Find any weakness in logic, evidence, structure, or claim strength. Use when structural integrity is the primary concern.

**Domain-specific advocacy:** Argue from the perspective of the argument's strongest opponent (e.g., a Python advocate for a Java-preferring series). Use for analytical work with a clear subject-matter position — forces the reviewer into the position most likely to find domain assumptions. May miss weaknesses outside that frame. *Domain refers to the subject-matter position the article's argument is most vulnerable to — not necessarily a technical field. For technical articles: the competing technology or approach. For policy articles: the opposition stakeholder perspective. For analytical arguments: the strongest competing framework. If no natural domain applies, use general challenge instead.*

**Hybrid:** Run both modes, either as a single combined instruction or as separate sessions. Broader coverage; higher cost.

The mode used must be recorded. The review findings reflect the mode's scope.

### Review output format

Each finding must use this structure:

```
**Finding N**
**Severity:** Critical / Important / Minor
**Applies to:** [which article or section]
**Location:** [section name and specific passage or claim]
**The claim:** [exact text being challenged]
**The challenge:** [why this is a problem — logic, evidence, or accuracy]
**Suggested fix:** [specific, actionable recommendation]
```

### Citation verification protocol

Citation verification is explicitly in scope for Stage 3. For every citation in the article, verify:

- [ ] Paper exists and is accessible at the cited URL or DOI
- [ ] Title matches exactly
- [ ] Authors match (correct names, correct order)
- [ ] Venue, journal, or conference and year are correct
- [ ] The specific claim we attribute to the paper is supported by the paper's actual content — abstract at minimum; full text where the claim is specific or load-bearing
- [ ] If the paper is behind a paywall, the abstract supports the claim and access has been confirmed by the author

A paper that exists but is mischaracterised is a citation error. Title accuracy alone is not sufficient.

### Gate criteria
- [ ] Every finding is addressed — either fixed in the draft or explicitly rejected with a written reason
- [ ] Rejected findings have a written justification (one sentence minimum)
- [ ] No finding is left unaddressed — every finding must be either fixed or explicitly rejected with a written reason. "Unaddressed" means neither action has been taken, not that the fix is insufficient. A Minor finding rejected with a brief note is addressed; a Critical finding acknowledged but not fixed is not.
- [ ] All citations have been verified against the citation checklist above

### Verification rounds
- Round N verifies whether round N-1's findings were adequately addressed — not just acknowledged
- A finding noted in responses but not applied to the file has not passed the gate
- Verification rounds continue until all findings are resolved
- Rounds continue until all findings are resolved — the minimum is resolution, not count. One verification round after the final fix is the minimum for any project size. Three rounds was used for the six-part series that motivated this spec; that is a data point, not a standard.

### Overall Assessment format

Each review round ends with:

```
**Overall Assessment**
Blockers remaining: [N — list them]
Important findings unresolved: [N — list them]
Publication-ready: Yes / No
If no: [what must change before the next round]
```

---

## Stage 4 — Record

### Record contents

The following must exist and be accessible before publication:

| Item | What it is | Where it lives |
|---|---|---|
| Specification | Stage 1 output | `docs/article/spec.md` or equivalent |
| Draft file | Final article text | `docs/article/[article-name].md` |
| Review documents | One per round: all findings | `docs/article/review-round-N.md` |
| Response document | Author's decision for each finding: fixed, rejected with reason, or deferred with reason | Required when any finding is rejected — the rejection reason must be recorded somewhere a reader can find it. For projects where all findings are fixed, the git history and article diffs constitute an adequate implicit record; a formal response document adds clarity but is not mandatory. If created, preferred location is `docs/article/review-responses.md`. If compiled after the fact, note that at the top. |
| Git history | Commit log with descriptive messages | Repository commit log |
| Published links | Article links to repository | Inline in published article |

### Accessibility standard

The record must be accessible to the article's audience, not only to developers:

- [ ] The repository is linked directly from the published article
- [ ] Review documents are written in plain language — no git knowledge required to read them
- [ ] A non-technical reader can follow the chain: specification → draft → review findings → responses → final article
- [ ] The git history uses descriptive commit messages that explain what changed and why (not "update draft")

### Publication blockers

A publication blocker is a named, specific condition that must be resolved before an article goes live. It lives in the article's status header — not in a review document or a separate note — where it is visible to whoever is about to publish.

Format:
```
**Publication blockers:**
- [Specific condition that must be met. Remove this line only when resolved.]
```

Common blockers:
- A companion article that must be published simultaneously
- A citation that requires primary-source verification before going live
- A cross-link whose target URL does not yet exist

A blocker is removed from the status header only when the condition is fully met. An article with an unresolved publication blocker in its header is not ready to publish, regardless of editorial state.

### Gate criteria
- [ ] All record items exist and are committed to the repository
- [ ] Repository link appears in the published article
- [ ] Review documents are readable without technical context
- [ ] All publication blockers in the status header have been resolved and removed
- [ ] Article status header updated from "Draft. Not yet published." to publication date

---

## Publication Checklist

Final gate before publication. All items must be checked.

**Process:**
- [ ] Stage 1 specification signed off and committed
- [ ] All Stage 2 sections explicitly approved
- [ ] Minimum one Stage 3 adversarial review completed, plus one verification round confirming corrections were applied to the file (not just acknowledged)
- [ ] All Stage 3 findings addressed (fixed or rejected with written reason)
- [ ] All citations verified against citation checklist

**Content:**
- [ ] No unresolved Critical findings
- [ ] All Important findings either fixed or rejected with justification
- [ ] Cross-links between paired articles resolve correctly
- [ ] All URLs in the article have been checked for accessibility

**Record:**
- [ ] All record items committed to repository
- [ ] Repository linked from article
- [ ] All publication blockers in the status header resolved and removed
- [ ] If any findings were rejected: rejection reasons are recorded in a response document or inline annotation
- [ ] Status header updated to publication date

**Coordination (for paired articles):**
- [ ] Both articles reviewed as a pair in at least one review round
- [ ] Cross-references between articles are consistent
- [ ] Articles published simultaneously or forthcoming note added to whichever publishes first

---

## Prompts

### Stage 1 — Specification challenge prompt

```
I am about to write an article arguing [thesis]. Before any drafting begins, I want you to challenge the specification.

Here is the specification:
[paste specification]

Challenge this: identify weaknesses in the argument, claims that are unsupported, scope that is too broad or too narrow, and anything that a hostile reader would immediately attack. Do not help me improve it — identify what is wrong with it. Report each problem with a suggested question I should be able to answer before drafting begins.
```

### Stage 3 — General challenge prompt

```
You are an adversarial reviewer. You have no context from the drafting process. Your goal is to find weaknesses in this article — not to help, but to break the argument.

Read the article below. Report every weakness you find: logical errors, unsupported claims, overclaiming, citations that may be inaccurate, structural problems, and anything a hostile expert would attack.

For each finding use this format:
**Finding N**
**Severity:** Critical / Important / Minor
**Applies to:** [section]
**Location:** [specific passage]
**The claim:** [exact text]
**The challenge:** [why this is a problem]
**Suggested fix:** [specific recommendation]

End with an Overall Assessment: is this publication-ready? If not, what are the blockers?

[paste article]
```

### Stage 3 — Domain-specific advocacy prompt

```
You are an adversarial reviewer arguing from [domain] perspective. You have no context from the drafting process. Your goal is to argue against this article as its most capable opponent — someone who knows [domain] deeply and believes the article is wrong.

Read the article below. Find every weakness from [domain] perspective: claims the domain would dispute, evidence the domain would reject, framing that misrepresents how [domain] actually works, and conclusions that don't follow from the evidence as a [domain] practitioner would evaluate it.

For each finding use this format:
**Finding N**
**Severity:** Critical / Important / Minor
**Applies to:** [section]
**Location:** [specific passage]
**The claim:** [exact text]
**The challenge:** [why this fails from [domain] perspective]
**Suggested fix:** [specific recommendation]

End with an Overall Assessment: is the core argument defensible from [domain] perspective? What would a [domain] expert find most damaging?

[paste article]
```

### Stage 3 — Verification round prompt

```
You are an adversarial reviewer verifying whether fixes from a previous review were adequately applied.

Read the article, the previous review findings, and the author's responses. For each finding marked as fixed: verify the fix was actually applied to the article text, not just acknowledged. For each finding marked as rejected: verify the rejection reason is adequate.

Previous review: [paste review-round-N.md]
Author responses: [paste responses]
Current article: [paste article]

Report:
- For each claimed fix: APPLIED / PARTIAL / NOT APPLIED — with evidence
- For each rejection: ADEQUATE / INADEQUATE — with reason
- Any new problems introduced by the fixes

End with Overall Assessment: are the blockers resolved? Is this publication-ready?
```
