package io.sparge.server;

import jakarta.inject.Inject;
import jakarta.ws.rs.*;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;

@Path("/api/search")
@Produces(MediaType.APPLICATION_JSON)
public class SearchResource {

    @Inject PythonBridge bridge;

    @GET
    public Response search(@QueryParam("q")     @DefaultValue("") String q,
                           @QueryParam("scope") @DefaultValue("both") String scope) {
        return BridgeResponse.of(bridge.call("bridge.search", q, scope));
    }
}
