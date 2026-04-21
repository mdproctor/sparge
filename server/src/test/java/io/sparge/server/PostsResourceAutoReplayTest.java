package io.sparge.server;

import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

class PostsResourceAutoReplayTest {

    // ── Auto-replay tests ─────────────────────────────────────────────────────────

    @Test void autoReplay_empty_rules_returns_original() {
        String md = "# Hello\n";
        var result = PostsResource.autoReplay(md, List.of());
        assertEquals(md, result.refinedMd());
        assertTrue(result.conflicts().isEmpty());
    }

    @Test void autoReplay_applies_language_tag_rule() {
        String md = "# Post\n\n```\nSystem.out.println(\"hi\");\nint x = 1;\n```\n";
        var fences = RefinementReplay.parseFences(md);
        assertFalse(fences.isEmpty(), "Should find at least one fence");
        String fp = RefinementReplay.fingerprint(fences.get(0).content());
        String sample = fences.get(0).content().substring(0, Math.min(128, fences.get(0).content().length()));
        var accepted = List.of(Map.<String, Object>of(
            "check", "language_tag_missing",
            "fence_index", 0,
            "fingerprint", fp,
            "content_sample", sample,
            "fix", Map.of("language", "java")
        ));
        var result = PostsResource.autoReplay(md, accepted);
        assertTrue(result.refinedMd().contains("```java\n"),
            "Auto-replay should add java language tag");
        assertTrue(result.conflicts().isEmpty());
    }

    @Test void autoReplay_null_rules_returns_original() {
        String md = "# Hello\n";
        var result = PostsResource.autoReplay(md, null);
        assertEquals(md, result.refinedMd());
        assertTrue(result.conflicts().isEmpty());
    }
}
