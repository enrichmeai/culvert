package com.enrichmeai.culvert.contracts;

import com.enrichmeai.culvert.finops.CostMetrics;
import com.enrichmeai.culvert.finops.FinOpsTag;

/**
 * Receives {@link CostMetrics} from cloud-specific cost trackers and writes
 * them wherever the team aggregates them (BigQuery, Athena, Synapse).
 *
 * <p>{@code FinOpsTag} is passed explicitly rather than read from the runtime
 * context. Cost emissions are infrequent and lossy attribution is the most
 * common bug; explicit tags make the data flow visible.
 *
 * <p>Java mirror of the Python {@code FinOpsSink} Protocol.
 */
@FunctionalInterface
public interface FinOpsSink {

    /**
     * Record cost metrics with attribution tags.
     *
     * <p>Implementations may batch internally; the framework calls this once
     * per cost-incurring operation (a BigQuery query, a GCS upload, a Pub/Sub
     * publish) and the sink decides when to flush.
     */
    void record(CostMetrics metrics, FinOpsTag tags);
}
