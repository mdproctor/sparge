package io.sparge.server;

import io.quarkus.test.junit.QuarkusTest;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIf;

import java.nio.file.Files;
import java.nio.file.Paths;

import static io.restassured.RestAssured.given;
import static org.hamcrest.Matchers.*;

/**
 * E2E test for POST /api/posts/{slug}/scan via @QuarkusTest.
 * Skipped when the KIE archive is not present.
 */
@QuarkusTest
class ScanEndpointTest {

    static boolean kieArchivePresent() {
        return Files.isDirectory(Paths.get(
                System.getProperty("user.home"),
                "mdproctor.github.io/legacy/posts/mark-proctor"));
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void scanEndpointReturns200WithPostState() {
        String slug = given()
                .when().get("/api/posts")
                .then().statusCode(200)
                .extract().jsonPath().getString("[0].slug");

        given()
                .when().post("/api/posts/" + slug + "/scan")
                .then()
                .statusCode(200)
                .body("slug", equalTo(slug))
                .body("html", notNullValue());
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void scanResponseContainsHtmlAndAssetsFields() {
        String slug = given()
                .when().get("/api/posts")
                .then().statusCode(200)
                .extract().jsonPath().getString("[0].slug");

        given()
                .when().post("/api/posts/" + slug + "/scan")
                .then()
                .statusCode(200)
                .body("slug",   equalTo(slug))
                .body("html",   notNullValue())
                .body("assets", notNullValue());
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void scanUnknownSlugReturns404() {
        given()
                .when().post("/api/posts/this-slug-does-not-exist-xyz/scan")
                .then()
                .statusCode(404);
    }
}
