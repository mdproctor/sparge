package io.sparge.server;

import jakarta.inject.Inject;
import jakarta.ws.rs.*;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;

@Path("/api/projects")
@Produces(MediaType.APPLICATION_JSON)
@Consumes(MediaType.APPLICATION_JSON)
public class ProjectsResource {

    @Inject PythonBridge bridge;

    @GET
    public Response list() {
        return BridgeResponse.of(bridge.call("bridge.projects_list"));
    }

    @POST
    public Response create(String body) {
        return BridgeResponse.of(bridge.call("bridge.projects_create",
                                             body == null ? "{}" : body));
    }

    @DELETE
    @Path("{id}")
    public Response delete(@PathParam("id") String id) {
        return BridgeResponse.of(bridge.call("bridge.projects_delete", id));
    }

    @POST
    @Path("{id}/activate")
    public Response activate(@PathParam("id") String id) {
        return BridgeResponse.of(bridge.call("bridge.projects_activate", id));
    }

    @POST
    @Path("{id}/ingest/run")
    public Response projectIngestRun(@PathParam("id") String id, String body) {
        return BridgeResponse.of(bridge.call("bridge.project_ingest_run",
                                             id, body == null ? "{}" : body));
    }
}
