package io.sparge.server;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * Thread-safe job state for the ingest pipeline.
 * Mirrors the Python _job dict + _job_lock in bridge.py.
 */
public class IngestJobState {

    private volatile boolean running   = false;
    private volatile int     done      = 0;
    private volatile int     total     = 0;
    private volatile String  current   = "";
    private volatile boolean cancelled = false;

    private final List<Map<String, Object>> errors = new ArrayList<>();
    private final List<Map<String, Object>> log    = new ArrayList<>();

    public synchronized void reset(int total) {
        this.running   = true;
        this.done      = 0;
        this.total     = total;
        this.current   = "";
        this.cancelled = false;
        this.errors.clear();
        this.log.clear();
    }

    public synchronized void incrementDone(String current) {
        this.done++;
        this.current = current;
    }

    public synchronized void setCurrent(String current) {
        this.current = current;
    }

    public synchronized void appendLog(Map<String, Object> entry) {
        log.add(entry);
    }

    public synchronized void appendError(Map<String, Object> entry) {
        errors.add(entry);
    }

    public synchronized void finish() {
        this.running = false;
        this.current = "";
    }

    public void cancel()           { this.cancelled = true; }
    public boolean isCancelled()   { return cancelled; }

    public synchronized Map<String, Object> snapshot() {
        return Map.of(
            "running",   running,
            "done",      done,
            "total",     total,
            "current",   current,
            "cancelled", cancelled,
            "errors",    List.copyOf(errors),
            "log",       List.copyOf(log)
        );
    }
}
