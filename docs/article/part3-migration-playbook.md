# When the Machine Codes: From Python to Quarkus — A Migration Playbook

**Part 3 of 5 — When the Machine Codes series**  
**Status:** Draft complete. Not yet published.

*This article is the first of two case-based examinations in this series. Part 3 is a case study: one project, one development context, one developer-LLM pair. It is a data point, not a controlled study. Part 5 is a systematic empirical examination: GitHub history across five integrated systems, quantified API evolution, and measured integration outcomes. Together they test the argument from two directions — that migration is viable, and that the model scales — with appropriately different levels of evidential weight.*

*Parts 1 and 2 of this series made the theoretical case. This article is concerned with what actually happened.*

---

The Sparge blog migration tool was built in Python. It ran. It did what it was supposed to do — ingesting HTML posts, enriching them, converting them to Markdown, tracking state. The Python implementation was tested, documented, and in production use. It was not broken.

Then a requirement emerged that Python could not meet. The Sparge server needed to ship inside an Electron desktop application — a self-contained package that a user could install without configuring a development environment. Electron can bundle a server; what it cannot do practically is bundle a Python runtime. The Python interpreter, its standard library, and the packages Sparge depended on weighed approximately 150 megabytes. The equivalent Quarkus uber-jar — a single Java Archive containing the complete server — weighed 19 megabytes. The decision was made on those numbers, not on a language preference.

This is the right way to make a migration decision. Not because Java is philosophically superior to Python, but because the deployment constraint was specific, the measurement was concrete, and the right tool for the job changed when the job changed. The arguments in Parts 1 and 2 of this series — about LLM-first development, static typing, token costs, and session continuity — are arguments for building new systems in Java from the start. The argument for this migration was simpler: the system needed to fit in a box, and it did not fit.

What the migration revealed about Java's properties — the compiler catching errors, the type system making contracts explicit, the annotation model making patterns consistent — is the evidence that grounds the theoretical arguments. Those arguments were not the reason for the migration. They are what the migration found.

---

## 1. Why the Migration Happened

The deployment constraint was not subtle. An Electron desktop application is distributed as a packaged bundle — a `.dmg` on macOS, an installer on Windows. Everything the application needs to run must be inside that bundle. There is no assumption of a pre-installed runtime environment.

Python requires a Python interpreter. Distributing a Python server inside an Electron application therefore requires distributing a Python interpreter alongside it — and not just the interpreter, but the standard library, the site-packages directory containing every dependency, and the platform-specific binary extensions. By the time this is assembled for each target platform (macOS ARM, macOS Intel, Windows, Linux), the addition to the bundle is measured in hundreds of megabytes. For a tool whose primary job is text processing, this is disproportionate.

The Quarkus path produces a different artifact entirely. The `mvn package` command assembles an uber-jar — a single file containing the compiled Java bytecode for the application and all its dependencies, runnable by any compatible JVM. In the Sparge case this file was 19 megabytes. The JVM itself is typically already present on developer machines and can be bundled for end users at a fraction of the Python runtime's cost. The distribution problem was solved by the architecture of the target platform, not by optimisation.

The migration was therefore not a reconsideration of Python as a language. It was a response to a constraint that Python could not satisfy and Java could. That distinction matters for how the migration is understood: it was not a correction of a mistake but an adaptation to a changed requirement. The Python implementation was correct. The requirement changed. The implementation had to follow.

---

## 2. The Design Spec-Led Development Model as Enabling Framework

A migration is traditionally one of the most expensive activities in software development. The conventional path — read the old code, understand it, rewrite it in the new language — accumulates two sources of risk: incomplete understanding of the original, and the gap between the new implementation's behaviour and the old one's. The larger the system, the more of both.

The migration described here followed a different path, and the difference is what made it tractable.

Before any Java was written, specifications were produced for each component to be ported. These were not technical documents describing the Python implementation — they were behavioural specifications describing what each component was supposed to do: what inputs it accepted, what outputs it produced, what edge cases it handled, what tests verified its correctness. The specification described the behaviour, not the code.

This distinction matters because a specification is language-agnostic. The document describing what Sparge's ingest endpoint should do does not change when the language of the implementation changes. The human architect produced specifications from the existing Python behaviour; the LLM implemented those specifications in Java. The migration was not a rewrite — it was a re-implementation from specification. These are different activities with different risk profiles.

Re-implementation from specification carries a structural advantage: the target language's type system can verify that the implementation matches the specification before it is run. When a specification says "the endpoint accepts a slug and returns the post state as a JSON object," the Java implementation expresses that contract in the method signature, in the return type, in the annotations on the endpoint. The compiler verifies that the implementation is consistent with those declarations. The tests verify that the behaviour is correct. The specification, the types, and the tests form three independent layers of verification — any one of which catching a discrepancy prevents it from reaching production.

The LLM's role in this process was implementation, not comprehension. It did not need to understand the full history of the Python codebase, the decisions that had accumulated over its development, or the technical debt that had collected in corners. It needed to implement a precise specification correctly. Given a precise specification and a type system that enforced its structure, this was a task the LLM could perform reliably, repeatedly, and verifiably across each of the six phases the migration required.

---

## 3. The JEP Bridge Strategy

The most significant practical challenge of a language migration is continuity: the system must remain functional throughout. A migration that requires taking the system offline for the duration is not viable for a tool in active use. The approach taken was incremental: port one component at a time, verify it works, retire the old implementation, repeat.

What makes incremental migration possible is a bridge — a mechanism that allows the new language to call functions in the old language during the transition period. For Java calling Python, this mechanism is JEP: Java Embedded Python. JEP allows a Java application to embed a Python interpreter and call Python functions directly, passing data between the two languages across the boundary.

The bridge served a specific purpose: at any point during the migration, exactly those components that had not yet been ported were still served by the Python implementation, called through JEP. The Java components and the Python components operated in the same process. From outside the system, there was no visible transition — the API behaved consistently throughout.

*[Technical detail]* JEP carries its own costs: the embedded Python interpreter adds startup overhead, the bridge requires careful management of the boundary between Java and Python object models, and the environment variables required to locate the Python runtime (`PYTHONHOME`, `DYLD_LIBRARY_PATH`) complicate deployment. These are accepted costs for a migration tool — costs that were always intended to be temporary, and that disappeared entirely when the bridge was removed. A JEP bridge is not an architecture. It is scaffolding, and scaffolding is removed when the building is complete.

The migration proceeded in six phases. Phase 4 ported the enrichment pipeline. Phase 5 ported the remaining endpoints. Phase 6 eliminated the final JEP calls entirely — at which point the Python runtime, the JEP dependency, the environment variables, and all the scaffolding were removed from the project. The exit criterion was zero bridge calls. That criterion was met.

The bridge strategy may be applicable to other language pairs for which a comparable bridge exists. For teams not ready to embed Python in the JVM, a process-level bridge — the Java server calling Python scripts as subprocesses — achieves the same incremental migration property at lower technical complexity, at the cost of higher communication overhead. The pattern is identical: bridge, port endpoint by endpoint, retire bridge. The mechanism differs; the approach does not.

---

## 4. What the Port Revealed

Migration is evidence. What a codebase reveals when ported from one language to another is not always what was expected.

**The compiler as reviewer.** Three errors were caught by the Java compiler during implementation that would have been silent in the Python version. The first was a constructor argument order error: a method was called with its arguments transposed — the check name where the level was expected, and the level where the check name was expected. In Python, both arguments were strings; the error would have been invisible until the output was examined. In Java, the record type declared the expected order, and the compiler rejected the transposition immediately. The second was a multi-fence aggregation: a method that should have returned one issue per untagged code fence was returning a single aggregate issue listing all untagged fences as a comma-separated string. The downstream code expected individual issues; the mismatch would have been a silent functional error. The third was a dead parameter: a function accepted an argument it never used, creating a false impression of its behaviour. The type system made the discrepancy between the declared interface and the actual implementation visible.

None of these errors were caught by the test suite that existed at the time. All three were caught by reading the type declarations and compiler output. They are concrete instances of the static analysis advantage described in Part 2.

**The type system as modelling tool.** The Python implementation had represented data primarily as dictionaries — flexible, convenient, and structurally implicit. The Java implementation was required to be explicit. Records were defined for `MdIssue`, `FenceBlock`, `RefinementRule`, `ReplayResult`. Each definition forced a decision: what exactly is this thing, what fields does it have, what types do those fields carry? Several of these decisions surfaced ambiguities in the specification — cases where the original Python code had been flexible about the shape of a data structure in ways that the specification had not anticipated. Making the decision explicit in a record type resolved the ambiguity in the specification as well.

**Where the pattern model paid off.** The Quarkus JAX-RS annotation model made endpoint implementation highly consistent. Every endpoint followed the same structural pattern: inject dependencies via CDI, read the active project configuration, resolve the relevant file paths, do the work, return a Response with appropriate headers. Once the first few endpoints were ported and reviewed, subsequent endpoints could be implemented by the LLM following the established pattern with minimal instruction. Review was fast because the pattern was familiar. Errors were easy to spot because deviations from the pattern were visible.

**Where Python was genuinely easier.** One component in the Stage 4 refinement pipeline — `refine_replay.py`, the fuzzy fence-matching engine — was implemented in Python first and later ported to Java. The Python implementation used `difflib.SequenceMatcher` from the standard library, which provided sequence similarity comparison in four lines of code. The Java equivalent required a manual implementation of normalised character similarity. The Python standard library's breadth was felt here in a way that was concrete and measurable. The Java implementation was correct — it passed all tests — but it required more code to achieve the same result. This is the honest accounting: Python won that component.

**The honest reckoning.** The migration took significant time and effort. Six phases across multiple sessions, with documentation and test suite maintenance required throughout. The JEP bridge introduced complexity that had to be managed carefully — wrong environment variables, platform-specific library paths, startup overhead. The test suite was not optional: without it, behavioural parity between the Python and Java implementations could not have been verified. Teams considering a comparable migration should not expect it to be quick or simple. They should expect it to be tractable, and verifiable, and to reveal things about their system that the original implementation had left implicit.

---

## 5. A Candidate Playbook

The migration described here followed a sequence derived from one project in a specific context. The steps are offered as structured guidance, not a validated methodology. The approach is readily repeatable — others can try the same sequence in their own migrations and observe whether it holds. That replication is what would turn this from a single data point into an established pattern.

**1. Establish the specification before writing any target-language code.**
Document what the existing system does — its endpoints, its data contracts, its behaviour at boundaries, its error handling. This is the specification the new implementation will be built against. If the specification reveals that the existing system's behaviour is ambiguous or underdocumented, resolve that ambiguity before starting the port. Ambiguity in the specification becomes ambiguity in the implementation, and ambiguity in the implementation is a defect waiting to surface.

**2. Choose the bridge mechanism and understand its costs.**
A bridge allows the new language to call the old language during the transition. JEP embeds Python in the JVM — high integration, higher complexity. A subprocess bridge calls Python as a separate process — lower integration, lower complexity, higher communication overhead. Choose based on the system's requirements. Either way, the bridge is temporary scaffolding. Plan to remove it.

**3. Port the smallest endpoint first.**
Begin with the component that has the fewest dependencies, the clearest specification, and the most straightforward implementation. Port it, test it against the specification, remove the bridge call, confirm the system still works end-to-end. This first port is where the pattern is established — the endpoint structure, the error handling conventions, the test approach. Get it right before it becomes the template for everything that follows.

**4. Maintain test parity throughout.**
For every component ported, the new implementation's test coverage should equal or exceed the original's. Do not accept "the system appears to work" as a substitute for tests. The test suite is the evidence that the implementation matches the specification in all cases, not just the cases that happened to be exercised during the session. At the completion of the migration, the test suite should be the primary evidence of behavioural parity.

**5. Use the type system as a second layer of specification verification.**
When the data contracts in the specification become record types and method signatures, the compiler verifies that the implementation is consistent with them. Treat compilation errors not merely as code errors but as specification feedback — the type system is telling you something about the contract that the implementation has not satisfied. Fix the implementation, or revise the specification if the type system has revealed an error in the specification itself.

**6. Remove the bridge completely before declaring the migration done.**
A system that retains bridge calls is not a migrated system — it is a partially ported system with ongoing maintenance overhead. The presence of the bridge means the original language's runtime must still be shipped, managed, and maintained. The exit criterion is unambiguous: zero bridge calls. Anything short of that is in-progress, not complete.

**7. Update documentation, deployment artifacts, and tooling immediately.**
Documentation drift is a real cost. Stale references to the old language's server setup, incorrect test counts, outdated configuration instructions — these accumulate quickly and mislead future sessions. Update them as each phase completes, not at the end of the migration. Future LLM sessions will read the documentation as though it is current. If it is not, they will build on incorrect foundations.

---

## 6. What Remains Python

The Sparge system retains Python in two places, and this is intentional.

`server.py` remains — the Python browser-mode server, available for development use via `python3 server.py`. This serves a different context from the Electron application: direct browser access for development and testing, without the Electron packaging overhead. The deployment constraint that drove the migration does not apply here. Python is the right tool for this use case, and it remains.

`scripts/` remains — the core Python logic for ingest, scan, enrich, state management, and the refinement replay engine. These scripts represent a large body of working, tested code. The Electron application's Java server has native Java implementations of the endpoints that the original Python scripts served, but the scripts themselves were not ported — because the scripts are not what the Electron application runs. They are a parallel implementation for browser mode, still correct and still maintained.

This is not a compromise or an incomplete migration. It is the correct outcome of a decision made on concrete grounds. The requirement was to make the Electron application ship without a Python runtime. That requirement is met. The Python code that remains serves a different deployment context with different requirements, and it remains because removing it would not serve those requirements better.

Migration should be driven by requirements, not by a principle of language purity. The Sparge migration was driven by a deployment constraint. When that constraint was resolved, the migration was complete — regardless of what remained in Python outside its scope.

---

*Technical readers: the appendix in Part 1 of this series contains additional arguments relevant to the migration, including refactoring completeness (Appendix A1) and error message precision (Appendix A4).*

---

## References

- Sparge project repository — github.com/mdproctor/sparge
- Project Panama (JEP 454) — stable Java 22 — openjdk.org/jeps/454
- JEP (Java Embedded Python) — github.com/ninia/jep
- Quarkus documentation — quarkus.io
- *LLMs Love Python: A Study of LLMs' Bias for Programming Languages and Libraries* (2025) — arxiv.org/html/2503.17181v1
