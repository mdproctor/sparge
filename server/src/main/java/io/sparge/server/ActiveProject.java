package io.sparge.server;

import jakarta.enterprise.context.ApplicationScoped;

/**
 * CDI singleton tracking which project is currently active.
 * Set by ProjectsResource.activate() after Python confirms the switch.
 */
@ApplicationScoped
public class ActiveProject {

    private volatile String projectId;
    private volatile SpargeConfig.ResolvedConfig config;
    private volatile java.nio.file.Path projectDir;

    public String getProjectId() { return projectId; }

    public SpargeConfig.ResolvedConfig getConfig() { return config; }

    public java.nio.file.Path getProjectDir() { return projectDir; }

    public boolean isActive() { return projectId != null; }

    public synchronized void set(String projectId,
                                  SpargeConfig.ResolvedConfig config,
                                  java.nio.file.Path projectDir) {
        this.projectId  = projectId;
        this.config     = config;
        this.projectDir = projectDir;
    }
}
