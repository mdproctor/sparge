package io.sparge.server;

import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import jakarta.enterprise.context.ApplicationScoped;
import jep.JepException;
import jep.SharedInterpreter;

import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;

/**
 * Single-thread Python bridge.
 *
 * JEP SharedInterpreter must be used exclusively from the thread that created it.
 * A dedicated daemon thread owns the interpreter for its entire lifetime.
 * HTTP threads submit tasks via a queue and block (with timeout) for the result.
 *
 * The timeout in call() prevents infinite hangs if Python blocks unexpectedly.
 */
@ApplicationScoped
public class PythonBridge {

    private record Task(String function, Object[] args, CompletableFuture<String> result) {}

    private final LinkedBlockingQueue<Task> queue = new LinkedBlockingQueue<>();
    private Thread                          pythonThread;
    private final String                    repoRootPath;

    public PythonBridge() {
        Path serverDir = Paths.get(System.getProperty("user.dir")).toAbsolutePath();
        this.repoRootPath = serverDir.getParent().toString();
    }

    @PostConstruct
    void init() {
        CompletableFuture<String> initDone = new CompletableFuture<>();
        pythonThread = new Thread(() -> runLoop(initDone), "python-bridge");
        pythonThread.setDaemon(true);
        pythonThread.start();

        try {
            // Block until Python is initialised (or fails)
            String result = initDone.get(60, TimeUnit.SECONDS);
            System.out.println("[PythonBridge] initialized: " + result);
        } catch (TimeoutException e) {
            throw new RuntimeException("PythonBridge init timed out after 60s");
        } catch (Exception e) {
            throw new RuntimeException("PythonBridge init failed: " + e.getMessage(), e);
        }
    }

    /** Entry point for the dedicated Python thread. */
    private void runLoop(CompletableFuture<String> initDone) {
        SharedInterpreter interp;
        try {
            interp = new SharedInterpreter();
            interp.exec("import sys");
            interp.set("_sparge_root", repoRootPath);
            interp.exec("sys.path.insert(0, _sparge_root)");
            interp.exec("import scripts.bridge as bridge");
            String initResult = (String) interp.invoke("bridge.bridge_init");
            initDone.complete(initResult);
        } catch (Exception e) {
            initDone.completeExceptionally(e);
            return;
        }

        // Process tasks from the queue on this thread for ever
        while (!Thread.currentThread().isInterrupted()) {
            Task task;
            try {
                task = queue.poll(5, TimeUnit.SECONDS);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                break;
            }
            if (task == null) continue;

            try {
                String result = (String) interp.invoke(task.function(), task.args());
                task.result().complete(result == null ? "{\"status\":200,\"body\":null}" : result);
            } catch (JepException e) {
                task.result().complete(errorJson(e.getMessage()));
            } catch (Exception e) {
                task.result().complete(errorJson(e.getMessage()));
            }
        }

        try { interp.close(); } catch (Exception ignored) {}
    }

    /**
     * Call a bridge function from any thread.
     * Submits to the Python thread and waits up to 30s for the result.
     * Returns an error JSON if the call times out or raises an exception.
     */
    public String call(String function, Object... args) {
        CompletableFuture<String> future = new CompletableFuture<>();
        queue.offer(new Task(function, args, future));
        try {
            return future.get(30, TimeUnit.SECONDS);
        } catch (TimeoutException e) {
            return errorJson("Python call timed out after 30s: " + function);
        } catch (Exception e) {
            return errorJson(e.getMessage());
        }
    }

    @PreDestroy
    void destroy() {
        if (pythonThread != null) {
            pythonThread.interrupt();
        }
    }

    private static String errorJson(String msg) {
        if (msg == null) msg = "unknown error";
        String escaped = msg.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n");
        return "{\"status\":500,\"body\":{\"error\":\"" + escaped + "\"}}";
    }
}
