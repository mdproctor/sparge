package io.sparge.server;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import jakarta.inject.Inject;
import jakarta.ws.rs.*;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;

import java.util.List;
import java.util.Map;

@Path("/api/posts")
@Produces(MediaType.APPLICATION_JSON)
@Consumes(MediaType.APPLICATION_JSON)
public class PostsResource {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    private static final java.util.regex.Pattern ARCHIVE_HEADER_RE =
            java.util.regex.Pattern.compile(
                    "<header\\s[^>]*class=\"[^\"]*archive-header[^\"]*\"[^>]*>.*?</header>",
                    java.util.regex.Pattern.DOTALL | java.util.regex.Pattern.CASE_INSENSITIVE);

    @Inject PythonBridge  bridge;
    @Inject StateStore    stateStore;
    @Inject ActiveProject activeProject;

    // ── CRUD ──────────────────────────────────────────────────────────────────

    @GET
    public Response list(@QueryParam("author") String author) {
        try {
            List<ObjectNode> posts = stateStore.getAll();
            String effectiveAuthor = (author != null) ? author : "";
            if (!effectiveAuthor.isEmpty()) {
                posts = posts.stream()
                        .filter(p -> effectiveAuthor.equals(p.path("author").asText("")))
                        .collect(java.util.stream.Collectors.toList());
            }
            posts.sort(java.util.Comparator
                    .comparing((ObjectNode p) -> p.path("date").asText(""))
                    .thenComparing(p -> p.path("slug").asText("")));
            ArrayNode result = MAPPER.createArrayNode();
            posts.forEach(result::add);
            return ok(result.toString());
        } catch (Exception e) {
            return err(e.getMessage());
        }
    }

    @GET
    @Path("{slug}")
    public Response get(@PathParam("slug") String slug) {
        ObjectNode post = stateStore.get(slug);
        if (post == null) return Response.status(404)
                .header("Content-Type", "application/json; charset=utf-8")
                .header("Access-Control-Allow-Origin", "*")
                .entity("{\"error\":\"unknown slug: " + slug + "\"}").build();
        return ok(post.toString());
    }

    @PATCH
    @Path("{slug}")
    public Response patch(@PathParam("slug") String slug, String body) {
        try {
            ObjectNode patch = (body != null && !body.isBlank())
                    ? (ObjectNode) MAPPER.readTree(body)
                    : MAPPER.createObjectNode();
            Map<String, Object> safe = new java.util.LinkedHashMap<>();
            if (patch.has("flagged"))   safe.put("flagged",   patch.get("flagged").asBoolean());
            if (patch.has("reviewed"))  safe.put("reviewed",  patch.get("reviewed").asBoolean());
            if (patch.has("user_note")) safe.put("user_note", patch.get("user_note").asText());
            stateStore.update(slug, safe);
            ObjectNode updated = stateStore.get(slug);
            return ok(updated != null ? updated.toString() : "{}");
        } catch (Exception e) {
            return err(e.getMessage());
        }
    }

    // ── HTML ──────────────────────────────────────────────────────────────────

    @GET
    @Path("{slug}/html")
    @Produces(MediaType.TEXT_PLAIN)
    public Response html(@PathParam("slug") String slug) {
        SpargeConfig.ResolvedConfig cfg = activeProject.getConfig();
        if (cfg == null) return err(400, "no active project");
        try {
            java.nio.file.Path enriched = cfg.enrichedDir().resolve(slug + ".html");
            java.nio.file.Path original  = cfg.postsDir().resolve(slug + ".html");
            java.nio.file.Path htmlPath  = java.nio.file.Files.exists(enriched) ? enriched : original;

            if (!java.nio.file.Files.exists(htmlPath)) {
                return Response.status(404)
                        .header("Content-Type",                "application/json; charset=utf-8")
                        .header("Access-Control-Allow-Origin", "*")
                        .entity("{\"error\":\"HTML not found: " + slug + "\"}")
                        .build();
            }

            String raw     = java.nio.file.Files.readString(htmlPath);
            String content = HtmlUtils.prettifyHtml(raw);

            return Response.ok(content)
                    .header("Content-Type",                "text/plain; charset=utf-8")
                    .header("Access-Control-Allow-Origin", "*")
                    .build();
        } catch (Exception e) {
            return err(e.getMessage());
        }
    }

    @GET
    @Path("{slug}/view")
    @Produces(MediaType.TEXT_HTML)
    public Response view(@PathParam("slug") String slug) {
        SpargeConfig.ResolvedConfig cfg = activeProject.getConfig();
        if (cfg == null) return err(400, "no active project");
        try {
            java.nio.file.Path enriched = cfg.enrichedDir().resolve(slug + ".html");
            java.nio.file.Path original  = cfg.postsDir().resolve(slug + ".html");
            java.nio.file.Path htmlPath  = java.nio.file.Files.exists(enriched) ? enriched : original;
            if (!java.nio.file.Files.exists(htmlPath)) {
                return Response.status(404)
                        .header("Content-Type",                "application/json; charset=utf-8")
                        .header("Access-Control-Allow-Origin", "*")
                        .entity("{\"error\":\"HTML not found: " + slug + "\"}").build();
            }
            String content = java.nio.file.Files.readString(htmlPath,
                    java.nio.charset.StandardCharsets.UTF_8);
            content = ARCHIVE_HEADER_RE.matcher(content).replaceAll("");
            return Response.ok(content)
                    .header("Content-Type",                "text/html; charset=utf-8")
                    .header("Access-Control-Allow-Origin", "*")
                    .build();
        } catch (Exception e) {
            return err(e.getMessage());
        }
    }

    @POST
    @Path("{slug}/save-html")
    @Consumes({MediaType.TEXT_PLAIN, MediaType.TEXT_HTML, MediaType.WILDCARD})
    public Response saveHtml(@PathParam("slug") String slug, String body) {
        SpargeConfig.ResolvedConfig cfg = activeProject.getConfig();
        if (cfg == null) return err(400, "no active project");
        try {
            java.nio.file.Path enrichedDir = cfg.enrichedDir();
            java.nio.file.Files.createDirectories(enrichedDir);
            java.nio.file.Files.writeString(enrichedDir.resolve(slug + ".html"),
                    body == null ? "" : body, java.nio.charset.StandardCharsets.UTF_8);
            ObjectNode post = stateStore.get(slug);
            return ok(post != null ? post.toString() : "{}");
        } catch (Exception e) {
            return err(e.getMessage());
        }
    }

    // ── Markdown ──────────────────────────────────────────────────────────────

    @POST
    @Path("{slug}/generate-md")
    public Response generateMd(@PathParam("slug") String slug,
                                @QueryParam("dry") @DefaultValue("") String dryParam) {
        // Accept ?dry=1 (Python server convention) and ?dry=true (JAX-RS convention)
        boolean dry = "1".equals(dryParam) || "true".equalsIgnoreCase(dryParam);
        return BridgeResponse.of(bridge.call("bridge.post_generate_md", slug, dry));
    }

    @POST
    @Path("{slug}/validate-md")
    public Response validateMd(@PathParam("slug") String slug) {
        return BridgeResponse.of(bridge.call("bridge.post_validate_md", slug));
    }

    @POST
    @Path("{slug}/save-md")
    @Consumes(MediaType.TEXT_PLAIN)
    public Response saveMd(@PathParam("slug") String slug, String body) {
        SpargeConfig.ResolvedConfig cfg = activeProject.getConfig();
        if (cfg == null) return err(400, "no active project");
        try {
            java.nio.file.Path mdPath = cfg.mdDir().resolve(slug + ".md");
            java.nio.file.Files.createDirectories(mdPath.getParent());
            java.nio.file.Files.writeString(mdPath,
                    body == null ? "" : body, java.nio.charset.StandardCharsets.UTF_8);
            java.nio.file.Path htmlPath = cfg.postsDir().resolve(slug + ".html");
            stateStore.markMdGenerated(slug,
                    java.nio.file.Files.exists(htmlPath) ? htmlPath : null);
            ObjectNode post = stateStore.get(slug);
            return ok(post != null ? post.toString() : "{}");
        } catch (Exception e) {
            return err(e.getMessage());
        }
    }

    // ── Staged workflow ───────────────────────────────────────────────────────

    @GET
    @Path("{slug}/staged")
    @Produces(MediaType.TEXT_PLAIN)
    public Response stagedGet(@PathParam("slug") String slug) {
        SpargeConfig.ResolvedConfig cfg = activeProject.getConfig();
        if (cfg == null) return err(400, "no active project");
        java.nio.file.Path staged = cfg.mdDir().resolve(slug + ".md.staged");
        if (!java.nio.file.Files.exists(staged)) return err(404, "no staged version");
        try {
            return Response.ok(java.nio.file.Files.readString(staged))
                    .header("Content-Type",                "text/plain; charset=utf-8")
                    .header("Access-Control-Allow-Origin", "*")
                    .build();
        } catch (Exception e) {
            return err(e.getMessage());
        }
    }

    @POST
    @Path("{slug}/stage")
    @Consumes({MediaType.TEXT_PLAIN, MediaType.WILDCARD})
    public Response stage(@PathParam("slug") String slug, String body) {
        SpargeConfig.ResolvedConfig cfg = activeProject.getConfig();
        if (cfg == null) return err(400, "no active project");
        try {
            java.nio.file.Files.writeString(cfg.mdDir().resolve(slug + ".md.staged"),
                    body == null ? "" : body);
            stateStore.stage(slug);
            ObjectNode post = stateStore.get(slug);
            return ok(post != null ? post.toString() : "{}");
        } catch (Exception e) {
            return err(e.getMessage());
        }
    }

    @POST
    @Path("{slug}/accept-staged")
    @Consumes(MediaType.WILDCARD)
    public Response acceptStaged(@PathParam("slug") String slug) {
        SpargeConfig.ResolvedConfig cfg = activeProject.getConfig();
        if (cfg == null) return err(400, "no active project");
        boolean accepted = stateStore.acceptStaged(slug, cfg.mdDir(), cfg.postsDir(), cfg.enrichedDir());
        if (!accepted) return Response.status(404)
                .entity("{\"error\":\"no staged version to accept\"}")
                .header("Content-Type",                "application/json; charset=utf-8")
                .header("Access-Control-Allow-Origin", "*")
                .build();
        ObjectNode post = stateStore.get(slug);
        return ok(post != null ? post.toString() : "{}");
    }

    @POST
    @Path("{slug}/reject-staged")
    @Consumes(MediaType.WILDCARD)
    public Response rejectStaged(@PathParam("slug") String slug) {
        SpargeConfig.ResolvedConfig cfg = activeProject.getConfig();
        if (cfg == null) return err(400, "no active project");
        try {
            stateStore.rejectStaged(slug, cfg.mdDir());
            ObjectNode post = stateStore.get(slug);
            return ok(post != null ? post.toString() : "{}");
        } catch (Exception e) {
            return err(e.getMessage());
        }
    }

    // ── Scan ─────────────────────────────────────────────────────────────────

    @POST
    @Path("{slug}/scan")
    public Response scan(@PathParam("slug") String slug) {
        SpargeConfig.ResolvedConfig cfg = activeProject.getConfig();
        if (cfg == null) {
            return BridgeResponse.of(bridge.call("bridge.post_scan_html", slug));
        }
        try {
            java.nio.file.Path postsDir    = cfg.postsDir();
            java.nio.file.Path enrichedDir = cfg.enrichedDir();
            java.nio.file.Path htmlPath    = postsDir.resolve(slug + ".html");

            if (!java.nio.file.Files.exists(htmlPath)) {
                return Response.status(404)
                        .header("Content-Type",                "application/json; charset=utf-8")
                        .header("Access-Control-Allow-Origin", "*")
                        .entity("{\"error\":\"HTML not found: " + slug + "\"}").build();
            }

            java.nio.file.Path enrichedPath = enrichedDir.resolve(slug + ".html");

            // Enrich if not yet enriched (Java — Enricher.java, Phase 5)
            if (!java.nio.file.Files.exists(enrichedPath)) {
                try {
                    Map<String, Integer> enrichStats = new Enricher().enrich(
                            htmlPath, enrichedPath, cfg.assetsDir(), cfg.githubToken());
                    stateStore.markEnriched(slug, new java.util.HashMap<>(enrichStats));
                } catch (Exception enrichEx) {
                    System.err.println("Warning: enrichment failed for " + slug + ": " + enrichEx.getMessage());
                }
            }

            // Apply code block fixes to enriched copy (Java)
            java.nio.file.Path scanPath = java.nio.file.Files.exists(enrichedPath) ? enrichedPath : htmlPath;
            if (java.nio.file.Files.exists(enrichedPath)) {
                try {
                    org.jsoup.nodes.Document soup = org.jsoup.Jsoup.parse(
                            java.nio.file.Files.readString(enrichedPath));
                    if (CodeBlockFixer.apply(soup)) {
                        java.nio.file.Files.writeString(enrichedPath, soup.outerHtml());
                    }
                } catch (Exception ignored) {}
            }

            // Scan HTML issues (Java)
            java.util.List<ScanHtml.Issue> rawIssues = ScanHtml.scanPost(scanPath, postsDir);
            java.util.List<java.util.Map<String, Object>> issues = rawIssues.stream().map(i ->
                    java.util.Map.<String, Object>of(
                            "type",     i.type(),
                            "level",    i.level(),
                            "check",    i.type(),
                            "detail",   i.detail(),
                            "selector", i.selector() != null ? i.selector() : ""
                    )).collect(java.util.stream.Collectors.toList());
            stateStore.setHtmlIssues(slug, issues, null, null);

            // Scan assets (Java)
            try {
                ScanAssets.Result assets = ScanAssets.scan(scanPath, htmlPath, cfg.serveRoot());
                stateStore.update(slug, java.util.Map.of("assets", java.util.Map.of(
                        "total",      assets.total(),
                        "localised",  assets.localised(),
                        "broken",     assets.broken(),
                        "checked_at", java.time.Instant.now().toString().substring(0, 19)
                )));
            } catch (Exception ignored) {}

            ObjectNode post = stateStore.get(slug);
            return ok(post != null ? post.toString() : "{}");
        } catch (Exception e) {
            return err(e.getMessage());
        }
    }

    // ── Dismiss ───────────────────────────────────────────────────────────────

    @POST
    @Path("{slug}/dismiss-html-check")
    public Response dismiss(@PathParam("slug") String slug, String body) {
        try {
            ObjectNode patch = (body != null && !body.isBlank())
                    ? (ObjectNode) MAPPER.readTree(body)
                    : MAPPER.createObjectNode();
            String issueType = patch.path("type").asText("");
            if (issueType.isEmpty()) return Response.status(400)
                    .header("Content-Type",                "application/json; charset=utf-8")
                    .header("Access-Control-Allow-Origin", "*")
                    .entity("{\"error\":\"type required\"}").build();
            stateStore.dismissHtmlCheck(slug, issueType);
            ObjectNode post = stateStore.get(slug);
            return ok(post != null ? post.toString() : "{}");
        } catch (Exception e) {
            return err(e.getMessage());
        }
    }

    @DELETE
    @Path("{slug}/dismiss-html-check/{type}")
    public Response undismiss(@PathParam("slug") String slug,
                               @PathParam("type") String type) {
        stateStore.undismissHtmlCheck(slug, type);
        return scan(slug);  // re-scan immediately so the issue reappears
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private Response ok(String json) {
        return Response.ok(json)
                .header("Content-Type",                "application/json; charset=utf-8")
                .header("Access-Control-Allow-Origin", "*")
                .build();
    }

    private Response err(String msg) {
        String escaped = msg == null ? "error" : msg.replace("\"", "\\\"");
        return Response.serverError()
                .header("Content-Type",                "application/json; charset=utf-8")
                .header("Access-Control-Allow-Origin", "*")
                .entity("{\"error\":\"" + escaped + "\"}")
                .build();
    }

    private Response err(int status, String msg) {
        String escaped = msg == null ? "error" : msg.replace("\"", "\\\"");
        return Response.status(status)
                .header("Content-Type",                "application/json; charset=utf-8")
                .header("Access-Control-Allow-Origin", "*")
                .entity("{\"error\":\"" + escaped + "\"}")
                .build();
    }
}
