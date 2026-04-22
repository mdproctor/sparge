# When the Machine Codes: From Python to Quarkus — A Migration Playbook

**Part 3 of 5 — When the Machine Codes series**  
**Status:** Outline complete. Draft pending.

---

## Framing

Part 3 is the first of two empirical cases in this series. It concerns a completed migration — an existing Python system ported to Java/Quarkus — undertaken for concrete deployment reasons, using a specific incremental strategy. Part 5 is the second empirical case: ongoing parallel development, Java from inception, across a suite of integrated systems.

The opening of Part 3 should make this two-case structure explicit:

> *This article documents the first of two empirical cases examined in this series. Part 3 concerns a completed migration — from Python to Java — undertaken on an existing system. Part 5 concerns ongoing parallel development — LLM-first, Java from inception — across a suite of integrated systems. Together they test the argument from two directions: that migration is viable, and that the model scales.*

---

## Outline

### Section 1 — Why the Migration Happened

**Not a language argument — a deployment argument.**

The decision to port Sparge's Python server to Java/Quarkus was not made because Python was the wrong language in the abstract. It was made because Electron desktop embedding required a bundleable server artifact, and the Python runtime — approximately 150 megabytes — was impractical to ship alongside the application. The Quarkus uber-jar weighed 19 megabytes.

Key points:
- State the deployment constraint clearly and first. The language argument follows from it, not the other way around.
- The JEP bridge strategy was chosen *because* the Python choice was not inherently wrong — the existing Python implementation was correct and tested. The goal was to port it without disrupting the running system.
- This framing is important: the migration validates that Java/Quarkus is better for this context, not that Python was a mistake.

---

### Section 2 — The Design Spec-Led Development Model as Enabling Framework

**Why the migration was tractable.**

Before documenting the migration itself, establish the model that made it possible. The human architect authored specifications for each component to be ported. The LLM implemented against those specifications. The human reviewed. The cycle was specification → implementation → review, not rewrite-and-hope.

Key points:
- The specification is language-agnostic. The same design document that described what the Python code did became the specification for what the Java code should do.
- This means migration is not a rewrite in the traditional sense — it is re-implementation from a specification, which is a fundamentally different and lower-risk activity.
- The type system of the target language (Java) enforced that the implementation matched the specification structurally, providing a second validation layer beyond the tests.

---

### Section 3 — The JEP Bridge Strategy

**How to migrate incrementally without breaking the running system.**

The JEP (Java Embedded Python) bridge allowed Java code to call Python functions during the transition period. Each endpoint was ported individually: the Java implementation was written and tested, the bridge call was removed, and the Python code behind it was retired. At any point during the migration, the system was fully functional.

Key points:
- The bridge is a *migration tool*, not an architecture. It was always intended to be temporary and was designed to be removed.
- The phased approach: Phase 4 (enrichment), Phase 5 (remaining endpoints), Phase 6 (complete JEP elimination). Each phase had a clear scope, a clear acceptance criterion (N bridge calls reduced to zero), and left the system in a working state.
- The bridge strategy is generalisable: any language pair with a comparable bridge mechanism can use this approach. The pattern is: bridge → port endpoint by endpoint → retire bridge.
- Test counts as evidence: the Java test suite grew from 180 to 346 tests across the migration, providing confidence that behavioural parity was maintained.

---

### Section 4 — What the Port Revealed

**Evidence from the migration about each language's properties in practice.**

Key findings to document:
- Java's compiler caught three errors during implementation that would have been silent in Python (wrong argument order, multi-fence aggregation, dead parameter). These are concrete examples of the static typing advantage in action.
- The type system forced explicit data modelling that the Python version had left implicit. Records for `MdIssue`, `FenceBlock`, `RefinementRule` made the data contracts clear in a way that Python dicts had not.
- The Quarkus annotation model (JAX-RS, CDI) made endpoint implementation highly pattern-consistent — the LLM followed the same structural pattern for each endpoint, which made review fast and reliable.
- Where Python was genuinely easier: the initial `refine_replay.py` implementation (fuzzy fence matching with `difflib.SequenceMatcher`) was written more quickly in Python. This was the one component where Python's standard library advantage was felt.

**Honest acknowledgements:**
- The migration took significant time and effort across multiple sessions.
- The JEP bridge introduced its own complexity during the transition period.
- The test suite was essential — without it, behavioural parity could not have been verified.

---

### Section 5 — A Reusable Playbook

**Practical guidance for teams considering the same transition.**

Structure as a numbered sequence:

1. **Establish the specification first.** Before writing any Java, document what the Python system does — its endpoints, its data contracts, its behaviour. This is the specification the Java implementation will be built against.

2. **Choose the bridge mechanism.** For Python-to-Java migrations, JEP is one option. Process-level bridges (the Java server calling Python scripts via subprocess) are another, lower-risk option for teams not ready to embed Python in the JVM. Start with the simpler bridge.

3. **Port endpoint by endpoint, smallest first.** Begin with the simplest endpoint — the one with the fewest dependencies and the clearest specification. Port it, test it, remove the bridge call. Build confidence before moving to complex endpoints.

4. **Maintain test parity throughout.** For every endpoint ported, the Java test coverage should equal or exceed the Python coverage. Do not accept "the system works" as a substitute for tests — the tests are the evidence that it works in all cases, not just the cases you tested manually.

5. **Use the type system to validate the specification.** When the data contracts in the specification become Java records and interfaces, the compiler will tell you immediately if the implementation violates them. Treat compiler errors as specification feedback, not just code errors.

6. **Remove the bridge completely before declaring success.** A migration that retains the bridge is not a migration — it is a partial port with ongoing maintenance overhead. The exit criterion is zero bridge calls.

7. **Update documentation and deployment artifacts immediately.** The documentation drift that accumulated in the Python phase — stale references to Python server setup, incorrect test counts, outdated key directory listings — was caught and corrected as part of the migration. Do not defer this.

---

### Section 6 — What Remains Python

**Honest accounting of what was not ported.**

The Sparge system retains Python in two places:
- `server.py` — the Python browser-mode server, which remains available for development use (`python3 server.py`)
- `scripts/` — the core Python logic for ingest, scan, enrich, state management

The scripts were not ported because they were not required to be. The Electron application uses the Java server exclusively. The Python browser mode serves a different use case (development without Electron). The scripts represent a body of working, tested code that would require significant effort to port for no production benefit.

This is the correct outcome. Migration should be driven by concrete requirements, not by a principle of language purity. The Python code that remains does so because it is in a different context with different requirements.

---

## Notes for Drafting

- The JEP bridge explanation needs to be accessible to non-technical readers. Avoid JVM-specific terminology where possible; describe what it does (allows Java code to call Python functions during the transition) rather than how it works internally.
- The playbook (Section 5) should be the most practically useful section for readers who are considering a similar migration. Make it specific and actionable.
- Resist the temptation to make the migration sound easier than it was. The honest account — it took significant time, the bridge introduced complexity, tests were essential — is more credible and more useful than a triumphant narrative.
- Cross-reference Part 1 Section 5 (Where Python Remains the Right Choice) when discussing what was not ported. The retention of Python browser mode is consistent with that section's argument.
