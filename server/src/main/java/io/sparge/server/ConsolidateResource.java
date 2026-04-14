package io.sparge.server;

import jakarta.inject.Inject;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;

@Path("/api/consolidate")
@Produces(MediaType.APPLICATION_JSON)
public class ConsolidateResource {

    @Inject PythonBridge bridge;

    @POST
    public Response consolidate() {
        return BridgeResponse.of(bridge.call("bridge.consolidate"));
    }
}
