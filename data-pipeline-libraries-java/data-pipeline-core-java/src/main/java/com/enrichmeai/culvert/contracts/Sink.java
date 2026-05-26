package com.enrichmeai.culvert.contracts;

import java.util.Iterator;

/**
 * Anything that consumes records out of the pipeline.
 *
 * <p>The framework guarantees ordering only within a single Sink invocation;
 * cross-sink ordering is the caller's responsibility.
 *
 * <p>Java mirror of the Python {@code Sink[U]} Protocol.
 *
 * @param <U> The record type consumed.
 */
@FunctionalInterface
public interface Sink<U> {

    /**
     * Write records to the underlying destination.
     *
     * @param records The records to write. May be a long-running stream;
     *                implementations should write incrementally.
     * @param context The runtime context for this stage.
     */
    void write(Iterator<U> records, RuntimeContext context);
}
