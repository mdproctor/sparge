package io.sparge.server;

import io.quarkus.test.junit.QuarkusTest;
import org.junit.jupiter.api.Test;

import static io.restassured.RestAssured.given;
import static org.hamcrest.Matchers.*;

@QuarkusTest
class IngestResourceTest {

    @Test
    void statusReturns200WithAllJobFields() {
        given()
                .when().get("/api/ingest/status")
                .then()
                .statusCode(200)
                .body("running",   notNullValue())
                .body("done",      notNullValue())
                .body("total",     notNullValue())
                .body("cancelled", notNullValue())
                .body("errors",    notNullValue())
                .body("log",       notNullValue());
    }

    @Test
    void statusInitiallyNotRunning() {
        given().when().get("/api/ingest/status").then()
                .statusCode(200).body("running", equalTo(false));
    }

    @Test
    void cancelReturns200WithCancelledTrue() {
        given().contentType("application/json")
                .when().post("/api/ingest/cancel").then()
                .statusCode(200).body("cancelled", equalTo(true));
    }

    @Test
    void detectMissingUrl_returns400() {
        given().contentType("application/json").body("{}")
                .when().post("/api/ingest/detect").then().statusCode(400);
    }

    @Test
    void discoverMissingUrl_returns400() {
        given().contentType("application/json").body("{}")
                .when().post("/api/ingest/discover").then().statusCode(400);
    }

    @Test
    void previewMissingUrl_returns400() {
        given().contentType("application/json").body("{}")
                .when().post("/api/ingest/preview").then().statusCode(400);
    }

    @Test
    void runEmptyUrls_returns400() {
        given().contentType("application/json").body("{\"urls\":[]}")
                .when().post("/api/ingest/run").then().statusCode(400);
    }
}
