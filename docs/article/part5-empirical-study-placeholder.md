# When the Machine Codes: Parallel Design and Spec-Led Development at Scale — An Empirical Study

**Part 5 of 5 — When the Machine Codes series**  
**Status:** Placeholder. Data collection and analysis pending.

---

## Purpose

Part 5 is the second of two empirical cases in this series. Where Part 3 documents a completed migration (Python to Java/Quarkus on the Sparge system), Part 5 examines ongoing parallel development — LLM-first, Java from inception — across a suite of five integrated systems.

Together Parts 3 and 5 test the series argument from two directions:
- Part 3: that migration to Java/Quarkus is viable and reveals genuine advantages
- Part 5: that the design spec-led development model scales to parallel, integrated development at volume

---

## The Systems Under Study

The five systems that will form the empirical basis:

| System | Domain | Notes |
|--------|--------|-------|
| casehub | Case management | |
| claudony | [TBD] | |
| qhorus | [TBD] | |
| ledger | Financial ledger | |
| workitems | Work item tracking | |

All developed concurrently, LLM-first, Java/Quarkus from inception. Integration points to be mapped and documented.

---

## Research Questions

1. **Development velocity:** What volume of feature development has been achieved across the five systems in parallel, measured by commits, features shipped, and lines of code? How does this compare to equivalent human-only development estimates?

2. **Integration coherence:** How many integration failures occurred at the API boundaries between systems? How were they detected (compile time vs. runtime)? What role did static typing play in detection?

3. **Session continuity:** How effectively did LLM sessions resume work on a codebase without prior context? Were there measurable differences in productivity between sessions with and without explicit specification documents?

4. **Specification quality:** What correlation exists between specification precision and implementation correctness on first pass?

5. **The cold-read test:** Can a fresh LLM session, given only the codebase and no conversation history, accurately reconstruct the architectural intent and current state of each system?

---

## Data Sources

- GitHub commit history across all five repositories
- GitHub issue history and closure rates
- API evolution history (breaking changes, additions, deprecations)
- Integration test failure history
- Session log analysis (where available)

---

## Planned Methodology

1. GitHub history analysis: extract commit patterns, feature velocity, integration point changes
2. Map inter-system API contracts and document their evolution over time
3. Identify integration events (failures, breaking changes, coordinated updates)
4. Classify integration events by detection mechanism (compile-time vs. runtime)
5. Qualitative analysis of specification documents and their relationship to implementation correctness
6. Draft empirical findings as structured claims with supporting evidence

---

## Language Consistency Notes for Parts 1–4

Parts 1–4 should carry the following consistent forward references to Part 5:

- **Part 1, Section 4** (parallel development): *"The empirical basis for this claim is examined in Part 5 of this series, which analyses GitHub history and integration evolution across a suite of five related systems."*
- **Part 2, Section 3** (parallel development coherence): *"The companion study in Part 5 examines this across a live multi-system development context."*
- **Part 4, Section 5** (vendor call): *"The empirical basis for the efficiency claims in this call is examined in Part 5 of this series, currently in preparation."*

---

## Status

This placeholder will be replaced with the full draft once data collection and analysis are complete. The article should not be published until Parts 3 and 5 can be presented together as the two-case empirical foundation of the series.
