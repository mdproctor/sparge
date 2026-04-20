package io.sparge.server;

import jakarta.annotation.PostConstruct;
import jakarta.enterprise.context.ApplicationScoped;

/**
 * Python bridge stub — JEP dependency removed.
 * This class is dead code pending deletion in a follow-up cleanup commit.
 * No endpoints inject it any longer.
 */
@ApplicationScoped
public class PythonBridge {

    public PythonBridge() {}

    @PostConstruct
    void init() {
        // Stub — JEP removed; PythonBridge is dead code pending deletion.
    }

    /**
     * Stub call method — always returns an error. Never invoked in normal operation.
     */
    public String call(String function, Object... args) {
        return "{\"status\":500,\"body\":{\"error\":\"PythonBridge disabled — JEP removed\"}}";
    }
}
