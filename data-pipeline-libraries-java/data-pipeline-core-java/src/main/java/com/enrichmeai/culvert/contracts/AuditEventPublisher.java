package com.enrichmeai.culvert.contracts;

import com.enrichmeai.culvert.audit.AuditEvent;

/**
 * Publishes audit events ({@code docs/CONTRACT.md} §4).
 *
 * <p>Implementations may batch internally for throughput, but must guarantee
 * at-least-once delivery within a single {@code runId} boundary. {@link #flush()}
 * blocks until all buffered events have been acknowledged by the backing
 * event bus.
 *
 * <h2>A failed publish is never silent</h2>
 * <p>How it fails depends on what was being published, and the event itself
 * says which — {@link AuditEvent#failureIsFatal()}:
 * <ul>
 *   <li><strong>Run-level</strong> ({@code RUN_START}, {@code RUN_END},
 *       {@code ERROR_RAISED}, {@code RECONCILIATION}, {@code RETRY_ATTEMPTED})
 *       — the publish <strong>throws</strong>. These events <em>are</em> the
 *       run's state; continuing without one is how a pipeline reports success
 *       it never had.</li>
 *   <li><strong>Aggregate</strong> ({@code RECORD_VALIDATED},
 *       {@code RECORD_REJECTED}) — log at ERROR and continue, so an audit
 *       hiccup over a counter cannot halt ingestion.</li>
 * </ul>
 *
 * <p>Implementations <strong>must not</strong> catch-and-continue on a
 * run-level event. The previous implementation logged every failure at WARN and
 * swallowed it, so an audit trail that had never once written looked healthy
 * for months.
 *
 * <p>Java mirror of the Python {@code AuditEventPublisher} Protocol.
 */
public interface AuditEventPublisher {

    /**
     * Publish a single audit event. May buffer.
     *
     * @throws RuntimeException if the event is run-level and the write failed.
     *                          Aggregate events log and return instead.
     */
    void publish(AuditEvent event);

    /**
     * Block until all buffered records have been acknowledged.
     *
     * <p>Called at pipeline-stage boundaries and at shutdown. Idempotent —
     * calling {@code flush()} on an empty buffer is a no-op.
     */
    void flush();
}
