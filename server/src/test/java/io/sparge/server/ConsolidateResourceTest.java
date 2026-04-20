package io.sparge.server;

import io.quarkus.test.junit.QuarkusTest;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIf;

import java.nio.file.Files;
import java.nio.file.Paths;

import static io.restassured.RestAssured.given;
import static org.hamcrest.Matchers.*;
import static org.junit.jupiter.api.Assertions.assertEquals;

@QuarkusTest
class ConsolidateResourceTest {

    static boolean kieArchivePresent() {
        return Files.isDirectory(Paths.get(
                System.getProperty("user.home"),
                "mdproctor.github.io/legacy/posts/mark-proctor"));
    }

    @BeforeEach
    void activateProject() {
        if (!kieArchivePresent()) return;
        try {
            String id = given()
                    .when().get("/api/projects")
                    .then().statusCode(200)
                    .extract().jsonPath().getString("[0].id");
            if (id != null && !id.isEmpty()) {
                given().contentType("application/json")
                        .when().post("/api/projects/{id}/activate", id)
                        .then().statusCode(200);
            }
        } catch (Exception e) {
            System.err.println("Warning: project activation failed: " + e.getMessage());
        }
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void consolidateReturns200WithExpectedFields() {
        given()
                .when().post("/api/consolidate")
                .then()
                .statusCode(200)
                .body("promoted",     notNullValue())
                .body("updated_html", notNullValue())
                .body("duplicates",   notNullValue());
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void consolidateIsIdempotent() {
        // First run may or may not promote files
        given().when().post("/api/consolidate").then().statusCode(200);

        // Second run must find zero new duplicates (already consolidated)
        int promoted = given()
                .when().post("/api/consolidate")
                .then()
                .statusCode(200)
                .extract().jsonPath().getInt("promoted");

        assertEquals(0, promoted, "Second consolidation run should find no new duplicates");
    }
}
