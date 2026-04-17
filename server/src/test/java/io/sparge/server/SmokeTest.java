package io.sparge.server;

import io.quarkus.test.junit.QuarkusTest;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIf;

import java.nio.file.Files;
import java.nio.file.Paths;

import static io.restassured.RestAssured.given;
import static org.hamcrest.Matchers.notNullValue;

@QuarkusTest
class SmokeTest {

    static boolean kieArchivePresent() {
        return Files.isDirectory(Paths.get(
                System.getProperty("user.home"),
                "mdproctor.github.io/legacy/posts/mark-proctor"));
    }

    @BeforeEach
    void activateProject() {
        if (!kieArchivePresent()) return;
        String id = given()
                .when().get("/api/projects")
                .then().statusCode(200)
                .extract().jsonPath().getString("[0].id");
        if (id != null && !id.isEmpty()) {
            given().contentType("application/json")
                    .when().post("/api/projects/{id}/activate", id)
                    .then().statusCode(200);
        }
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void configEndpointReturns200() {
        given()
            .when().get("/api/config")
            .then()
            .statusCode(200)
            .body("project_name", notNullValue());
    }
}
