# When the Machine Codes: Technical Companion

**Companion document to the six-part article series**  
**Status:** Draft complete. Not yet published.

*This document contains the technical supporting arguments for the series. It assumes familiarity with the main articles and is written for developers who want the mechanism behind the claims, not just the claims themselves. Each section is cross-referenced from the relevant series part.*

---

## A1 — Refactoring Completeness

*Referenced from Part 1 Section 4, Part 2 Section 2*

When an LLM refactors code — renames a method, changes a record field, restructures a data contract — the compiler in a statically typed language validates that the refactoring is complete. Every call site that was not updated fails to compile. The LLM receives an exhaustive, precise list of what remains to be fixed.

In Python, a renamed function may leave call sites that still resolve through duck typing or dynamic dispatch, appearing correct until runtime reveals the breakage. A function renamed from `get_post_state` to `get_state` that is called in twelve places will silently break the eleven places that were not updated — each passing as valid Python syntax. The failure manifests when those paths are exercised, which may be hours, days, or never in the test suite.

This distinction matters specifically for LLM-generated refactoring because:

1. LLMs frequently introduce naming changes as part of implementation — a record type added mid-session may prompt the LLM to rename a related field across the codebase
2. LLMs cannot verify completeness without running the code; the compiler provides that verification for free in Java
3. Each uncaught call site is a potential silent regression that surfaces in production rather than in the next session's review

The practical effect: Java refactoring by LLMs is structurally complete or it does not compile. Python refactoring by LLMs is complete if all affected call sites happened to be in scope during generation. These are not equivalent guarantees.

---

## A2 — Virtual Threads and Concurrency Simplicity

*Referenced from Part 1 Section 4, Part 4 Section 2*

Java 21's Project Loom virtual threads allow concurrent server code to be written with simple blocking idioms — read a file, call an API, return a result — and the runtime handles concurrent request handling transparently. The LLM does not need to reason about thread pools, callback chains, or backpressure; it generates sequential code and the JVM scales it correctly.

Python's concurrency model for I/O-bound server work requires the `asyncio` model: `async def`, `await`, and `async with` propagating throughout the call graph. An LLM generating a Python REST endpoint that calls a database must mark the handler as `async`, `await` the database call, and propagate `async` through every function in the call chain from handler to database client. A missed `await` produces code that appears to work — the coroutine object is truthy — but silently does nothing.

Python 3.13's free-threaded mode (PEP 703) addresses CPU-bound parallelism by removing the GIL. This is a significant and genuine improvement. However, I/O-bound server code — the dominant pattern in REST API development — still benefits from the `asyncio` model for non-blocking behaviour, and `asyncio` propagation requirements remain. Free-threading and `asyncio` address different problems.

For LLMs generating server code:
- **Virtual thread Java:** generate sequential blocking code; correctness is structural and the runtime handles concurrency
- **`asyncio` Python:** generate async-aware code throughout the call graph; a single missing `await` is a silent failure with no compiler or runtime warning until the code path is exercised

Java 21's virtual threads eliminate an entire class of concurrency errors that Python's `asyncio` model requires active attention to avoid.

---

## A3 — OpenAPI as Machine-Verifiable Specification

*Referenced from Part 2 Section 3*

Typed API frameworks — Quarkus/JAX-RS in Java, FastAPI/Pydantic in Python — both generate OpenAPI specifications from typed endpoint signatures, producing non-divergent documentation where the implementation and the spec are the same artifact. This is not a Java-exclusive capability.

The Java-specific advantage is what happens at the consuming end. When System B consumes System A's API and both are statically typed Java, System B's REST client can be generated from System A's OpenAPI spec and compiled against System A's type declarations. A change to System A's endpoint that adds a required field causes System B's client to fail to compile — before either system is run, before integration tests, before deployment.

**The compilation chain:**
1. System A: annotate endpoint with JAX-RS → OpenAPI spec generated automatically
2. System B: generate type-safe client from System A's spec
3. System A changes: update endpoint annotation → spec updated automatically
4. System B: client fails to compile — exact field and type mismatch reported
5. Fix: update System B's call site, recompile, proceed

In Python/FastAPI: steps 1–3 are equivalent. Step 4 becomes a runtime failure when the systems are exercised together. Step 5 requires finding the failure point through debugging rather than following compiler output.

For LLM sessions working on System B in isolation — without access to System A's running instance — the compiled client is a structural guarantee that their integration code speaks the current contract. Python's equivalent requires either running both systems together or trusting documentation.

---

## A4 — Training Data Distribution: Two Explanations for the Accuracy Gap

*Referenced from Part 1 Section 1*

The "LLMs Love Python" study (2025, arxiv.org/html/2503.17181v1) found that LLMs achieve 11.3 percentage points higher accuracy in Python than Java on standard benchmarks. The paper attributes this to training data distribution. A second explanation is equally plausible and not addressed by the paper.

**Explanation 1 — Training data distribution.** Python is overrepresented in LLM training corpora, particularly through the data science and ML domain. LLMs have seen more Python code, more Python tutorials, more Python Stack Overflow answers than Java equivalents in many domains. The accuracy gap reflects familiarity, not language quality.

**Explanation 2 — Structural simplicity.** A correct Python function requires fewer structural decisions than the equivalent Java: no package declaration, no class wrapper, no access modifiers, no explicit return type, no checked exception declarations. If LLMs have a baseline probability of making an error per structural decision, fewer decisions produces fewer errors independently of training data volume. Python's syntax is genuinely smaller.

**Why both can be true simultaneously.** The two explanations are not mutually exclusive. Python may both dominate training data AND be structurally simpler to generate correctly. Separating the contributions would require a controlled study isolating structural complexity from training data frequency — no such study exists.

**The domain qualification.** The 11.3 percentage point gap is concentrated in scientific and algorithmic benchmark domains where Python's training data dominance is strongest. For web service code, REST API implementation, and business logic — Java has substantial high-quality training data (Spring Boot, Java EE, Jakarta EE) and the gap is smaller. The headline figure should not be read as universal.

**The counter-argument.** The series does not need to resolve which explanation dominates. Even if Python is genuinely easier for LLMs to generate correctly due to structural simplicity, the compile-time correction mechanism in Java — catching errors before execution with precise location information — may produce lower *net* error costs across a complete implementation. Whether the correction advantage outweighs the initial error rate advantage is the controlled study the series calls for.

---

## A5 — The Positive Feedback Loop

*Referenced from Part 4 Section 5*

The choice of programming language by LLMs is not static — it is self-reinforcing in a way that requires deliberate intervention to correct.

**The mechanism.** LLMs trained on a corpus where Python dominates will generate Python code preferentially. That generated code — produced at scale by AI systems across thousands of projects — accumulates in public repositories. Public repositories become training data. The Python prior in the next generation of models strengthens, not because Python has become more suitable, but because it has become more prevalent in the training distribution. The dynamic amplifies whatever language is currently dominant. It does not correct for suitability.

**The scale of the effect.** As AI-assisted development grows, the volume of LLM-generated code in public repositories grows with it. If that code is predominantly Python — because LLMs default to Python — the feedback loop operates faster and with greater force than the organic adoption patterns of human-written code. The error, if it is an error, compounds.

**The inverse loop.** The same mechanism runs in reverse. If LLM vendors deliberately increase the quality and diversity of Java and statically typed language training data for the application development domain — not waiting for organic drift — output quality improves, more high-quality typed code appears in repositories, and future training improves further. TypeScript's rapid adoption and improving LLM generation quality in web development is an early example of this dynamic already operating in the statically typed direction.

**What deliberate action looks like.** It is not "train on more Java code regardless of quality." It is: identify the application development domain specifically (backend services, REST APIs, system integration), curate high-quality examples of Java/Quarkus and other typed framework patterns in that domain, weight them appropriately in training, and evaluate model outputs on application code tasks — not only on algorithmic benchmarks where Python's structural simplicity advantages are largest.

**The window.** Training data decisions made now shape the next generation of models. The transition from Python-default to statically-typed-language-appropriate is easier to make while the proportion of AI-generated code is still relatively small. As that proportion grows, the feedback loop strengthens and the cost of correction increases. The call to vendors in Part 4 is time-sensitive, not open-ended.

---

## References

- *LLMs Love Python: A Study of LLMs' Bias for Programming Languages and Libraries* (2025) — arxiv.org/html/2503.17181v1
- Mündler, He, Wang, Sen, Song, Vechev — *Type-Constrained Code Generation with Language Models* — PLDI 2025 — arxiv.org/abs/2504.09246
- *The Debugging Decay Index: Rethinking Debugging Strategies for Code LLMs* — arxiv.org/html/2506.18403v2
- Project Panama (JEP 454) — stable Java 22 — openjdk.org/jeps/454
- Project Loom virtual threads (JEP 444) — stable Java 21 — openjdk.org/jeps/444
- Python PEP 703 — free-threaded CPython — peps.python.org/pep-0703/
- Kotlin Foundation — structure and governance — kotlinfoundation.org/structure/
- Stack Overflow Developer Survey 2024 — survey.stackoverflow.co/2024/technology
- FastAPI documentation — fastapi.tiangolo.com
- Quarkus REST client and OpenAPI — quarkus.io/guides/rest-client
