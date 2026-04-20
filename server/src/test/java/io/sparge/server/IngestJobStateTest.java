package io.sparge.server;

import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

import static org.junit.jupiter.api.Assertions.*;

class IngestJobStateTest {

    @Test
    void initialState_notRunning() {
        IngestJobState s = new IngestJobState();
        Map<String, Object> snap = s.snapshot();
        assertFalse((Boolean) snap.get("running"));
        assertEquals(0, snap.get("done"));
        assertEquals(0, snap.get("total"));
        assertEquals("", snap.get("current"));
        assertFalse((Boolean) snap.get("cancelled"));
        assertTrue(((List<?>) snap.get("errors")).isEmpty());
        assertTrue(((List<?>) snap.get("log")).isEmpty());
    }

    @Test
    void reset_setsRunningAndTotal() {
        IngestJobState s = new IngestJobState();
        s.reset(42);
        Map<String, Object> snap = s.snapshot();
        assertTrue((Boolean) snap.get("running"));
        assertEquals(42, snap.get("total"));
        assertEquals(0, snap.get("done"));
    }

    @Test
    void cancel_setsCancelledFlag() {
        IngestJobState s = new IngestJobState();
        s.reset(10);
        assertFalse(s.isCancelled());
        s.cancel();
        assertTrue(s.isCancelled());
        assertTrue((Boolean) s.snapshot().get("cancelled"));
    }

    @Test
    void finish_setsRunningFalse() {
        IngestJobState s = new IngestJobState();
        s.reset(5);
        s.finish();
        assertFalse((Boolean) s.snapshot().get("running"));
    }

    @Test
    void appendLog_recordsEntries() {
        IngestJobState s = new IngestJobState();
        s.reset(2);
        s.appendLog(Map.of("url", "https://a.com", "slug", "a", "ok", true));
        s.appendLog(Map.of("url", "https://b.com", "slug", "b", "ok", false));
        List<?> log = (List<?>) s.snapshot().get("log");
        assertEquals(2, log.size());
    }

    @Test
    void appendError_recordsEntries() {
        IngestJobState s = new IngestJobState();
        s.reset(1);
        s.appendError(Map.of("url", "https://bad.com", "error", "timeout"));
        List<?> errors = (List<?>) s.snapshot().get("errors");
        assertEquals(1, errors.size());
    }

    @Test
    void reset_clearsPreviousState() {
        IngestJobState s = new IngestJobState();
        s.reset(5);
        s.appendLog(Map.of("url", "u", "slug", "sl", "ok", true));
        s.cancel();
        s.reset(3);
        Map<String, Object> snap = s.snapshot();
        assertTrue(((List<?>) snap.get("log")).isEmpty());
        assertFalse((Boolean) snap.get("cancelled"));
        assertEquals(3, snap.get("total"));
    }

    @Test
    void snapshot_returnsCopies_notLiveReferences() {
        IngestJobState s = new IngestJobState();
        s.reset(1);
        s.appendLog(Map.of("url", "u", "slug", "sl", "ok", true));
        List<?> logSnapshot = (List<?>) s.snapshot().get("log");
        s.appendLog(Map.of("url", "v", "slug", "sl2", "ok", true));
        assertEquals(1, logSnapshot.size(), "Snapshot should be independent of further mutations");
    }

    @Test
    void threadSafety_concurrentAppends_noDataLoss() throws Exception {
        IngestJobState s = new IngestJobState();
        s.reset(100);
        int threads = 10;
        CountDownLatch latch = new CountDownLatch(threads);
        ExecutorService pool = Executors.newFixedThreadPool(threads);
        for (int i = 0; i < threads; i++) {
            final int idx = i;
            pool.submit(() -> {
                for (int j = 0; j < 10; j++)
                    s.appendLog(Map.of("url", "u" + idx + "_" + j, "slug", "s", "ok", true));
                latch.countDown();
            });
        }
        latch.await();
        pool.shutdown();
        assertEquals(100, ((List<?>) s.snapshot().get("log")).size(),
                "All 100 entries should be recorded");
    }
}
