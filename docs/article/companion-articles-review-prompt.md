# Adversarial Review: Companion Articles

You are an adversarial reviewer. Review two linked articles as a body of work — they reference each other and together make a claim about the rigour of AI-assisted writing. Challenge both individually and as a pair.

## Read these files first

```
~/claude/sparge/docs/article/meta-article-draft.md
~/claude/sparge/docs/article/framework-article-draft.md
```

Read both in full before proceeding.

## Context

These are companion articles:

1. **"Against AI Slop"** — a case study documenting how a six-part article series (*When the Machine Codes*) was produced using AI assistance. Claims the process makes the output rigorous rather than "slop."

2. **"The Editorial Pipeline"** — a proposed four-stage framework (Specify → Draft and Gate → Challenge → Record) for rigorous AI-assisted writing, drawn from the practices described in the case study.

They link to each other. The framework article cites the case study as its documented example. The case study article points to the framework as the formalised version of its process.

## Your task

Challenge everything — weak claims, unsourced assertions, circular reasoning, overclaiming, consistency failures between the two articles, and anything a hostile reader would attack.

**For the meta-article ("Against AI Slop"), focus on:**
- Whether the "human's hand" examples are representative or cherry-picked
- Whether the process claims are falsifiable or merely procedural
- Whether "the core claim held" is a fair characterisation of what the reviews actually found
- Whether the limitations are stated prominently enough or buried

**For the framework article ("The Editorial Pipeline"), focus on:**
- Whether the four stages and gates are sufficiently defined to be replicable
- Whether the comparison table is fair to existing approaches (HITL, red-teaming, peer review)
- Whether the claim "we are not aware of a named framework" is substantiated or assumes its own novelty
- Whether the limitations section adequately qualifies the framework's claims
- Whether this is a genuinely useful framework or a post-hoc rationalisation of one team's process

**For both articles as a linked body of work:**
- Do they contradict each other anywhere?
- Does the framework article make claims that the case study article doesn't support?
- Does the case study article promise something the framework article doesn't deliver?
- Is the circular risk managed — that the case study validates a framework that was derived from the case study?
- Are the cross-references accurate (do the linked sections actually exist and say what is claimed)?

## Output format

Write your findings to:
```
~/claude/sparge/docs/article/companion-articles-review.md
```

Structure each finding as:

```markdown
## Finding N: [Brief title]
**Severity:** CRITICAL / IMPORTANT / MINOR
**Applies to:** Meta-article / Framework article / Both
**Location:** [Section name]
**The claim:** [What is said]
**The challenge:** [Your counter-argument]
**Suggested fix:** [What should change]
```

End with **Overall Assessment** covering both articles: what are the two or three most serious remaining issues, and are these articles publication-ready as a pair?

Be especially rigorous on the circularity question — the framework is derived from the case study, and the case study is validated by the framework. A hostile reader will spot this immediately.
