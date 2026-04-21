package io.sparge.server;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import java.util.List;
import java.util.Map;

class RefinementReplayTest {

    static final String MD_UNTAGGED = """
            # Post

            ```
            System.out.println("hello");
            int x = 1;
            ```

            Some text.

            ```java
            already tagged();
            ```
            """;

    static final String MD_PROSE = """
            # Post

            ```
            This is a prose sentence about the algorithm.
            Another sentence explaining what happens here.
            A third prose sentence describing the outcome.
            System.out.println("hi");
            ```
            """;

    @Test void parseFences_finds_correct_count() {
        var fences = RefinementReplay.parseFences(MD_UNTAGGED);
        assertEquals(2, fences.size());
    }

    @Test void parseFences_first_has_no_language() {
        var fences = RefinementReplay.parseFences(MD_UNTAGGED);
        assertEquals("", fences.get(0).language());
    }

    @Test void parseFences_second_has_java() {
        var fences = RefinementReplay.parseFences(MD_UNTAGGED);
        assertEquals("java", fences.get(1).language());
    }

    @Test void fingerprint_is_16_chars() {
        assertEquals(16, RefinementReplay.fingerprint("some content").length());
    }

    @Test void fingerprint_same_for_normalised_equivalent() {
        assertEquals(
            RefinementReplay.fingerprint("  Hello "),
            RefinementReplay.fingerprint("hello")
        );
    }

    @Test void findFence_exact_index_match() {
        var fences = RefinementReplay.parseFences(MD_UNTAGGED);
        String fp = RefinementReplay.fingerprint(fences.get(0).content());
        var rule = new RefinementRule("language_tag_missing", 0, fp,
            fences.get(0).content().substring(0, Math.min(128, fences.get(0).content().length())),
            Map.of("language", "java"));
        var found = RefinementReplay.findFence(fences, rule);
        assertTrue(found.isPresent());
        assertEquals(0, found.get().index());
    }

    @Test void findFence_slides_on_index_mismatch() {
        var fences = RefinementReplay.parseFences(MD_UNTAGGED);
        String fp = RefinementReplay.fingerprint(fences.get(0).content());
        // Rule says index=1 but content matches fence 0
        var rule = new RefinementRule("language_tag_missing", 1, fp,
            fences.get(0).content().substring(0, Math.min(128, fences.get(0).content().length())),
            Map.of("language", "java"));
        var found = RefinementReplay.findFence(fences, rule);
        assertTrue(found.isPresent());
        assertEquals(0, found.get().index());
    }

    @Test void findFence_returns_empty_on_no_match() {
        var fences = RefinementReplay.parseFences(MD_UNTAGGED);
        var rule = new RefinementRule("language_tag_missing", 99, "deadbeef00000000",
            "completely unrelated content xyz", Map.of("language", "java"));
        assertTrue(RefinementReplay.findFence(fences, rule).isEmpty());
    }

    @Test void replay_applies_language_tag() {
        var fences = RefinementReplay.parseFences(MD_UNTAGGED);
        String fp = RefinementReplay.fingerprint(fences.get(0).content());
        var rule = new RefinementRule("language_tag_missing", 0, fp,
            fences.get(0).content().substring(0, Math.min(128, fences.get(0).content().length())),
            Map.of("language", "java"));
        var result = RefinementReplay.replay(MD_UNTAGGED, List.of(rule));
        assertTrue(result.refinedMd().contains("```java\n"));
        assertTrue(result.conflicts().isEmpty());
    }

    @Test void replay_records_conflict_on_no_match() {
        var rule = new RefinementRule("language_tag_missing", 99, "deadbeef00000000",
            "no match", Map.of("language", "java"));
        var result = RefinementReplay.replay(MD_UNTAGGED, List.of(rule));
        assertEquals(1, result.conflicts().size());
        assertTrue(result.conflicts().get(0).contains("language_tag_missing"));
        assertEquals(MD_UNTAGGED, result.refinedMd()); // unchanged
    }

    @Test void replay_empty_rules_returns_original() {
        var result = RefinementReplay.replay(MD_UNTAGGED, List.of());
        assertEquals(MD_UNTAGGED, result.refinedMd());
        assertTrue(result.conflicts().isEmpty());
    }
}
