package io.sparge.server;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import java.util.regex.*;

public final class RefinementReplay {

    private RefinementReplay() {}

    /** A parsed fenced code block. */
    public record FenceBlock(int index, int start, int end, String language, String content) {}

    /** Result of a replay operation. */
    public record ReplayResult(String refinedMd, List<String> conflicts) {}

    private static final Pattern FENCE_BLOCK = Pattern.compile(
        "(?m)^(```+)(\\w*)\\n(.*?)^\\1\\s*$", Pattern.DOTALL);

    /** Parse all fenced code blocks from md, in order. */
    public static List<FenceBlock> parseFences(String md) {
        List<FenceBlock> result = new ArrayList<>();
        Matcher m = FENCE_BLOCK.matcher(md);
        int idx = 0;
        while (m.find()) {
            result.add(new FenceBlock(idx++, m.start(), m.end(), m.group(2), m.group(3)));
        }
        return result;
    }

    /** Normalise text: lowercase + collapse whitespace. */
    static String normalise(String text) {
        return text.toLowerCase().replaceAll("\\s+", " ").strip();
    }

    /** SHA-256 of normalised text, first 16 hex chars. */
    public static String fingerprint(String content) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] hash = md.digest(normalise(content).getBytes(StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder(16);
            for (byte b : hash) {
                sb.append(String.format("%02x", b));
                if (sb.length() >= 16) break;
            }
            return sb.toString();
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }

    /** Simple normalised character-by-character similarity: matching chars / max length. */
    static double similarity(String a, String b) {
        String na = normalise(a), nb = normalise(b);
        if (na.isEmpty() && nb.isEmpty()) return 1.0;
        if (na.isEmpty() || nb.isEmpty()) return 0.0;
        int matches = 0;
        int len = Math.min(na.length(), nb.length());
        for (int i = 0; i < len; i++) {
            if (na.charAt(i) == nb.charAt(i)) matches++;
        }
        return (double) matches / Math.max(na.length(), nb.length());
    }

    /**
     * Locate the fence for a rule.
     * 1. Exact fingerprint at fenceIndex (no slide).
     * 2. Slide ±1, ±2: exact fingerprint.
     * 3. Slide ±1, ±2: contentSample similarity ≥ 0.85.
     */
    public static Optional<FenceBlock> findFence(List<FenceBlock> fences, RefinementRule rule) {
        Map<Integer, FenceBlock> byIndex = new HashMap<>();
        fences.forEach(f -> byIndex.put(f.index(), f));
        int[] offsets = {0, 1, -1, 2, -2};

        // Pass 1: exact fingerprint
        for (int offset : offsets) {
            FenceBlock c = byIndex.get(rule.fenceIndex() + offset);
            if (c != null && fingerprint(c.content()).equals(rule.fingerprint())) {
                return Optional.of(c);
            }
        }
        // Pass 2: fuzzy similarity
        for (int offset : offsets) {
            FenceBlock c = byIndex.get(rule.fenceIndex() + offset);
            if (c != null && similarity(c.content(), rule.contentSample()) >= 0.85) {
                return Optional.of(c);
            }
        }
        return Optional.empty();
    }

    /** Replace the opening ``` of a fence with ```<language>. */
    static String applyLanguageTag(String md, FenceBlock fence, String language) {
        String oldOpen = "```" + fence.language() + "\n";
        String newOpen = "```" + language + "\n";
        int openEnd = fence.start() + oldOpen.length();
        return md.substring(0, fence.start()) + newOpen + md.substring(openEnd);
    }

    /**
     * Replay all accepted rules against md.
     * Rules applied highest fence_index first to preserve string offsets.
     */
    public static ReplayResult replay(String md, List<RefinementRule> rules) {
        if (rules.isEmpty()) return new ReplayResult(md, List.of());
        List<String> conflicts = new ArrayList<>();
        String current = md;
        List<RefinementRule> sorted = new ArrayList<>(rules);
        sorted.sort(Comparator.comparingInt(RefinementRule::fenceIndex).reversed());

        for (RefinementRule rule : sorted) {
            List<FenceBlock> fences = parseFences(current);
            Optional<FenceBlock> found = findFence(fences, rule);
            if (found.isEmpty()) {
                conflicts.add(rule.check() + "@fence_" + rule.fenceIndex());
                continue;
            }
            FenceBlock fence = found.get();
            if ("language_tag_missing".equals(rule.check())) {
                String lang = rule.fix().getOrDefault("language", "");
                if (!lang.isEmpty()) current = applyLanguageTag(current, fence, lang);
            }
            // prose_in_code: marked as conflict for now (requires interactive extraction)
        }
        return new ReplayResult(current, conflicts);
    }
}
