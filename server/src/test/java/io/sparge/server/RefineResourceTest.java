package io.sparge.server;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.*;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;

class RefineResourceTest {

    static final ObjectMapper MAPPER = new ObjectMapper();

    static final String MD_WITH_UNTAGGED = """
            # Post

            ```
            System.out.println("hello");
            int x = 1;
            ```
            """;

    static final String MD_CLEAN = """
            # Post

            ```java
            System.out.println("hello");
            ```
            """;

    @Test void computeSuggestions_finds_untagged_fence() {
        var suggestions = RefineResource.computeSuggestions(MD_WITH_UNTAGGED, "slug", null);
        assertTrue(suggestions.stream()
            .anyMatch(s -> "language_tag_missing".equals(s.get("check"))));
    }

    @Test void computeSuggestions_clean_md_returns_empty_or_no_language_flag() {
        var suggestions = RefineResource.computeSuggestions(MD_CLEAN, "slug", null);
        assertTrue(suggestions.stream()
            .noneMatch(s -> "language_tag_missing".equals(s.get("check"))));
    }

    @Test void computeSuggestions_includes_fence_index() {
        var suggestions = RefineResource.computeSuggestions(MD_WITH_UNTAGGED, "slug", null);
        var lang = suggestions.stream()
            .filter(s -> "language_tag_missing".equals(s.get("check")))
            .findFirst();
        assertTrue(lang.isPresent());
        assertTrue(lang.get().containsKey("fence_index"));
        assertTrue(lang.get().containsKey("fingerprint"));
        assertTrue(lang.get().containsKey("content_sample"));
        assertTrue(lang.get().containsKey("fix"));
    }

    @Test void applyChecks_with_language_tag_missing_modifies_md() {
        var suggestions = RefineResource.computeSuggestions(MD_WITH_UNTAGGED, "slug", null);
        var acceptedChecks = List.of("language_tag_missing");
        String refined = RefineResource.applyChecks(MD_WITH_UNTAGGED, suggestions, acceptedChecks);
        // The opening fence should now have a language tag (e.g. ```java)
        // Note: closing fences (```) still appear — only the opening line is tagged
        assertTrue(refined.contains("```java\n") || refined.contains("```xml\n")
                || refined.contains("```text\n") || refined.contains("```sql\n"),
                "Opening fence should have a language tag now");
    }

    @Test void applyChecks_empty_accepted_returns_original() {
        String refined = RefineResource.applyChecks(MD_WITH_UNTAGGED, List.of(), List.of());
        assertEquals(MD_WITH_UNTAGGED, refined);
    }

    @Test void buildRules_creates_rule_from_suggestion() {
        var suggestions = RefineResource.computeSuggestions(MD_WITH_UNTAGGED, "slug", null);
        var langSugg = suggestions.stream()
            .filter(s -> "language_tag_missing".equals(s.get("check")))
            .findFirst().orElseThrow();
        var rules = RefineResource.buildRules(MD_WITH_UNTAGGED, List.of(langSugg));
        assertEquals(1, rules.size());
        assertEquals("language_tag_missing", rules.get(0).check());
        assertFalse(rules.get(0).fingerprint().isEmpty());
    }
}
