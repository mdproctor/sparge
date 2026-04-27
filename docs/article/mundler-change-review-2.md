# Adversarial Review Round 2: Mündler et al. Verification
## Parts 1 and 2 — *When the Machine Codes*

**Reviewer:** Adversarial Claude session (independent)
**Date:** 2026-04-26
**Scope:** Verify five Round 1 findings; brief secondary pass.

---

**Finding 1 — Inference gap**
Status: APPLIED
Evidence: Part 2 now reads: "type-constrained decoding is a research technique requiring specialised inference infrastructure. It does not activate automatically when a developer writes in a statically typed language." The practical bridge to standard deployment follows immediately: "The practical benefit in this series is the same underlying property applied through standard deployment: when an LLM generates a type error in a statically typed language, it surfaces as a precise compile error." The overreaching sentence "Languages with richer type systems enable more constrained, more correct output from the LLMs working in them" has been removed from both articles.
New problem: None.

---

**Finding 2 — ">50%" qualification**
Status: APPLIED
Evidence: Both articles now specify the scope: "more than half for synthesis and translation tasks" — restricting the >50% claim to those task types rather than asserting it universally. Repair is given its own figure (37%). Reference annotations updated consistently.
New problem: None.

---

**Finding 3 — 94% orphaned**
Status: APPLIED
Evidence: Part 2 now includes: "That concession does not strand the 94 percent figure — it establishes why the second finding works. Type errors dominate compilation failures; constraining generation on types therefore addresses the dominant failure mode." The purpose of the 94% figure is now explicit. "Simply do not arise" has been softened to "may not surface as compilation errors at all."
New problem: Minor wording residual — "rather than arising identically later" is awkward. Errors don't arise "identically" later in Python; they arise differently (as AttributeErrors, wrong-shape behaviour) or not at all. The phrase reads as if Python defers the same error in the same form, which is not what duck typing produces. The word "identically" should be removed or replaced: "may not surface as compilation errors at all, or may surface as runtime failures with different symptoms." Not a logical problem, but a precision issue a Python advocate would probe.

---

**Finding 4 — "Significantly"**
Status: APPLIED
Evidence: Part 2 replaces "significantly" with specific figures: "37 percent on average" for repair and "3.5 to 5.5 percent relatively" for synthesis/translation. Both figures also appear in the Part 2 reference annotation.
New problem: Part 1's body text includes the 37% repair figure but not the 3.5–5.5% synthesis/translation correctness figure, while Part 1's reference annotation includes both. A reader of Part 1 who checks the annotation will find a figure that wasn't in the body. This is a minor inconsistency — Part 1 is a summary article and directing detail to Part 2 is defensible — but the annotation having more specific claims than the body it annotates is slightly unusual. Consider either adding the synthesis/translation figure to Part 1's body in parentheses, or removing it from Part 1's annotation with a note that the full figures are in Part 2.

---

**Finding 5 — TypeScript role**
Status: APPLIED
Evidence: Part 2 now reads "implemented and evaluated on TypeScript across HumanEval and MBPP" — neutral description with benchmark names, replacing the purposive framing "extended specifically to TypeScript to demonstrate practicality."
New problem: None.

---

## Secondary Pass

**New Finding A — 94% figure broadened without verification**
**Severity:** Important
**Location:** Part 1, "The token cost corrective"; Part 2, Section 1; both reference annotations
**The claim:** Both articles now state "94 percent of LLM-generated compilation errors are type-related — confirmed in both Java and TypeScript."
**The challenge:** In Round 1, the 94% figure was Java-specific: "94 percent of LLM-generated Java compilation errors are type-related." The fix to Finding 3 introduced TypeScript confirmation: the figure has been broadened to "compilation errors" in both Java and TypeScript. This requires that the paper actually reports a comparable figure for TypeScript — not merely that it evaluates type-constrained decoding on TypeScript. The paper may find that 94% of Java compilation errors are type-related while TypeScript's figure is different (higher or lower), because the type systems differ and the error distributions may differ. If the 94% figure is Java-specific and the TypeScript experiments don't report the same breakdown, the broadening from "Java compilation errors" to "compilation errors — confirmed in both Java and TypeScript" overstates what the paper found. The confirmation in the reference annotations ("94% of LLM-generated compilation errors are type-related") has dropped "Java" entirely, which compounds the potential overclaim.
**Suggested fix:** Verify against the paper whether the 94% figure applies specifically to Java or to both languages. If Java-specific: restore "94% of LLM-generated Java compilation errors are type-related — the paper also evaluates TypeScript for type-constrained decoding but the error-type breakdown for TypeScript is [X / not separately reported]." If the 94% figure is confirmed for TypeScript as well: retain the current text but add the TypeScript figure explicitly so readers can verify it. Do not collapse two separate figures into one claim without stating both.

---

## Overall Assessment

**The Mündler passages are substantially improved and close to sound.** The three substantive problems from Round 1 — the inference gap, the unqualified ">50%" claim, and the orphaned 94% figure — are all resolved. The bridge to standard deployment is explicit and well-reasoned. The task-type qualification on the error-reduction figure is correct. The 94% figure now has a clear purpose in the argument.

One new Important issue requires resolution before publication: the 94% figure has been broadened from Java-specific to "confirmed in both Java and TypeScript" without verification that the paper reports this figure for TypeScript. This is exactly the citation verification risk the spec identifies. It can be resolved by checking the paper's error analysis section for TypeScript. If the figure doesn't apply equally to TypeScript, the text should be revised. If it does, the current text is accurate and should stand.

The wording residual in Finding 3 ("arising identically later") and the annotation/body inconsistency in Part 1 (Finding 4) are minor and can be addressed in the same pass.

Resolve the 94% broadening. The passages are otherwise sound.
