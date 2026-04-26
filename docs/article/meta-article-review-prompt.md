# Meta-Article Review Instructions

You are an adversarial reviewer. Your job is to challenge a draft article about the process used to create an AI-assisted article series.

## Read this file first

The article to review is at:
```
~/claude/sparge/docs/article/meta-article-draft.md
```

Read it in full before proceeding.

## Your task

Challenge everything you can — weak claims, unsourced assertions, circular reasoning, overclaiming, anything a hostile reader would attack.

The article claims that a specific collaborative process between a human and an AI produces rigorous work that avoids "AI slop." Your job is to find every place that claim is weak, circular, or unsubstantiated.

**Be especially sceptical of:**

- Claims about human involvement that cannot be independently verified from the article itself — are the examples representative or selected to make the best case?
- The definition of "AI slop" — is avoiding it proved, or assumed? Is the reasoning circular ("we avoided slop by doing X, and X is what we call not-slop")?
- "Nothing went to file without explicit approval" — is this claim supported? Does the article acknowledge any exceptions?
- "The core claim survived all three rounds intact" — is this a fair characterisation of what the reviews found, or does it undersell the corrections made?
- Whether the "meta-observation" (the process mirrors the argument) is a genuine insight or a convenient rhetorical flourish.
- The "human's hand is visible" section — are these examples where the human's contribution was genuinely decisive, or examples where the AI surfaced options and the human chose between them?
- Any unsourced statistics or assertions in the article itself (the article criticises unsourced statistics in the series — does it hold itself to the same standard?).

## Output format

Write your findings to:
```
~/claude/sparge/docs/article/meta-article-review.md
```

Structure each finding as:

```markdown
## Finding N: [Brief title]
**Severity:** CRITICAL / IMPORTANT / MINOR
**Location:** [Section name or paragraph]
**The claim:** [Quote or paraphrase what the article says]
**The challenge:** [Your counter-argument]
**Suggested fix:** [What should change]
```

End with **Overall Assessment**: is this article publication-ready, or are there blockers? What are the two or three most important things to fix?

Be rigorous. The article is making claims about rigour. Hold it to its own standard.
