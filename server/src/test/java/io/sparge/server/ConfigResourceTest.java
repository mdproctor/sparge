package io.sparge.server;

import io.quarkus.test.junit.QuarkusTest;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIf;

import java.nio.file.Files;
import java.nio.file.Paths;

import static io.restassured.RestAssured.given;
import static org.hamcrest.Matchers.*;

@QuarkusTest
class ConfigResourceTest {

    static boolean kieArchivePresent() {
        return Files.isDirectory(Paths.get(
                System.getProperty("user.home"),
                "mdproctor.github.io/legacy/posts/mark-proctor"));
    }

    @AfterEach
    void cleanupTestKey() {
        if (!kieArchivePresent()) return;
        // Remove the synthetic test key if it was written
        try {
            String current = given()
                    .when().get("/api/config")
                    .then().statusCode(200)
                    .extract().response().asString();
            com.fasterxml.jackson.databind.ObjectMapper mapper = new com.fasterxml.jackson.databind.ObjectMapper();
            com.fasterxml.jackson.databind.node.ObjectNode node =
                    (com.fasterxml.jackson.databind.node.ObjectNode) mapper.readTree(current);
            node.remove("_test_roundtrip");
            given()
                    .contentType("application/json")
                    .body(mapper.writeValueAsString(node))
                    .when().post("/api/config")
                    .then().statusCode(200);
        } catch (Exception ignored) {}
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
    void getConfigReturns200WithProjectName() {
        given()
                .when().get("/api/config")
                .then()
                .statusCode(200)
                .body("project_name", notNullValue());
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void getConfigDoesNotExposeInternalUnderscoreKeys() {
        given()
                .when().get("/api/config")
                .then()
                .statusCode(200)
                .body("_posts_dir", nullValue())
                .body("_md_dir",    nullValue());
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void postConfigSavesAndReturnsSavedTrue() {
        // Read current config, POST it back unchanged — a safe no-op
        String current = given()
                .when().get("/api/config")
                .then().statusCode(200)
                .extract().response().asString();

        given()
                .contentType("application/json")
                .body(current)
                .when().post("/api/config")
                .then()
                .statusCode(200)
                .body("saved", equalTo(true));
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void postConfigInvalidJsonReturns400() {
        given()
                .contentType("application/json")
                .body("not valid json }{")
                .when().post("/api/config")
                .then()
                .statusCode(400);
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void getAfterPostReflectsUpdate() {
        // Post a harmless synthetic field, then read it back
        given()
                .contentType("application/json")
                .body("{\"_test_roundtrip\": \"phase6a\"}")
                .when().post("/api/config")
                .then().statusCode(200);

        given()
                .when().get("/api/config")
                .then()
                .statusCode(200)
                .body("_test_roundtrip", equalTo("phase6a"));
    }
}
