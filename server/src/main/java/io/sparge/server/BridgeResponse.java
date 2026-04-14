package io.sparge.server;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.ws.rs.core.Response;

public final class BridgeResponse {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    private BridgeResponse() {}

    /**
     * Parse bridge JSON and produce the appropriate JAX-RS Response.
     *
     * bridge returns one of:
     *   {"status":int, "body": jsonValue}                                → application/json
     *   {"status":int, "content_type":"text/plain", "body":"string"}    → text/plain
     *   {"status":int, "content_type":"text/html",  "body":"string"}    → text/html
     */
    public static Response of(String bridgeJson) {
        try {
            JsonNode node = MAPPER.readTree(bridgeJson);
            int    status      = node.get("status").asInt();
            String contentType = node.has("content_type")
                ? node.get("content_type").asText() + "; charset=utf-8"
                : "application/json; charset=utf-8";

            JsonNode bodyNode = node.get("body");
            String   body     = bodyNode.isTextual()
                ? bodyNode.asText()       // text/plain or text/html — return raw string
                : bodyNode.toString();    // JSON — serialize back

            return Response.status(status)
                .header("Content-Type",                contentType)
                .header("Access-Control-Allow-Origin", "*")
                .entity(body)
                .build();
        } catch (Exception e) {
            return Response.serverError()
                .header("Content-Type", "application/json")
                .entity("{\"error\":\"bridge parse error: " + e.getMessage() + "\"}")
                .build();
        }
    }
}
