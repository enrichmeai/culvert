package com.enrichmeai.culvert.contracts;

import com.enrichmeai.culvert.audit.AuditRecord;

/**
 * Publishes audit records.
 *
 * <p>Implementations may batch internally for throughput, but must guarantee
 * at-least-once delivery within a single {@code runId} boundary. {@link #flush()}
 * blocks until all buffered records have been acknowledged by the backing
 * event bus.
 *
 * <p>Java mirror of the Python {@code AuditEventPublisher} Protocol.
 */
public interface AuditEventPublisher {

    /** Publish a single audit record. May buffer. */
    void publish(AuditRecord record);

    /**
     * Block until all buffered records have been acknowledged.
     *
     * <p>Called at pipeline-stage boundaries and at shutdown. Idempotent —
     * calling {@code flush()} on an empty buffer is a no-op.
     */
    void flush();
}
