package io.sparge.server;

import jakarta.inject.Inject;
import jakarta.ws.rs.*;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;

@Path("/api/posts")
@Produces(MediaType.APPLICATION_JSON)
@Consumes(MediaType.APPLICATION_JSON)
public class PostsResource {

    @Inject PythonBridge bridge;

    // ── CRUD ──────────────────────────────────────────────────────────────────

    @GET
    public Response list(@QueryParam("author") String author) {
        // Empty string means no filter (matches server.py behaviour)
        return BridgeResponse.of(bridge.call("bridge.posts_list",
                                             author != null ? author : ""));
    }

    @GET
    @Path("{slug}")
    public Response get(@PathParam("slug") String slug) {
        return BridgeResponse.of(bridge.call("bridge.post_get", slug));
    }

    @PATCH
    @Path("{slug}")
    public Response patch(@PathParam("slug") String slug, String body) {
        return BridgeResponse.of(bridge.call("bridge.post_patch", slug,
                                             body == null ? "{}" : body));
    }

    // ── HTML ──────────────────────────────────────────────────────────────────

    @GET
    @Path("{slug}/html")
    @Produces(MediaType.TEXT_PLAIN)
    public Response html(@PathParam("slug") String slug) {
        return BridgeResponse.of(bridge.call("bridge.post_html", slug));
    }

    @GET
    @Path("{slug}/view")
    @Produces(MediaType.TEXT_HTML)
    public Response view(@PathParam("slug") String slug) {
        return BridgeResponse.of(bridge.call("bridge.post_view", slug));
    }

    @POST
    @Path("{slug}/save-html")
    @Consumes({MediaType.TEXT_PLAIN, MediaType.TEXT_HTML, MediaType.WILDCARD})
    public Response saveHtml(@PathParam("slug") String slug, String body) {
        return BridgeResponse.of(bridge.call("bridge.post_save_html", slug,
                                             body == null ? "" : body));
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
        return BridgeResponse.of(bridge.call("bridge.post_save_md", slug,
                                             body == null ? "" : body));
    }

    // ── Staged workflow ───────────────────────────────────────────────────────

    @GET
    @Path("{slug}/staged")
    @Produces(MediaType.TEXT_PLAIN)
    public Response stagedGet(@PathParam("slug") String slug) {
        return BridgeResponse.of(bridge.call("bridge.post_staged_get", slug));
    }

    @POST
    @Path("{slug}/stage")
    @Consumes(MediaType.TEXT_PLAIN)
    public Response stage(@PathParam("slug") String slug, String body) {
        return BridgeResponse.of(bridge.call("bridge.post_stage", slug,
                                             body == null ? "" : body));
    }

    @POST
    @Path("{slug}/accept-staged")
    public Response acceptStaged(@PathParam("slug") String slug) {
        return BridgeResponse.of(bridge.call("bridge.post_accept_staged", slug));
    }

    @POST
    @Path("{slug}/reject-staged")
    public Response rejectStaged(@PathParam("slug") String slug) {
        return BridgeResponse.of(bridge.call("bridge.post_reject_staged", slug));
    }

    // ── Scan ─────────────────────────────────────────────────────────────────

    @POST
    @Path("{slug}/scan")
    public Response scan(@PathParam("slug") String slug) {
        return BridgeResponse.of(bridge.call("bridge.post_scan_html", slug));
    }

    // ── Dismiss ───────────────────────────────────────────────────────────────

    @POST
    @Path("{slug}/dismiss-html-check")
    public Response dismiss(@PathParam("slug") String slug, String body) {
        return BridgeResponse.of(bridge.call("bridge.post_dismiss_html_check", slug,
                                             body == null ? "{}" : body));
    }

    @DELETE
    @Path("{slug}/dismiss-html-check/{type}")
    public Response undismiss(@PathParam("slug") String slug,
                               @PathParam("type") String type) {
        return BridgeResponse.of(bridge.call("bridge.post_undismiss_html_check", slug, type));
    }
}
