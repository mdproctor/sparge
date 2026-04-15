package io.sparge.server;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Mirrors tests/test_sparge_home.py — four behaviours for SpargeHome.getProjectsDir().
 */
class SpargeHomeTest {

    @Test
    void defaultsToSpargeProjectsWhenNoConfig(@TempDir Path home) throws IOException {
        SpargeHome spargeHome = new SpargeHome(home);
        Path result = spargeHome.getProjectsDir();
        assertEquals(home.resolve("sparge-projects"), result);
    }

    @Test
    void readsProjectsDirFromConfig(@TempDir Path home) throws IOException {
        Path custom = home.resolve("my-projects");
        Path spargeDir = home.resolve(".sparge");
        Files.createDirectories(spargeDir);
        Files.writeString(spargeDir.resolve("config.json"),
                "{\"projects_dir\": \"" + custom + "\"}");

        SpargeHome spargeHome = new SpargeHome(home);
        assertEquals(custom, spargeHome.getProjectsDir());
    }

    @Test
    void expandsTildeInProjectsDir(@TempDir Path home) throws IOException {
        Path spargeDir = home.resolve(".sparge");
        Files.createDirectories(spargeDir);
        Files.writeString(spargeDir.resolve("config.json"),
                "{\"projects_dir\": \"~/custom-projects\"}");

        SpargeHome spargeHome = new SpargeHome(home);
        assertEquals(home.resolve("custom-projects"), spargeHome.getProjectsDir());
    }

    @Test
    void createsSpargeConfigWithDefaultsOnFirstCall(@TempDir Path home) throws IOException {
        SpargeHome spargeHome = new SpargeHome(home);
        spargeHome.getProjectsDir();

        Path cfgPath = home.resolve(".sparge").resolve("config.json");
        assertTrue(Files.exists(cfgPath), "~/.sparge/config.json should be created");
        String content = Files.readString(cfgPath);
        assertTrue(content.contains("projects_dir"), "config.json must contain projects_dir key");
    }
}
