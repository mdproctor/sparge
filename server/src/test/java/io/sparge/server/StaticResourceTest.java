package io.sparge.server;

import io.quarkus.test.junit.QuarkusTest;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIf;

import java.nio.file.Files;
import java.nio.file.Paths;

import static io.restassured.RestAssured.given;
import static org.hamcrest.Matchers.*;

@QuarkusTest
class StaticResourceTest {

    static boolean kieArchivePresent() {
        return Files.isDirectory(Paths.get(
                System.getProperty("user.home"),
                "mdproctor.github.io/legacy/posts/mark-proctor"));
    }

    @BeforeEach
    void activateProject() {
        if (!kieArchivePresent()) return;
        // StartupActivation already activated the first project; this is a safety-net re-confirm.
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
            System.err.println("Warning: explicit project activation failed: " + e.getMessage());
        }
    }

    @Test
    void rootRedirectsToProjectsHtml() {
        given()
                .redirects().follow(false)
                .when().get("/")
                .then()
                .statusCode(anyOf(is(301), is(302), is(307), is(308)))
                .header("Location", containsString("projects.html"));
    }

    @Test
    void uiProjectsHtmlIsServed() {
        given()
                .when().get("/ui/projects.html")
                .then()
                .statusCode(200)
                .contentType(containsString("text/html"));
    }

    @Test
    void unknownStaticPathReturns404() {
        given()
                .when().get("/xyzzy-this-path-does-not-exist/file.txt")
                .then()
                .statusCode(404);
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void pathTraversalAttemptReturns403OrNot200() {
        // Traversal attempts must not serve files outside serve root
        given()
                .when().get("/../../etc/passwd")
                .then()
                .statusCode(not(equalTo(200)));
    }

    @Test
    @EnabledIf("kieArchivePresent")
    void knownLegacyAssetIsServed() {
        // A real HTML post file known to exist in the KIE archive
        String slug = given()
                .when().get("/api/posts")
                .then().statusCode(200)
                .extract().jsonPath().getString("[0].slug");

        given()
                .when().get("/legacy/posts/mark-proctor/" + slug + ".html")
                .then()
                .statusCode(200)
                .contentType(containsString("text/html"));
    }
}
