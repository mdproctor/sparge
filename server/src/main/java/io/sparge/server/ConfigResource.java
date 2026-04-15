package io.sparge.server;

import jakarta.inject.Inject;
import jakarta.ws.rs.*;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;

@Path("/api/config")
@Produces(MediaType.APPLICATION_JSON)
@Consumes(MediaType.APPLICATION_JSON)
public class ConfigResource {

    @Inject PythonBridge bridge;

    @GET
    public Response get() {
        return BridgeResponse.of(bridge.call("bridge.config_get"));
    }

    @POST
    public Response post(String body) {
        return BridgeResponse.of(bridge.call("bridge.config_post",
                                             body == null ? "{}" : body));
    }
}
