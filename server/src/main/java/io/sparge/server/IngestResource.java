package io.sparge.server;

import jakarta.inject.Inject;
import jakarta.ws.rs.*;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;

@Path("/api/ingest")
@Produces(MediaType.APPLICATION_JSON)
@Consumes(MediaType.APPLICATION_JSON)
public class IngestResource {

    @Inject PythonBridge bridge;

    @GET
    @Path("status")
    public Response status() {
        return BridgeResponse.of(bridge.call("bridge.ingest_status"));
    }

    @POST
    @Path("detect")
    public Response detect(String body) {
        return BridgeResponse.of(bridge.call("bridge.ingest_detect",
                                             body == null ? "{}" : body));
    }

    @POST
    @Path("discover")
    public Response discover(String body) {
        return BridgeResponse.of(bridge.call("bridge.ingest_discover",
                                             body == null ? "{}" : body));
    }

    @POST
    @Path("preview")
    public Response preview(String body) {
        return BridgeResponse.of(bridge.call("bridge.ingest_preview",
                                             body == null ? "{}" : body));
    }

    @POST
    @Path("run")
    public Response run(String body) {
        return BridgeResponse.of(bridge.call("bridge.ingest_run",
                                             body == null ? "{}" : body));
    }

    @POST
    @Path("cancel")
    public Response cancel() {
        return BridgeResponse.of(bridge.call("bridge.ingest_cancel"));
    }
}
