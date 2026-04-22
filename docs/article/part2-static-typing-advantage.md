# When the Machine Codes: The LLM-First Development Advantage of Static Typing

**Part 2 of 5 — When the Machine Codes series**  
**Status:** Draft complete. Not yet published.

*Part 1 of this series argued that the conventional case for Python as the default language in LLM-first development rests on assumptions that do not transfer from human developers to large language models. This article makes the positive case: the specific properties of statically typed languages — and Java in particular — that make them better suited to a development model where the LLM is the primary implementer. The argument proceeds from generation time through review time and finally to scale.*

*Technical detail is marked where it appears. The argument holds without it.*

---

The conventional wisdom about static typing is that it benefits large teams working on long-lived codebases. The overhead of declaring types, maintaining type annotations, and fixing compiler errors pays off over years of maintenance by multiple developers. For small projects and rapid prototyping, the conventional wisdom continues, dynamic typing is faster — you write less, you iterate more freely, and you deal with type problems when they arise rather than upfront.

This argument is not wrong for the case it describes. It is wrong in assuming that case is the only relevant one. When the primary implementer is a large language model, the properties that make static typing valuable change, and some of the properties that made dynamic typing attractive disappear. The result is a different calculation — one that the conventional wisdom was not designed for and does not accurately reflect.

---

## 1. At Generation Time: The Token Cost Argument

The most immediate objection to Java in LLM-first development is verbosity. A Java class with type declarations, package statements, imports, and explicit generics is longer than the equivalent Python. Longer output means more tokens. More tokens mean higher cost.

This objection has the right structure but the wrong accounting.

Token costs for LLM APIs are not uniform. Output tokens — the text the model generates — cost between three and ten times more than input tokens, because generation requires more computational resources than reading. A longer Java class does cost more to generate than a shorter Python equivalent. But that is one side of the ledger. The other side is the debugging cycle.

When an LLM generates code that contains an error, what follows is a cycle: the error is discovered, the error is fed back to the LLM as input, the LLM reasons about it, the LLM generates a correction. Each cycle consumes input tokens (the error and context), output tokens (the correction), and — critically — reasoning capacity. Research on LLM debugging behaviour documents this as the Debugging Decay Index: models lose between 60 and 80 percent of their debugging effectiveness within two to three attempts. The first cycle is the most effective. Each subsequent cycle is progressively worse. This means the cost of a debug cycle is not simply its token count — it is its token count multiplied by the degraded quality of the reasoning that produced it.

Into this calculation, introduce the finding that 94 percent of LLM-generated compilation errors are type-related. In Python, these errors surface at runtime — requiring a debug cycle. In Java, they surface at compile time, before execution, with precise location information and a clear description of what was expected versus what was provided. The LLM can act on a compile error immediately, often within the same response, without triggering a full debug cycle.

The arithmetic inverts. Java's verbosity is paid once, at generation time. Python's type errors are paid repeatedly, at debugging time, with degrading returns. If Java eliminates even one substantive debug cycle per implementation unit — and the evidence suggests it eliminates several — the net token cost of a correct, working Java implementation is lower than the equivalent Python. The verbosity is in the output. The savings are in the cycles.

**The enterprise implication.** At the scale of enterprise software development — many developers, many projects, many LLM sessions per day — this differential becomes material. Enterprise AI coding costs are substantial: published figures show heavy Claude Code usage running to thousands of dollars per month per developer at high session volumes, with output tokens costing three to ten times input tokens. A consistent reduction in debug cycles across a large engineering organisation is not a marginal efficiency gain. It is a structural cost reduction driven by a language choice. The precise magnitude requires controlled study — no such study exists yet at the time of writing — but the direction of the effect is not in doubt. *(See Appendix 4 for the error message precision argument that compounds this further.)*

---

## 2. At Review Time: Static Read-Through Reliability

Code review in LLM-first development has a property that distinguishes it from human code review: every review session begins cold. A human reviewer who has worked on a codebase for months carries an internal model of what the code is supposed to do, what conventions are in use, what the data looks like at each point. An LLM reviewer begins each session from the code alone, with no memory of previous sessions, no accumulated familiarity, and no ability to ask a colleague what was intended. The quality of the review is bounded by what can be reconstructed from a single read of the codebase.

This is where the gap between statically and dynamically typed code becomes concrete.

When a reviewer reads `List<MdIssue>`, they know — with compiler-verified certainty — that the list contains instances of `MdIssue`, that each `MdIssue` has the fields declared in its record definition, and that nothing in the codebase has been permitted to violate that structure without producing a compilation error. The reviewer does not need to search for where `MdIssue` is constructed, or check whether it might sometimes be populated differently, or caveat their findings against the possibility that the type constraint is violated in some edge case. The type system has already answered those questions.

When a reviewer reads a Python function that accepts a list of dictionaries, none of that certainty is available. The reviewer must infer the shape of each dictionary from how it is used — which keys are accessed, what operations are applied to the values, whether the same name is used for structurally different objects elsewhere in the codebase. This inference may be accurate. It may not be. It is always inference, and the review findings must be qualified accordingly.

**What this means for review confidence.** An LLM reviewing a statically typed Java codebase can make definite claims: *this method cannot receive a null where it expects a `String`; this list cannot contain an element of a different type; this record cannot be partially constructed.* An LLM reviewing equivalent Python code must make probabilistic claims: *this dictionary appears to always contain these keys; this function appears to be called with this type of argument; this pattern appears to be consistent across the codebase.* The word *appears* carries all the uncertainty. In a review whose purpose is to find what is wrong, qualified confidence is weaker than verified confidence.

**A concrete example from this project.** During the development of the Stage 4 refinement pipeline described in Part 3 of this series, a separate LLM session was used to perform a static read-through of the implementation — verifying that the code matched the specification without running either. The review identified structural issues that had been missed during implementation. This was possible because the data contracts — `RefinementRule`, `FenceBlock`, `ReplayResult` — were Java records with compiler-enforced fields. The reviewer could reason about what each method received and returned, what the replay engine guaranteed, and where the implementation diverged from the specification, all from the code alone. The same exercise on equivalent Python code would have required either running the code or accepting inference as a substitute for verification.

**The type hint caveat, stated fairly.** Python's optional type annotation system — enforced by tools such as `mypy` and `pyright` — narrows this gap for codebases where annotations are present and maintained. A fully annotated Python codebase with strict type checking applied consistently provides substantially more structural information than unannotated Python. The gap with Java is real but smaller. The honest qualification is that full annotation is not the norm. It requires discipline to establish and maintain; it is not enforced by the language; and it is unevenly applied in practice, particularly across the boundaries of dependency libraries where the LLM has no control over annotation quality. Java's type information is always present, always accurate, and always verified. Python's type hints are sometimes present, sometimes accurate, and never verified by the runtime. *(See Appendix 1 for the related refactoring completeness argument.)*

---

## 3. At Scale: Parallel Development and Integration Coherence

The arguments in Sections 1 and 2 concern a single project developed by a single LLM working session at a time. They show that static typing reduces debugging cost at generation and improves reliability at review. Both arguments are real. Neither is the strongest one.

The strongest argument for static typing in LLM-first development operates at scale — across multiple projects developing concurrently, sharing integration contracts, evolving in parallel. At this level, static typing is not merely a quality improvement. It is an enabling condition for coherent development that dynamic typing cannot replicate structurally.

**The integration contract problem.** When two systems communicate — System A exposing an API that System B consumes — they share a contract. That contract specifies what System A will provide, in what form, with what guarantees. System B's correctness depends on that contract being honoured. In traditional software development, enforcing this contract at scale is an unsolved problem. Documentation drifts. APIs evolve. Consumers are not always notified. Integration failures surface at runtime, in production, far from the change that caused them.

In a statically typed ecosystem, the contract is expressed as types. When Quarkus generates a type-safe REST client for System B to call System A, the client is derived from the same type declarations that define System A's API surface. A change to System A that alters its API types — adding a required field, changing a return type, removing a parameter — will cause System B's client code to fail to compile. The failure surfaces immediately, in the build, before either system is run. The developer — or LLM — working on System B learns about the breaking change at the earliest possible moment, with the most precise possible information about what changed and where.

In a dynamically typed ecosystem, the same contract is a convention. It is expressed in documentation, in comments, in the shared understanding of developers who have worked on both systems. When System A evolves, that convention may or may not be updated. System B may or may not be notified. The failure, if it occurs, surfaces at runtime — during integration testing if you are disciplined, in production if you are not. The distance between the cause and the observable effect is measured in time and in the accumulated work built on the broken assumption.

**The integration debt concept.** In high-volume parallel development, this asymmetry compounds. Consider five systems developing concurrently, each making multiple changes per session, each depending on APIs exposed by the others. In a dynamically typed ecosystem, each integration point is a convention that may drift. At low volume — one change per system per week, integration testing after every change — the drift is manageable. At high volume — many changes per system per day, integration testing only when systems are run together — the gap between assumed contract state and actual contract state widens faster than it can be closed. By the time an integration failure surfaces, multiple layers of additional work have been built on the broken assumption. The failure is expensive to diagnose and expensive to correct.

Static typing prevents this at the source. The convention becomes a compiler-enforced type. The drift is impossible — not improbable, not discouraged, but structurally prevented. A system that cannot compile cannot be committed. A contract that has changed announces itself immediately to every dependent. The gap cannot widen because the tools that would let it widen are not available.

**This is not hypothetical.** The five systems referenced in this series — casehub, claudony, qhorus, ledger, work — are under concurrent development in the model described here: design spec-led, LLM-implemented, Java from inception. These systems are not independent. They depend on each other through shared APIs that have been growing and changing throughout development — new endpoints added, existing contracts extended, data models revised as requirements evolved. LLM sessions working on different systems in isolation — each beginning without memory of previous sessions, each unaware of what other sessions were doing simultaneously on sibling systems — had to navigate those evolving contracts and adapt their implementations accordingly. The type system was the mechanism that made this tractable: each session could read the current API types, know with certainty what was expected, and produce code that either compiled against the contract or failed with a precise description of the mismatch. *Part 5 of this series examines the git history of these five systems — API evolution, integration changes, and how each was propagated — as the empirical record of this claim in practice.*

**What dynamic typing requires instead.** It is worth being explicit about the alternative. Dynamic typing does not make coherent parallel development impossible — it makes it procedural rather than structural. The coherence must be maintained by discipline: comprehensive documentation, regular integration runs, explicit coordination between developers or LLM sessions working on different systems, and thorough testing at every boundary. These practices work. They are also expensive, prone to lapses, and dependent on the consistency of the team or system applying them. Static typing makes coherence a property of the code rather than a property of the process. The distinction matters most when volume is high, sessions are many, and the people or systems doing the work cannot coordinate in real time.

**The OpenAPI connection.** In a Quarkus-based system, the integration contract can be made explicit in a third form that compounds the advantage further. Quarkus generates an OpenAPI specification directly from JAX-RS annotations — the implementation and the specification are the same artifact, expressed in different representations. System B can generate a type-safe client from System A's OpenAPI spec. The spec cannot drift from the implementation because the spec is derived from the implementation at build time. For LLM sessions working on System B, the OpenAPI document is a machine-readable, always-current description of what System A provides. It is the specification that the LLM can read cold and trust completely. *(See Appendix 3.)*

---

## 4. The Continuity Mechanism

The three arguments so far — reduced debugging cost, more reliable review, and parallel development coherence — all have analogues in human software development. A human team also benefits from catching errors early, reviewing code accurately, and maintaining integration contracts. The advantages are real for humans too, which is why large teams have long preferred statically typed languages for complex systems. What makes these arguments specific to LLM-first development is the degree to which they apply — the compounding of debugging decay with type errors, the cold-session review problem, the volume and parallelism of concurrent LLM work — rather than the direction.

The fourth argument has no analogue in human development at all. It is specific to how large language models work, and it is the one that does not appear in any conventional comparison between Java and Python.

**The session boundary.** A human developer working on a codebase across multiple sessions carries their understanding with them. They know what they built last week. They remember the design decisions that were made, the constraints that shaped them, the parts of the codebase that are fragile or incomplete. When they return to a project after a break, they resume — imperfectly, but substantially. Their prior context reduces the time needed to return to productive work.

An LLM has no such continuity. Every session begins from the code. There is no memory of the previous session, no accumulated understanding of the codebase's history, no recollection of what was decided and why. The LLM working on a system today has exactly the same starting point as a different LLM working on the same system for the first time: the files as they currently exist, whatever documentation is present, and nothing else.

This means the code is not just an implementation artefact. It is the complete and sole record of everything the next session needs to know. The quality of that record — how accurately it communicates architectural intent, data contracts, system boundaries, and design decisions — determines the quality of the session that follows.

**What static typing contributes to continuity.** A statically typed codebase encodes structural information in a form that is verified, explicit, and immediately readable. A record type `RefinementRule(String check, int fenceIndex, String fingerprint, String contentSample, Map<String, String> fix)` tells the next session, with certainty, what a refinement rule is, what it contains, and what types its fields carry. A sealed class hierarchy tells the next session what states are possible and that the list is exhaustive. A method signature `replay(String md, List<RefinementRule> rules)` tells the next session what the replay engine accepts and what it returns. None of this requires reading the implementation. All of it is available from the declarations alone.

A dynamically typed codebase communicates the same information less reliably. A dictionary named `rule` might contain the same fields — or it might not, in some paths. A function named `replay` might accept a list of dicts — or it might accept a single dict, or something else, depending on the call site. The next session must read more code, make more inferences, and carry more uncertainty before it can reason accurately about what the system does. That uncertainty is not eliminated by reading further — it is reduced, incrementally, with each additional piece of code that confirms or challenges the inference. In a large codebase, the inference is never fully resolved.

**The design implication.** If the code is the sole continuity mechanism for LLM-first development, then the design of the code is also the design of the continuity. Every structural decision — whether to use a record type or a dict, a sealed class or a string constant, an explicit interface or an implicit convention — is also a decision about how much information the next session will have available when it begins. Well-named record types, explicit data contracts, and compiler-enforced interfaces are not merely good software engineering practice. They are session continuity infrastructure. Designing for LLM-first development means designing code that communicates its intent to a reader with no prior context, because that is exactly the reader the next session will be.

This reframes the verbosity argument one final time. The additional declarations in Java — the type annotations, the record definitions, the explicit interfaces — are not overhead. They are the mechanism by which architectural intent survives the session boundary. The Python dict that saves five lines of declaration also withholds five lines of verified structural information from the next session. That information must either be reconstructed by inference, carried in separate documentation that may be stale, or simply not known. In LLM-first development, none of those alternatives is as reliable as having the information in the code.

---

## Closing

The four arguments developed here operate at different levels but share a common structure. Each identifies a property of static typing that is genuinely more valuable in LLM-first development than in human development — not merely valuable in general, but specifically and measurably more valuable when the implementer generates text rather than types it, begins each session without memory, and may be working simultaneously on multiple integrated systems without real-time coordination.

Taken individually, each argument is modest: fewer debug cycles, more reliable reviews, better integration coherence, improved session continuity. Taken together, they describe a compounding effect. The code that is cheaper to generate correctly is also easier to review accurately, which is also easier to navigate across sessions, which is also easier to integrate at scale. The properties reinforce each other. A codebase that earns the first advantage tends to earn the others.

Part 1 of this series argued that the case for Python as default had not been examined. This article has examined what replaces it. Part 3 documents what that examination looks like in practice — a completed migration, a working system, and the evidence of what the port revealed.

---

## References

- *The Debugging Decay Index: Rethinking Debugging Strategies for Code LLMs* — arxiv.org/html/2506.18403v2
- *94% of LLM-generated compilation errors are type-check failures* — cited across multiple sources; original attributed to ETH Zurich/UC Berkeley (primary source not directly accessible at time of writing)
- *LLM Token Optimization: Cut Costs & Latency in 2026* — redis.io/blog/llm-token-optimization-speed-up-apps/
- *LLM Cost Optimization: 5 Levers to Cut API Spend 70-85%* — morphllm.com/llm-cost-optimization
- Project Panama (JEP 454) — stable Java 22 — openjdk.org/jeps/454
- Quarkus REST client and OpenAPI documentation — quarkus.io/guides/rest-client

*For appendix entries referenced in this article (Appendices 1, 3, 4), see the appendix in Part 1 of this series.*
