# Against AI Slop: How We Made *"When the Machine Codes"*

**Status:** Draft. Not yet published.

*A note on method before anyone reads the series.*

---

Simon Willison [coined the term](https://simonwillison.net/2024/May/8/slop/) in 2024: slop is unwanted AI-generated content, the new spam. "Don't publish slop," he wrote — meaning the problem is not AI assistance itself but the absence of editorial accountability. Merriam-Webster made it [word of the year in 2025](https://www.pbs.org/newshour/nation/merriam-websters-word-of-the-year-for-2025-is-ais-slop). The broader debate is more nuanced — Deni Ellis Béchard [argued in Scientific American](https://www.scientificamerican.com/article/ai-slop-how-every-media-revolution-breeds-rubbish-and-art/) that every media revolution produces rubbish alongside valuable work — but for analytical writing, the concern is specific: text that sounds rigorous but was generated without the kind of scrutiny that would catch errors. That kind of text exists. There is a lot of it.

The six-part series published here — *When the Machine Codes*, arguing that statically typed languages are better suited to LLM-first software development than Python — was written with Claude as the primary drafter and me as the architect, reviewer, and approver of every sentence. That makes it AI-assisted in a specific sense: the AI generated text; I directed, challenged, and accepted or rejected it. Nothing went to file without explicit approval.

This is an account of the process — because the process is what makes the difference between a serious argument and text that looks like one.

---

## The Method: Spec-Led Article Writing

The series was built the same way the series argues software should be built: design specification first, implementation second, adversarial review third.

Before any drafting began, we ran a full brainstorming session to establish the argument structure, identify the key claims, stress-test the framing, and agree on scope. The series title, the six-part structure, the language comparison table, the two-hypothesis treatment of the accuracy gap, the distinction between training data bias and structural simplicity — all of these were established before a word of article text was written. Each section was proposed, agreed, and only then drafted.

During drafting, every section was shown before being committed. Every significant claim required approval. Several were revised before they touched a file. This is slower than generating the article in one pass. It is also the only way to produce something where the human is actually responsible for the argument.

The git history is the record — over 80 commits, each with a message explaining what changed and why. What it proves is iteration: that the text was revised across many sessions rather than generated in one pass. It cannot prove that every commit followed explicit approval; for that you would need to trust the account given here.

---

## Where the Human's Hand Is Visible

The places where this process produced something different from what the AI would have generated alone are worth being specific about.

**The Kotlin governance argument.** Early drafts justified the preference for Java over Kotlin on the grounds of "training data volume and enterprise familiarity" — which is circular. The series spends two articles arguing that training data bias is an *illegitimate* reason to prefer Python over Java, then used the same reasoning to prefer Java over Kotlin. When I pushed back on this, we did proper research: the Kotlin Foundation's governance structure, the distinction between OpenJDK's multi-vendor community meritocracy and Kotlin's directed governance model under JetBrains. The final argument has four concrete non-anthropocentric reasons. None of them were in the first draft.

**The Sparge evidence for LLM defaults.** A draft section claimed that "LLMs don't currently default to generating Pydantic-typed Python" — an empirical assertion without evidence. When challenged by the adversarial reviewer, the natural response would have been to remove the claim. My observation was that we already had evidence: the Sparge Python server, built by an LLM from design specifications without instruction to use typed patterns, had used plain Python dictionaries throughout. The project the series was documenting was itself the evidence. That connection was mine, not the AI's.

**Challenging retroactive narrative.** At one point, the AI characterised the JEP bridge — the mechanism used to migrate incrementally from Python to Java — as "a red flag from day one." It wasn't. The JEP bridge was a deliberate, well-designed migration tool, introduced after the decision to port was made. The AI was reading the end state backwards and constructing a narrative from it. I corrected that.

**The adversarial review idea.** Running independent Claude sessions to argue against the series was my suggestion. The AI would not have proposed this unprompted — whether it would have if asked, I cannot say. What I can say is that it didn't, and that three rounds of that process found things the drafting process had missed.

**The "Rust is strongest" claim.** An early comparison table described Rust as having the "strongest" type system. I questioned this. Rust's type system is strongest in the sense of what it prevents — memory safety, data races — but for application development, where a garbage collector already handles memory safety, Rust's additional constraints are a complexity cost without commensurate benefit. The table was revised to make that distinction precise.

*These are the clearest examples of decisive intervention. Many sections proceeded from draft to approval with minor revision — which is the ordinary case in this kind of collaboration, not evidence of less rigour.*

---

## Three Rounds of Adversarial Review

After the series was drafted, I ran three independent Claude sessions — separately from the session that wrote the series — with a single instruction: argue against it from Python's perspective. Find every weakness. Be as hostile as the argument deserves.

Each session received no context from the others and no access to the conversation that produced the series. They read the articles cold and reported what they found.

**One limitation belongs here, not in a closing caveat:** all three reviewers are Claude — the same model, the same training data, the same systematic blind spots. If the model misunderstands something about this domain, three rounds of Claude review will not surface it. What adversarial review can find is logical contradictions, factual errors the model recognises as such, and claims stronger than the cited evidence supports. What it cannot find is what the model itself does not know it is wrong about.

**Round one** produced 18 findings. Critical issues included: a primary source cited as load-bearing but described as "not directly accessible at time of writing" (it turned out to be a paper accepted at PLDI 2025, findable with a proper search); a logical contradiction in the Kotlin recommendation; the GIL claim applied to Python 3.13 as though free-threaded mode didn't exist.

**Round two** verified whether the responses to round one were adequate. Six residual issues remained — including one where the fix had been documented in the notes but not actually applied to the file.

**Round three** found three remaining blockers before publication. Its conclusion: *"the series argument is genuinely interesting and the core insight is sound. The review process has been rigorous precisely because the argument is worth making well."*

The core claim held — but the reviews found material errors, not just precision issues. A logical contradiction in the Kotlin reasoning. A stale technical claim about Python 3.13. An unsourced Fortune 500 statistic that was removed when no traceable primary source could be found. These were corrected. The argument that survived is not the same argument that entered. It was sharper for having been challenged, and more honest for having had its errors named.

---

## What the Challenge Found

Some of what the reviews found was correction. A figure described as "attributed to ETH Zurich/UC Berkeley — primary source not directly accessible" turned out to be a properly accessible PLDI 2025 paper. A line — "the verbosity is in the output, the savings are in the cycles" — appeared three times across different articles doing the same work each time. Repetition at that scale is filler, not emphasis.

Some of what the reviews found was strengthening. The Kotlin recommendation became a better argument when the circular reasoning was removed and replaced with evidence. The LLM defaults claim became more defensible when grounded in a specific observation rather than an assertion. The Pydantic characterisation became more honest when we acknowledged that well-engineered modern Python (FastAPI, Pydantic v2, pyright strict) is substantially stronger than the baseline, and that the real remaining distinction is compile-time versus runtime enforcement — not the presence or absence of types.

---

## The Meta-Observation

The most striking thing about this process — and it may be a consistency observation rather than a proof — is that it mirrors the argument.

The series argues that LLM-first development works best when the human writes the specification and the LLM implements it; when the implementation is reviewed and challenged; when errors are caught before they reach production. Design the argument before drafting it. Challenge it before publishing it. Let the challenge produce a stronger version rather than just a defended one.

That is also what happened here. Whether it is surprising that an author applies their own framework consistently is a fair question.

---

## A Note on What This Doesn't Prove

Harvard Business School researchers identified what they call the [Human-AI Oversight Paradox](https://www.hbs.edu/ris/Publication%20Files/25-001_8ebbe0cb-2a19-453c-9014-1e301e8dd2fb.pdf): human oversight can improve task performance while simultaneously reducing the overseer's understanding of what they are overseeing. Better-assisted work, less-informed author. It is a real risk. The [MIT Media Lab found](https://www.media.mit.edu/publications/your-brain-on-chatgpt/) that ChatGPT users showed lower cognitive engagement and worse recall of their own writing compared to unassisted writers. Whether active collaborative drafting — where the human is directing and challenging rather than accepting — produces the same effect is an open question.

More directly: three rounds of adversarial review by an AI system find what an AI system finds. The review process found logical contradictions, unsourced statistics, stale technical claims, and overclaiming language. It did not find that the core argument was wrong. That is the honest characterisation of what three rounds of challenge produced — neither more nor less.

*The review documents, export files, and git history are in the [sparge repository](https://github.com/mdproctor/sparge) under docs/article/. The record is there for anyone who wants to check the work. The process described here is formalised as a reusable framework in the companion piece: [The Editorial Pipeline](/articles/the-editorial-pipeline/).*

*It is also possible that a domain expert would find things three rounds of Claude did not. We welcome that. The series calls for a controlled study that might prove some of its own claims wrong — which is either intellectual honesty or a peculiar form of optimism, depending on whether the study eventually gets done.*

---

## References

- Simon Willison, *"Slop is the new name for unwanted AI-generated content"* (May 2024) — simonwillison.net/2024/May/8/slop/
- Deni Ellis Béchard, *"AI Slop — How Every Media Revolution Breeds Rubbish and Art"*, Scientific American (November 2025) — scientificamerican.com
- *"Merriam-Webster's word of the year for 2025 is AI 'slop'"*, PBS News — pbs.org/newshour
- *"Narrative AI and the Human-AI Oversight Paradox"*, Harvard Business School Working Paper 25-001 (2025) — hbs.edu
- *"Your Brain on ChatGPT"*, MIT Media Lab (June 2025) — media.mit.edu/publications/your-brain-on-chatgpt/
- Mündler, He, Wang, Sen, Song, Vechev — *"Type-Constrained Code Generation with Language Models"*, PLDI 2025 — arxiv.org/abs/2504.09246
