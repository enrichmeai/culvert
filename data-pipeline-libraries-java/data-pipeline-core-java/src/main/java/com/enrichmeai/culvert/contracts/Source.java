package com.enrichmeai.culvert.contracts;

import java.util.Iterator;

/**
 * Anything that yields records into the pipeline.
 *
 * <p>Stateless from the caller's perspective. Implementations may be backed
 * by a file, a queue, a table, an API. The {@code context} carries run
 * metadata, cost tags, and the lookup table for cloud-pluggable services.
 *
 * <p>Java mirror of the Python {@code Source[T]} Protocol. Java doesn't
 * have declaration-site variance, so {@code T} is invariant here; consumers
 * use wildcards ({@code Source<? extends T>}) at the use site if they need
 * covariance.
 *
 * @param <T> The record type yielded.
 */
@FunctionalInterface
public interface Source<T> {

    /**
     * Stream records into the pipeline.
     *
     * @param context The runtime context for this stage.
     * @return An iterator over records. Must be lazy — implementations
     *         must not materialise the full result in memory.
     */
    Iterator<T> read(RuntimeContext context);
}
