package io.sparge.server;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * Manages state.json — one entry per post slug.
 * Mirrors scripts/state.py.
 *
 * CDI bean uses ActiveProject to resolve the state file path.
 * Tests use the package-private StateStore(Path) constructor directly.
 */
@ApplicationScoped
public class StateStore {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    @Inject ActiveProject activeProject;

    public StateStore() {}

    /** Testable constructor — bypasses CDI. */
    StateStore(Path stateFile) {
        this.fixedStateFile = stateFile;
    }

    private Path fixedStateFile;

    private Path stateFile() {
        if (fixedStateFile != null) return fixedStateFile;
        return activeProject.getProjectDir().resolve("state.json");
    }

    // ── Internal helpers ──────────────────────────────────────────────────────

    private ObjectNode load() {
        Path f = stateFile();
        try {
            return Files.exists(f) ? (ObjectNode) MAPPER.readTree(f.toFile()) : MAPPER.createObjectNode();
        } catch (IOException e) {
            return MAPPER.createObjectNode();
        }
    }

    private void saveInternal(ObjectNode state) throws IOException {
        MAPPER.writerWithDefaultPrettyPrinter().writeValue(stateFile().toFile(), state);
    }

    private static boolean isStale(ObjectNode entry) {
        String htmlHash = entry.path("html").path("hash").asText(null);
        String mdHash   = entry.path("md").path("html_hash").asText(null);
        String genAt    = entry.path("md").path("generated_at").asText(null);
        return genAt != null && !genAt.isEmpty()
            && htmlHash != null && !htmlHash.isEmpty()
            && mdHash   != null && !mdHash.isEmpty()
            && !htmlHash.equals(mdHash);
    }

    private static ObjectNode computed(ObjectNode entry) {
        ObjectNode copy = entry.deepCopy();
        ObjectNode md   = copy.has("md") ? (ObjectNode) copy.get("md") : MAPPER.createObjectNode();
        md.put("stale", isStale(copy));
        copy.set("md", md);
        return copy;
    }

    /** sha256[:12] of a file — matches Python's _hash(). */
    static String hash(Path file) throws Exception {
        byte[] bytes  = Files.readAllBytes(file);
        byte[] digest = MessageDigest.getInstance("SHA-256").digest(bytes);
        StringBuilder sb = new StringBuilder();
        for (byte b : digest) sb.append(String.format("%02x", b));
        return sb.substring(0, 12);
    }

    private static String now() {
        return Instant.now().toString().substring(0, 19);
    }

    @SuppressWarnings("unchecked")
    private static void mergeInto(ObjectNode entry, Map<String, Object> patch) {
        for (Map.Entry<String, Object> kv : patch.entrySet()) {
            String key = kv.getKey();
            Object val = kv.getValue();
            if ((key.equals("html") || key.equals("md") || key.equals("assets"))
                    && val instanceof Map) {
                ObjectNode sub = entry.has(key)
                        ? (ObjectNode) entry.get(key)
                        : MAPPER.createObjectNode();
                for (Map.Entry<String, Object> sv : ((Map<String, Object>) val).entrySet()) {
                    sub.set(sv.getKey(), toJsonNode(sv.getValue()));
                }
                entry.set(key, sub);
            } else {
                entry.set(key, toJsonNode(val));
            }
        }
    }

    private static com.fasterxml.jackson.databind.JsonNode toJsonNode(Object val) {
        if (val == null)              return MAPPER.nullNode();
        if (val instanceof Boolean b) return MAPPER.getNodeFactory().booleanNode(b);
        if (val instanceof Integer i) return MAPPER.getNodeFactory().numberNode(i);
        if (val instanceof Long l)    return MAPPER.getNodeFactory().numberNode(l);
        if (val instanceof String s)  return MAPPER.getNodeFactory().textNode(s);
        if (val instanceof List<?> list) {
            ArrayNode arr = MAPPER.createArrayNode();
            for (Object item : list) arr.add(toJsonNode(item));
            return arr;
        }
        if (val instanceof Map<?,?> map) {
            ObjectNode obj = MAPPER.createObjectNode();
            for (Map.Entry<?,?> e : map.entrySet()) {
                obj.set(e.getKey().toString(), toJsonNode(e.getValue()));
            }
            return obj;
        }
        return MAPPER.getNodeFactory().textNode(val.toString());
    }

    // ── Public API ────────────────────────────────────────────────────────────

    public List<ObjectNode> getAll() {
        ObjectNode state = load();
        List<ObjectNode> result = new ArrayList<>();
        state.fields().forEachRemaining(e -> result.add(computed((ObjectNode) e.getValue())));
        return result;
    }

    public ObjectNode get(String slug) {
        ObjectNode entry = (ObjectNode) load().get(slug);
        return entry == null ? null : computed(entry);
    }

    public synchronized void update(String slug, Map<String, Object> patch) {
        ObjectNode state = load();
        ObjectNode entry = state.has(slug)
                ? (ObjectNode) state.get(slug)
                : MAPPER.createObjectNode().put("slug", slug);
        mergeInto(entry, patch);
        state.set(slug, entry);
        try { saveInternal(state); } catch (IOException e) { throw new RuntimeException(e); }
    }

    // ── HTML issues ───────────────────────────────────────────────────────────

    public synchronized void dismissHtmlCheck(String slug, String issueType) {
        ObjectNode state = load();
        ObjectNode post  = (ObjectNode) state.get(slug);
        if (post == null) return;

        ObjectNode dismissed = post.has("dismissed_html_checks")
                ? (ObjectNode) post.get("dismissed_html_checks")
                : MAPPER.createObjectNode();
        dismissed.put(issueType, now());
        post.set("dismissed_html_checks", dismissed);

        ArrayNode issues = post.has("html")
                ? (ArrayNode) ((ObjectNode) post.get("html")).path("issues")
                : MAPPER.createArrayNode();
        if (issues.isMissingNode() || !issues.isArray()) issues = MAPPER.createArrayNode();
        ArrayNode filtered = MAPPER.createArrayNode();
        for (var i : issues) {
            String t = i.path("type").asText(i.path("check").asText(""));
            if (!t.equals(issueType)) filtered.add(i);
        }
        post.with("html").set("issues", filtered);

        state.set(slug, post);
        try { saveInternal(state); } catch (IOException e) { throw new RuntimeException(e); }
    }

    public synchronized void undismissHtmlCheck(String slug, String issueType) {
        ObjectNode state = load();
        ObjectNode post  = (ObjectNode) state.get(slug);
        if (post == null) return;
        if (post.has("dismissed_html_checks")) {
            ((ObjectNode) post.get("dismissed_html_checks")).remove(issueType);
        }
        state.set(slug, post);
        try { saveInternal(state); } catch (IOException e) { throw new RuntimeException(e); }
    }

    public synchronized void setHtmlIssues(String slug, List<Map<String, Object>> issues,
                                             String htmlHash, String checkedAt) {
        ObjectNode state = load();
        ObjectNode post  = state.has(slug) ? (ObjectNode) state.get(slug)
                                           : MAPPER.createObjectNode().put("slug", slug);

        ObjectNode dismissed = post.has("dismissed_html_checks")
                ? (ObjectNode) post.get("dismissed_html_checks")
                : MAPPER.createObjectNode();

        Set<String> detected = new HashSet<>();
        for (Map<String, Object> i : issues) {
            Object t = i.get("type");
            if (t != null) detected.add(t.toString());
        }

        Set<String> toRemove = new HashSet<>();
        dismissed.fieldNames().forEachRemaining(t -> { if (!detected.contains(t)) toRemove.add(t); });
        toRemove.forEach(dismissed::remove);

        ArrayNode active = MAPPER.createArrayNode();
        for (Map<String, Object> i : issues) {
            String t = i.containsKey("type") ? i.get("type").toString() : "";
            if (!dismissed.has(t)) active.add(toJsonNode(i));
        }

        ObjectNode html = post.has("html") ? (ObjectNode) post.get("html")
                                           : MAPPER.createObjectNode();
        html.set("issues", active);
        html.put("checked_at", checkedAt != null ? checkedAt : now());
        if (htmlHash != null) html.put("hash", htmlHash);
        post.set("html", html);
        post.set("dismissed_html_checks", dismissed);

        state.set(slug, post);
        try { saveInternal(state); } catch (IOException e) { throw new RuntimeException(e); }
    }

    // ── MD issues ─────────────────────────────────────────────────────────────

    public synchronized void setMdIssues(String slug, List<Map<String, Object>> issues) {
        update(slug, Map.of("md", Map.of(
                "issues",       issues,
                "validated_at", now()
        )));
    }

    // ── mark_md_generated ─────────────────────────────────────────────────────

    public synchronized void markMdGenerated(String slug, Path htmlFile) {
        String h = null;
        if (htmlFile != null && Files.exists(htmlFile)) {
            try { h = hash(htmlFile); } catch (Exception ignored) {}
        }
        update(slug, Map.of(
                "html", Map.of("hash", h != null ? h : ""),
                "md",   Map.of(
                        "generated_at", now(),
                        "html_hash",    h != null ? h : "",
                        "staged",       false,
                        "staged_at",    "",
                        "issues",       List.of(),
                        "validated_at", ""
                )
        ));
    }

    // ── mark_enriched ─────────────────────────────────────────────────────────

    public synchronized void markEnriched(String slug, Map<String, Object> stats) {
        update(slug, Map.of("enriched", Map.of(
                "generated_at",      now(),
                "youtube_replaced",  stats.getOrDefault("youtube_replaced",  0),
                "gists_replaced",    stats.getOrDefault("gists_replaced",    0),
                "gists_failed",      stats.getOrDefault("gists_failed",      0),
                "classes_normalised",stats.getOrDefault("classes_normalised",0),
                "languages_detected",stats.getOrDefault("languages_detected",0),
                "embeds_wrapped",    stats.getOrDefault("embeds_wrapped",    0)
        )));
    }

    // ── Staged workflow ───────────────────────────────────────────────────────

    public synchronized void stage(String slug) {
        update(slug, Map.of("md", Map.of("staged", true, "staged_at", now())));
    }

    /** Original 3-arg form — no enriched dir (used by tests that don't need enriched-first). */
    public synchronized boolean acceptStaged(String slug, Path mdDir, Path postsDir) {
        return acceptStaged(slug, mdDir, postsDir, null);
    }

    /** Enriched-first form — mirrors Python accept_staged behaviour. */
    public synchronized boolean acceptStaged(String slug, Path mdDir, Path postsDir, Path enrichedDir) {
        Path staged = mdDir.resolve(slug + ".md.staged");
        if (!Files.exists(staged)) return false;
        try {
            Files.writeString(mdDir.resolve(slug + ".md"), Files.readString(staged));
            Files.delete(staged);
        } catch (IOException e) { throw new RuntimeException(e); }
        String h = null;
        Path htmlFile = (enrichedDir != null && Files.exists(enrichedDir.resolve(slug + ".html")))
                ? enrichedDir.resolve(slug + ".html")
                : postsDir.resolve(slug + ".html");
        if (Files.exists(htmlFile)) { try { h = hash(htmlFile); } catch (Exception ignored) {} }
        update(slug, Map.of("md", Map.of(
                "staged", false, "staged_at", "",
                "generated_at", now(), "html_hash", h != null ? h : "",
                "issues", List.of(), "validated_at", ""
        )));
        return true;
    }

    public synchronized boolean rejectStaged(String slug, Path mdDir) {
        Path staged = mdDir.resolve(slug + ".md.staged");
        boolean existed = Files.exists(staged);
        if (existed) { try { Files.delete(staged); } catch (IOException e) { throw new RuntimeException(e); } }
        update(slug, Map.of("md", Map.of("staged", false, "staged_at", "")));
        return existed;
    }
}
