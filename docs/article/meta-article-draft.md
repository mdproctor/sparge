# Against AI Slop: How We Made *"When the Machine Codes"*

**Status:** Draft. Not yet published.

*A note on method before anyone reads the series.*

---

The obvious objection to an article written with AI assistance is that it might be sophisticated-sounding nonsense — well-structured, fluent, and wrong. There is now enough AI-generated content in the world that readers have developed a reasonable prior: text that moves quickly and sounds confident is probably not rigorous. This is not unfair.

The six-part series published here — *When the Machine Codes*, arguing that statically typed languages are better suited to LLM-first software development than Python — was written with Claude as the primary drafter and me as the architect, reviewer, and approver of every sentence. That makes it AI-assisted in a specific sense: the AI generated text; I directed, challenged, and accepted or rejected it. Nothing went to file without explicit approval.

What it does not make it is fast or unchecked. This is an account of the process — because the process is what makes the difference between a serious argument and text that looks like one.

---

## The Method: Spec-Led Article Writing

The series was built the same way the series argues software should be built: design specification first, implementation second, adversarial review third.

Before any drafting began, we ran a full brainstorming session to establish the argument structure, identify the key claims, stress-test the framing, and agree on scope. The series title, the six-part structure, the language comparison table, the two-hypothesis treatment of the accuracy gap, the distinction between training data bias and structural simplicity — all of these were established before a word of article text was written. Each section was proposed, agreed, and only then drafted.

During drafting, every section was shown before being committed. Every significant claim required approval. Several were revised before they touched a file. This is slower than generating the article in one pass. It is also the only way to produce something where the human is actually responsible for the argument.

The git history tells this story more precisely than I can. There are over 80 commits in the article files' history — each with a message explaining what changed and why. An article generated in one pass and minimally edited does not produce a git history that looks like this.

---

## Where the Human's Hand Is Visible

The places where this process produced something different from what the AI would have generated alone are worth being specific about.

**The Kotlin governance argument.** Early drafts justified the preference for Java over Kotlin on the grounds of "training data volume and enterprise familiarity" — which is circular. The series spends two articles arguing that training data bias is an *illegitimate* reason to prefer Python over Java, then used the same reasoning to prefer Java over Kotlin. When I pushed back on this, we did proper research: the Kotlin Foundation's governance structure, the distinction between OpenJDK's multi-vendor community meritocracy and Kotlin's directed governance model under JetBrains. The final argument has four concrete non-anthropocentric reasons. None of them were in the first draft.

**The Sparge evidence for LLM defaults.** A draft section claimed that "LLMs don't currently default to generating Pydantic-typed Python" — an empirical assertion without evidence. When challenged by the adversarial reviewer, the natural response would have been to remove the claim. My observation was that we already had evidence: the Sparge Python server, built by an LLM from design specifications without instruction to use typed patterns, had used plain Python dictionaries throughout. The project the series was documenting was itself the evidence. That connection was mine, not the AI's.

**Challenging retroactive narrative.** At one point, the AI characterised the JEP bridge — the mechanism used to migrate incrementally from Python to Java — as "a red flag from day one." It wasn't. The JEP bridge was a deliberate, well-designed migration tool, introduced after the decision to port was made, to enable incremental transition. The AI was reading the end state backwards and constructing a narrative from it. I corrected that. The revised article is more honest and, as a consequence, a more credible account of what actually happened.

**The adversarial review idea.** Running independent Claude sessions to argue against the series was my suggestion. The AI would not have proposed this — it has no incentive to challenge its own output. Three rounds of that process found things two authors working in good faith had missed.

**The "Rust is strongest" claim.** An early comparison table described Rust as having the "strongest" type system. I questioned this. Rust's type system is strongest in the sense of what it prevents — memory safety, data races — but for application development, where a garbage collector already handles memory safety, Rust's additional constraints are a complexity cost without commensurate benefit. The table was revised to make that distinction precise.

These are not corrections of factual errors. They are places where the human's judgment shaped what the argument was allowed to claim.

---

## Three Rounds of Adversarial Review

After the series was drafted, I ran three independent Claude sessions — separately from the session that wrote the series — with a single instruction: argue against it from Python's perspective. Find every weakness. Be as hostile as the argument deserves.

Each session received no context from the others and no access to the conversation that produced the series. They read the articles cold and reported what they found.

**Round one** produced 18 findings. Critical issues included: a primary source cited as load-bearing but described as "not directly accessible at time of writing" (the primary source turned out to be accessible — a paper accepted at PLDI 2025); a logical contradiction in the Kotlin recommendation; the GIL claim applied to Python 3.13 as though free-threaded mode didn't exist.

**Round two** verified whether the responses to round one were adequate. Six residual issues remained — including one where the fix had been documented in the notes but not actually applied to the file.

**Round three** found three remaining blockers before publication, all precision issues rather than argument failures. Its conclusion: *"the series argument is genuinely interesting and the core insight is sound. The review process has been rigorous precisely because the argument is worth making well."*

The core claim survived all three rounds intact. It was sharper for having been challenged.

---

## What the Challenge Found

Some of what the reviews found was correction. The Fortune 500 statistic ("90% of Fortune 500 companies use Java for core backend systems") was circulating widely but had no traceable primary source. A figure described as "attributed to ETH Zurich/UC Berkeley — primary source not directly accessible" turned out to be a properly accessible paper. The GIL claim was stale. Several instances of "the verbosity is in the output, the savings are in the cycles" — a decent line — appeared three times across different articles doing the same work each time. Repetition at that scale is filler, not emphasis.

Some of what the reviews found was strengthening. The Kotlin recommendation became a better argument when the circular reasoning was removed and replaced with evidence. The LLM defaults claim became more defensible when grounded in a specific observation rather than an assertion. The Pydantic characterisation became more honest when we acknowledged that well-engineered modern Python (FastAPI, Pydantic v2, pyright strict) is substantially stronger than the baseline, and that the real remaining distinction is compile-time versus runtime enforcement — not the presence or absence of types.

---

## The Meta-Observation

The most striking thing about this process is that it mirrors the argument.

The series argues that LLM-first development works best when the human writes the specification and the LLM implements it; when the implementation is reviewed and challenged; when errors are caught before they reach production. Design the argument before drafting it. Challenge it before publishing it. Let the challenge produce a stronger version rather than just a defended one.

That is also what happened here.

---

## A Note on What This Doesn't Prove

This process does not guarantee the argument is correct. Three rounds of adversarial review by an AI system find what an AI system finds — which may not be what a domain expert, a practising Java architect, or a Python maintainer would find. The series has not been peer-reviewed. The controlled study it calls for does not exist.

The review process found logical contradictions, unsourced statistics, stale technical claims, and overclaiming language. It did not find that the core argument was wrong. That is the honest characterisation of what three rounds of challenge produced.

*The review documents, export files, and git history are all in the repository. The record is there for anyone who wants to check the work.*

*It is also possible that a domain expert would find things three rounds of Claude did not. We welcome that. The series calls for a controlled study that might prove some of its own claims wrong — which is either intellectual honesty or a peculiar form of optimism, depending on whether the study eventually gets done.*
