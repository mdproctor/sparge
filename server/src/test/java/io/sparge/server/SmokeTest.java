package io.sparge.server;

import io.quarkus.test.junit.QuarkusTest;
import org.junit.jupiter.api.Test;

import static io.restassured.RestAssured.given;
import static org.hamcrest.Matchers.notNullValue;

@QuarkusTest
class SmokeTest {

    @Test
    void configEndpointReturns200() {
        given()
            .when().get("/api/config")
            .then()
            .statusCode(200)
            .body("project_name", notNullValue());
    }
}
