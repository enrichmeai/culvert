package com.enrichmeai.culvert.contracts;

import java.util.Iterator;

/**
 * Anything that maps records V to records W.
 *
 * <p>Pure where possible; side effects must be declared via the {@code Governed}
 * annotation (Stage 3 Java) so the runtime can track them.
 *
 * <p>Java mirror of the Python {@code Transform[V, W]} Protocol.
 *
 * @param <V> The input record type.
 * @param <W> The output record type.
 */
@FunctionalInterface
public interface Transform<V, W> {

    /**
     * Map an input stream to an output stream.
     *
     * @param records The input records.
     * @param context The runtime context for this stage.
     * @return The mapped records. Must be lazy.
     */
    Iterator<W> apply(Iterator<V> records, RuntimeContext context);
}
