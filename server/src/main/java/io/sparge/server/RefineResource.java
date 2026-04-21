package io.sparge.server;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import jakarta.inject.Inject;
import jakarta.ws.rs.*;
import jakarta.ws.rs.core.Response;

import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.stream.Collectors;

@Path("/api/posts/{slug}/refine")
public class RefineResource {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    @Inject ActiveProject activeProject;
    @Inject StateStore    stateStore;

    private Response err(int status, String msg) {
        String escaped = msg == null ? "error" : msg.replace("\"", "\\\"");
        return Response.status(status)
                .header("Content-Type",                "application/json; charset=utf-8")
                .header("Access-Control-Allow-Origin", "*")
                .entity("{\"error\":\"" + escaped + "\"}").build();
    }

    private Response ok(String json) {
        return Response.ok(json)
                .header("Content-Type",                "application/json; charset=utf-8")
                .header("Access-Control-Allow-Origin", "*").build();
    }

    /**
     * GET /api/posts/{slug}/refine
     * Run refine() on current MD. Returns all suggestions + refined_md (all applied).
     */
    @GET
    @Produces("application/json")
    public Response getSuggestions(@PathParam("slug") String slug) {
        SpargeConfig.ResolvedConfig cfg = activeProject.getConfig();
        if (cfg == null) return err(400, "no active project");
        java.nio.file.Path mdPath = cfg.mdDir().resolve(slug + ".md");
        if (!java.nio.file.Files.exists(mdPath)) return err(404, "MD not generated for " + slug);
        try {
            String md = java.nio.file.Files.readString(mdPath, StandardCharsets.UTF_8);
            java.nio.file.Path htmlPath = resolveHtmlPath(cfg, slug);
            List<Map<String, Object>> suggestions = computeSuggestions(md, slug, htmlPath);
            List<String> allChecks = suggestions.stream()
                    .map(s -> (String) s.get("check")).distinct().collect(Collectors.toList());
            String refinedMd = applyChecks(md, suggestions, allChecks);
            ObjectNode result = MAPPER.createObjectNode();
            result.set("suggestions", MAPPER.valueToTree(suggestions));
            result.put("refined_md", refinedMd);
            stateStore.setMdSuggestions(slug, suggestions);
            return ok(result.toString());
        } catch (Exception e) {
            return err(500, e.getMessage() != null ? e.getMessage() : "internal error");
        }
    }

    /**
     * POST /api/posts/{slug}/refine
     * Body: {"accepted_checks": ["language_tag_missing"]}
     * Re-runs with only those checks. Returns updated refined_md.
     */
    @POST
    @Consumes("application/json")
    @Produces("application/json")
    public Response computeRefined(@PathParam("slug") String slug, String body) {
        SpargeConfig.ResolvedConfig cfg = activeProject.getConfig();
        if (cfg == null) return err(400, "no active project");
        java.nio.file.Path mdPath = cfg.mdDir().resolve(slug + ".md");
        if (!java.nio.file.Files.exists(mdPath)) return err(404, "MD not generated for " + slug);
        try {
            var req = MAPPER.readTree(body);
            List<String> acceptedChecks = new ArrayList<>();
            req.path("accepted_checks").forEach(n -> acceptedChecks.add(n.asText()));
            String md = java.nio.file.Files.readString(mdPath, StandardCharsets.UTF_8);
            java.nio.file.Path htmlPath = resolveHtmlPath(cfg, slug);
            List<Map<String, Object>> suggestions = computeSuggestions(md, slug, htmlPath);
            String refinedMd = applyChecks(md, suggestions, acceptedChecks);
            ObjectNode result = MAPPER.createObjectNode();
            result.put("refined_md", refinedMd);
            return ok(result.toString());
        } catch (Exception e) {
            return err(500, e.getMessage() != null ? e.getMessage() : "internal error");
        }
    }

    /**
     * POST /api/posts/{slug}/refine/accept
     * Body: {"accepted": [{check, fence_index, fingerprint, content_sample, fix}, ...]}
     * Writes refined MD to disk; stores rules to state.
     */
    @POST
    @Path("accept")
    @Consumes("application/json")
    @Produces("application/json")
    public Response accept(@PathParam("slug") String slug, String body) {
        SpargeConfig.ResolvedConfig cfg = activeProject.getConfig();
        if (cfg == null) return err(400, "no active project");
        java.nio.file.Path mdPath = cfg.mdDir().resolve(slug + ".md");
        if (!java.nio.file.Files.exists(mdPath)) return err(404, "MD not generated for " + slug);
        try {
            var req = MAPPER.readTree(body);
            List<Map<String, Object>> acceptedRaw = new ArrayList<>();
            req.path("accepted").forEach(n -> {
                var m = new LinkedHashMap<String, Object>();
                n.fields().forEachRemaining(e -> {
                    if (e.getValue().isObject()) {
                        var inner = new LinkedHashMap<String, String>();
                        e.getValue().fields().forEachRemaining(ie ->
                            inner.put(ie.getKey(), ie.getValue().asText()));
                        m.put(e.getKey(), inner);
                    } else if (e.getValue().isInt()) {
                        m.put(e.getKey(), e.getValue().intValue());
                    } else {
                        m.put(e.getKey(), e.getValue().asText());
                    }
                });
                acceptedRaw.add(m);
            });
            String md = java.nio.file.Files.readString(mdPath, StandardCharsets.UTF_8);
            List<RefinementRule> rules = buildRules(md, acceptedRaw);
            RefinementReplay.ReplayResult result = RefinementReplay.replay(md, rules);
            java.nio.file.Files.writeString(mdPath, result.refinedMd(), StandardCharsets.UTF_8);
            stateStore.setRefinement(slug, acceptedRaw, result.conflicts());
            ObjectNode post = stateStore.get(slug);
            return ok(post != null ? post.toString() : "{}");
        } catch (Exception e) {
            return err(500, e.getMessage() != null ? e.getMessage() : "internal error");
        }
    }

    // ── Package-private helpers (used by tests and auto-replay) ───────────────

    static List<Map<String, Object>> computeSuggestions(String md, String slug,
                                                          java.nio.file.Path htmlPath) {
        List<MdIssue> issues = MdValidator.refine(md, slug, htmlPath);
        List<RefinementReplay.FenceBlock> fences = RefinementReplay.parseFences(md);
        List<Map<String, Object>> result = new ArrayList<>();
        for (MdIssue issue : issues) {
            Map<String, Object> s = new LinkedHashMap<>();
            s.put("check",  issue.check());
            s.put("level",  issue.level());
            s.put("detail", issue.detail());
            int fenceIdx = parseFenceIndex(issue.detail());
            Map<String, String> fix = Map.of();
            if (fenceIdx >= 0 && fenceIdx < fences.size()) {
                RefinementReplay.FenceBlock fence = fences.get(fenceIdx);
                String fp = RefinementReplay.fingerprint(fence.content());
                int sampleLen = Math.min(128, fence.content().length());
                s.put("fence_index",    fenceIdx);
                s.put("fingerprint",    fp);
                s.put("content_sample", fence.content().substring(0, sampleLen));
                fix = inferFix(issue.check(), fence);
            } else {
                s.put("fence_index",    -1);
                s.put("fingerprint",    "");
                s.put("content_sample", "");
            }
            s.put("fix", fix);
            result.add(s);
        }
        return result;
    }

    static String applyChecks(String md, List<Map<String, Object>> suggestions,
                               List<String> acceptedChecks) {
        List<RefinementRule> rules = suggestions.stream()
                .filter(s -> acceptedChecks.contains(s.get("check")))
                .filter(s -> {
                    Object fi = s.get("fence_index");
                    int idx = fi instanceof Number ? ((Number) fi).intValue() : -1;
                    return idx >= 0;
                })
                .map(s -> {
                    Object fi = s.get("fence_index");
                    int idx = fi instanceof Number ? ((Number) fi).intValue() : 0;
                    @SuppressWarnings("unchecked")
                    Map<String, String> fix = s.get("fix") instanceof Map
                            ? (Map<String, String>) s.get("fix") : Map.of();
                    return new RefinementRule(
                            (String) s.get("check"), idx,
                            (String) s.get("fingerprint"),
                            (String) s.get("content_sample"),
                            fix
                    );
                }).collect(Collectors.toList());
        return RefinementReplay.replay(md, rules).refinedMd();
    }

    static List<RefinementRule> buildRules(String md,
                                            List<Map<String, Object>> acceptedRaw) {
        return acceptedRaw.stream()
                .filter(r -> {
                    Object fi = r.get("fence_index");
                    int idx = fi instanceof Number ? ((Number) fi).intValue()
                            : (fi != null ? Integer.parseInt(fi.toString()) : -1);
                    return idx >= 0;
                })
                .map(r -> {
                    Object fi = r.get("fence_index");
                    int idx = fi instanceof Number ? ((Number) fi).intValue()
                            : Integer.parseInt(fi.toString());
                    Object fixObj = r.get("fix");
                    @SuppressWarnings("unchecked")
                    Map<String, String> fix = fixObj instanceof Map
                            ? (Map<String, String>) fixObj : Map.of();
                    return new RefinementRule(
                            (String) r.get("check"), idx,
                            (String) r.get("fingerprint"),
                            (String) r.get("content_sample"),
                            fix
                    );
                }).collect(Collectors.toList());
    }

    private static int parseFenceIndex(String detail) {
        if (detail == null) return -1;
        var m = java.util.regex.Pattern.compile("fence\\s+(\\d+)").matcher(detail);
        if (m.find()) return Integer.parseInt(m.group(1));
        return 0; // list-level issue: apply to first fence
    }

    private static Map<String, String> inferFix(String check,
                                                  RefinementReplay.FenceBlock fence) {
        if ("language_tag_missing".equals(check)) {
            String c = fence.content().toLowerCase();
            String lang = "text";
            if (c.contains("system.out") || c.contains("public class") || c.contains("import java")) lang = "java";
            else if (c.contains("<?xml") || c.contains("<beans") || c.contains("xmlns")) lang = "xml";
            else if (c.contains("select ") || c.contains("insert into") || c.contains("create table")) lang = "sql";
            else if (c.contains("def ") || c.contains("print(") || c.contains("import ") && c.contains(":")) lang = "python";
            else if (c.contains("function ") || c.contains("const ") || c.contains("var ") || c.contains("=>")) lang = "javascript";
            else if (c.contains("#!/bin/bash") || c.contains("echo ") || c.contains("export ")) lang = "bash";
            else if (c.contains("rule ") && c.contains("when") && c.contains("then")) lang = "drl";
            return Map.of("language", lang);
        }
        return Map.of();
    }

    private static java.nio.file.Path resolveHtmlPath(SpargeConfig.ResolvedConfig cfg, String slug) {
        java.nio.file.Path enriched = cfg.enrichedDir().resolve(slug + ".html");
        java.nio.file.Path original  = cfg.postsDir().resolve(slug + ".html");
        return java.nio.file.Files.exists(enriched) ? enriched : original;
    }
}
