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

    public String getProjectId() { return projectId; }

    public SpargeConfig.ResolvedConfig getConfig() { return config; }

    public boolean isActive() { return projectId != null; }

    public synchronized void set(String projectId, SpargeConfig.ResolvedConfig config) {
        this.projectId = projectId;
        this.config    = config;
    }
}
