# The Editorial Pipeline: A Framework for Rigorous AI-Assisted Writing

**Status:** Draft. Not yet published.

---

The problem with AI-assisted writing is not that it exists. It is that most of it is indistinguishable from careful work and careless work alike. Both are fluent. Both are confident. Both can be wrong.

Simon Willison [coined the term](https://simonwillison.net/2024/May/8/slop/) for the careless kind: slop. Text that is generated without the scrutiny that would catch errors — well-structured, fluent, and wrong. The question worth asking is not whether AI-assisted writing can be slop, but what specifically distinguishes the kind that isn't.

The answer, we think, is process. Not the AI model used, not the length of the prompt, not the subject matter. Process: what happens between the first token generated and the moment something is published.

We searched for an existing named framework and did not find one combining all of: specification before AI generation, gated human approval during drafting, clean-context adversarial review, and a public audit trail — applied specifically to analytical writing. Adjacent frameworks exist: Structured Analytic Techniques (Devil's Advocate, Red Hat analysis) apply adversarial challenge to intelligence analysis; the PAIRR framework (UC Davis, 2025) combines peer and AI review for student writing; the GAR framework (2024) uses LLM agents to simulate peer reviewers of manuscripts. Individual components — HITL approval, red-teaming, audit trails — are well established in their own domains. What appears not to exist is the specific combination for the specific problem: how to structure AI-assisted drafting of analytical content so the human remains genuinely responsible for the argument.

This article proposes one. We call it **The Editorial Pipeline**.

---

## Why a Framework

The case for formalising this is straightforward: without a named process, "I used AI carefully" is unfalsifiable. It can mean anything from "I read the output before publishing" to "I ran three rounds of adversarial review and fixed every finding." These are not the same thing. Readers cannot tell them apart. Authors cannot be held to a standard that isn't stated.

A named framework with defined stages and gates makes the claim specific enough to verify — or falsify. Either the specification was agreed before drafting or it wasn't. Either every section was approved before committing or it wasn't. Either adversarial review was run from a clean context or it wasn't. Either the record is public or it isn't.

The framework we propose is described in the companion piece *["Against AI Slop: How We Made 'When the Machine Codes'"](/articles/against-ai-slop/)*, which documents the process in practice. This article extracts and formalises it.

---

## The Framework: Four Stages, Four Gates

The Editorial Pipeline has four stages. Each stage has a gate — a condition that must be met before the next stage begins. Nothing advances without the gate being passed.

The framework is named after the software development pipeline deliberately. Its disciplines are the same: specification before implementation, implementation reviewed before merging, testing from a clean context, public audit log. The domain is different; the logic is identical.

---

### Stage 1 — Specify

**What happens:** Before any text is generated, the human establishes the argument structure, scope, key claims, and what evidence would support each. This is the specification phase. The AI's role here is to assist the human in articulating the specification — not to generate the argument itself.

**What this prevents:** Arguments that drift from their intended scope; claims added opportunistically during drafting that were never agreed as part of the argument; structure that emerges from what the AI finds easiest to generate rather than what the argument requires.

**The gate:** Explicit human sign-off on the specification before drafting begins. If the specification is not agreed, drafting does not start.

**In practice:** This may take the form of a brainstorming session, an outline review, or a structured Q&A where the AI challenges the specification before accepting it. The key property is that it happens *before* any article text is generated.

---

### Stage 2 — Draft and Gate

**What happens:** The AI generates sections against the specification. The human reviews each section before it is committed to the article — not a light read, but an evaluation of whether the section says what was specified, whether its claims are supported, and whether it introduces anything not agreed in Stage 1.

**What this prevents:** Generated text that sounds correct but drifts from the specification; claims that are too strong for the evidence; framing that favours the AI's prior over the argument's requirements.

**The gate:** Explicit human approval of each section. Nothing reaches the file without a human decision. Sections can be sent back for revision, rewritten from scratch, or rejected entirely. The default is not publication.

**In practice:** The human and AI work section by section. The human reads each section when complete, provides feedback, and explicitly approves or requests revision. "Looks good" is an approval. No response is not.

---

### Stage 3 — Challenge

**What happens:** After the full draft exists, one or more adversarial review sessions are run from a *clean context* — no access to the drafting conversation, with an explicit instruction to challenge the work.

Two modes are available. **General challenge** tasks the reviewer with finding any weakness in logic, evidence, or claim strength — effective for structural problems regardless of subject matter. **Domain-specific advocacy** tasks the reviewer with arguing from a particular perspective (for example, a Python advocate for a series arguing for Java) — effective for finding weaknesses in domain assumptions that general challenge may miss. Domain-specific advocacy is the stronger approach for analytical work with a clear subject-matter position, because it targets the argument's most vulnerable assumptions. Both modes require a clean context with no access to the drafting conversation.

This is the stage most distinct from conventional writing review. The adversarial reviewer is not a collaborator; they are an opponent. They have not seen the drafting conversation and are not trying to help. They are trying to break the argument.

**What this prevents:** Arguments that survive because no one has genuinely tried to defeat them; claims that feel solid in context but collapse under challenge; logical contradictions that neither author nor drafter noticed because both were building in the same direction.

**The gate:** Every finding from the adversarial review is addressed — either fixed, or explicitly rejected with a written reason. Unaddressed findings are publication blockers. The review findings and responses are part of the record.

**In practice:** The session is run in a new conversation with instructions to read the article, identify every weakness, and report findings with severity, location, the specific claim, the challenge, and a suggested fix. Multiple rounds may be run; round N verifies whether round N-1's findings were adequately addressed.

**The limitation:** If all adversarial reviewers are the same AI system, they share the same systematic blind spots. Three rounds of Claude review will not find what Claude does not know it is wrong about. Domain expert review remains necessary for claims that require specialist knowledge. The framework is a floor, not a ceiling.

---

### Stage 4 — Record

**What happens:** The audit trail is made publicly available. This includes: the commit history of the article file (showing what changed and when), the adversarial review findings and responses, and — where possible — the drafting conversations themselves.

**What this prevents:** Process claims that are unfalsifiable; "I reviewed it carefully" that means anything or nothing; a published article where the reader has no way to examine how decisions were made.

**The gate:** Nothing is published without the record being accessible. The repository, review documents, and git history are linked from the article. This is the accountability mechanism.

**In practice:** The article links to the repository. The review documents (`review-round-1.md`, `review-round-2.md`, responses) are committed alongside the article draft. The git history is the commit log of the article file, with descriptive commit messages explaining what changed at each step.

---

## Comparison to Existing Approaches

| Approach | Spec before draft | Gated approval | Adversarial review | Public record |
|---|---|---|---|---|
| **The Editorial Pipeline** | ✓ | ✓ | ✓ | ✓ |
| Standard AI-assisted writing | ✗ | ✗ | ✗ | ✗ |
| HITL (human-in-the-loop) | Varies | ✓ (annotation) | ✗ | ✗ |
| AI safety red-teaming | N/A | N/A | ✓ | Varies |
| Academic peer review | Varies | Varies | ✓ (reviewers) | ✗ (blind) |

The Editorial Pipeline combines practices that exist separately — HITL approval, adversarial challenge, public audit — and applies them specifically to analytical writing. The specification gate and the public record are the elements least common in existing practice.

---

## What the Framework Does Not Guarantee

The framework makes process verifiable. It does not make the argument correct.

An adversarial reviewer using the same AI system will share that system's blind spots. A specification agreed before drafting can still specify the wrong argument. Human approval at each stage is only as good as the human's judgment. Domain expertise is not provided by process.

The [Harvard Business School's research on human-AI oversight](https://www.hbs.edu/ris/Publication%20Files/25-001_8ebbe0cb-2a19-453c-9014-1e301e8dd2fb.pdf) identifies a related risk: better AI assistance can improve task performance while simultaneously reducing the overseer's understanding of the work. A human who approves sections they did not struggle to produce may understand them less than one who wrote them without assistance. The framework addresses process accountability, not cognitive engagement.

These are real limitations. The framework is a minimum standard, not a guarantee. What it provides is the difference between a process claim that is falsifiable and one that is not.

---

## Applying the Framework

The four stages scale to different project sizes. A short analytical post may need a one-paragraph specification, per-section review, a single adversarial pass, and a public gist. A multi-part series may need a full brainstorming session, section-by-section approval across many sessions, multiple adversarial rounds, and a repository with full commit history.

The gates are not optional. A process with Stage 1 and 2 but no Stage 3 is not the Editorial Pipeline — it is a reviewed draft, which is an improvement on unreviewed generation but not the same claim. A process with Stages 1–3 but no public record cannot be verified. The stages are interdependent.

---

## A Case Study

The Editorial Pipeline was abstracted from the practices used in one project — the *When the Machine Codes* series, six articles arguing that statically typed languages produce better outcomes in LLM-first software development. The framework was not applied to that project; it was derived from it. The companion piece [*"Against AI Slop"*](/articles/against-ai-slop/) documents what those practices were and what they found. That article is the source material for this framework, not independent evidence that the framework works. Independent validation — applying the framework to a project where it was specified before the work began — does not yet exist.

The short version of what the practices found: adversarial reviews identified a logical contradiction in the Kotlin recommendation, a stale technical claim about Python 3.13, and an unsourced statistic with no traceable primary source. All three were corrected. The argument that was published is not the same as the argument that entered review. The record of what changed is in the repository.

---

## References

- Simon Willison, *"Slop is the new name for unwanted AI-generated content"* (May 2024) — simonwillison.net/2024/May/8/slop/
- *"Narrative AI and the Human-AI Oversight Paradox"*, Harvard Business School Working Paper 25-001 (2025) — hbs.edu
- *"Your Brain on ChatGPT"*, MIT Media Lab (June 2025) — media.mit.edu/publications/your-brain-on-chatgpt/
- *Enterprise Times, "Agentic AI testing gets adversarial with AI red teaming"* (November 2025) — enterprisetimes.co.uk
- *EU AI Act, Article 14: Human Oversight* — artificialintelligenceact.eu/article/14/
