# Adversarial Review Round 3: Mündler et al. Final Verification
## Parts 1 and 2 — *When the Machine Codes*

**Reviewer:** Adversic Claude session (independent)
**Date:** 2026-04-26
**Scope:** Five specific checks only.

---

**Check 1 — "Confirmed in both Java and TypeScript" removed from both articles**
CONFIRMED. Neither article contains this phrase. Part 1 reads "94 percent of LLM-generated TypeScript compilation errors are type-related." Part 2 reads identically. The multi-language claim is gone.

---

**Check 2 — 94% correctly attributed to TypeScript specifically**
CONFIRMED with one residual. Both articles now say "TypeScript compilation errors" — the TypeScript attribution is correct. However, in Part 1 the immediately following sentence reads: "The 94 percent figure applies to typed languages; the inference to what this means for Python is the series' own." Since the figure has been narrowed to TypeScript specifically, "applies to typed languages" (plural, general) is now imprecise — it implies the figure generalises across typed languages, which is itself a series inference, not what the paper shows. Part 2 handles this better by saying only "The inference to Python is the series' own" without claiming the figure applies to typed languages broadly. The Part 1 sentence should be updated to match: "The 94 percent figure is from TypeScript compilation; the inference to what this means for Python is the series' own."

---

**Check 3 — Part 1 annotation no longer contains the 3.5–5.5% figure**
CONFIRMED. Part 1's annotation reads: "94% of LLM-generated TypeScript compilation errors are type-related; type-constrained decoding reduces compilation errors by >50% for synthesis/translation; increases repair correctness by 37% on average; evaluated on TypeScript." The 3.5–5.5% figure is absent.

---

**Check 4 — Part 2 annotation still contains the 3.5–5.5% figure**
CONFIRMED. Part 2's annotation reads: "...increases repair correctness by 37% on average; 3.5–5.5% relative improvement in synthesis/translation correctness; implemented and evaluated on TypeScript." The figure is present and consistent with the Part 2 body text.

---

**Check 5 — No new problems introduced**
TWO MINOR ISSUES:

First: as noted in Check 2, Part 1's "The 94 percent figure applies to typed languages" is imprecise given the narrowing. This is a one-sentence fix — not a new logical problem, but an inconsistency the change introduced.

Second: Part 2 adds a new claim not present in prior versions: "type errors dominate; syntax errors account for the remaining 6 percent." The 6% is an arithmetic inference from 100% − 94%, but attributing the remaining 6% specifically to syntax errors asserts knowledge of the paper's error taxonomy that may not be warranted. If the paper's 94% type-related figure leaves a remainder that is not exclusively syntax errors — if there are naming errors, import errors, or other categories — the claim that syntax errors account for the remaining 6% is a characterisation that needs to be in the paper. This should be verified or softened to "the remaining 6 percent are non-type errors" if the paper's breakdown isn't available at that level of detail.

---

**Overall: Yes — sound, subject to two minor fixes.**

The substantive work is complete. The 94% figure is correctly attributed to TypeScript; the "confirmed in both Java and TypeScript" overclaim is gone; the annotations are internally consistent and appropriately differentiated between Part 1 and Part 2. The two residuals are editorial, not logical:

1. Part 1: replace "The 94 percent figure applies to typed languages" with "The 94 percent figure is from TypeScript compilation."
2. Part 2: verify or soften "syntax errors account for the remaining 6 percent" — if the paper doesn't specify the composition of the non-type-related errors, "the remaining 6 percent are non-type-related" is the safe phrasing.

Neither residual undermines the argument. The Mündler passages are sound.
