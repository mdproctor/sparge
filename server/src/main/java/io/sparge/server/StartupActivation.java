package io.sparge.server;

import com.fasterxml.jackson.databind.node.ObjectNode;
import io.quarkus.runtime.StartupEvent;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.event.Observes;
import jakarta.inject.Inject;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

/**
 * Mirrors Python's bridge_init() auto-activation: on startup, load the first project
 * from projects.json and populate ActiveProject so native resources work immediately.
 *
 * This runs after PythonBridge @PostConstruct completes (StartupEvent fires after all
 * @PostConstruct beans are ready), so the ordering is safe.
 */
@ApplicationScoped
public class StartupActivation {

    @Inject ProjectsStore store;
    @Inject ActiveProject activeProject;

    void onStart(@Observes StartupEvent event) {
        try {
            List<ObjectNode> projects = store.load();
            if (projects.isEmpty()) return;
            String id         = projects.get(0).path("id").asText();
            Path   projectDir = store.getProjectDir(id);
            Path   configPath = projectDir.resolve("config.json");
            if (Files.exists(configPath)) {
                activeProject.set(id, SpargeConfig.load(configPath, projectDir), projectDir);
            }
        } catch (Exception e) {
            // Non-fatal — server works without an active project, UI prompts user to activate one
        }
    }
}
