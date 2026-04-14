package io.sparge.server;

import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import jakarta.enterprise.context.ApplicationScoped;
import jep.JepException;
import jep.SharedInterpreter;

import java.nio.file.Path;
import java.nio.file.Paths;

@ApplicationScoped
public class PythonBridge {

    private SharedInterpreter interp;
    private final String repoRootPath;

    public PythonBridge() {
        // When running from server/, parent is the repo root (sparge/)
        Path serverDir = Paths.get(System.getProperty("user.dir")).toAbsolutePath();
        Path repoRoot  = serverDir.getParent();
        this.repoRootPath = repoRoot.toString();
    }

    @PostConstruct
    void init() {
        try {
            interp = new SharedInterpreter();
            interp.exec("import sys");
            // Use set() to pass path safely — avoids Python string escaping issues
            interp.set("_sparge_root", repoRootPath);
            interp.exec("sys.path.insert(0, _sparge_root)");
            interp.exec("import scripts.bridge as bridge");
            String result = (String) interp.invoke("bridge.bridge_init");
            System.out.println("[PythonBridge] initialized: " + result);
        } catch (JepException e) {
            throw new RuntimeException("PythonBridge init failed: " + e.getMessage(), e);
        }
    }

    @PreDestroy
    void destroy() {
        if (interp != null) {
            try { interp.close(); } catch (JepException ignored) {}
        }
    }

    /**
     * Call a bridge function with arguments, return raw JSON string.
     * Synchronized: all Python calls serialized (respects GIL and mutable global state).
     */
    public synchronized String call(String function, Object... args) {
        try {
            return (String) interp.invoke(function, args);
        } catch (JepException e) {
            String msg = e.getMessage() == null ? "JEP error" : e.getMessage()
                .replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n");
            return "{\"status\":500,\"body\":{\"error\":\"" + msg + "\"}}";
        }
    }

}
