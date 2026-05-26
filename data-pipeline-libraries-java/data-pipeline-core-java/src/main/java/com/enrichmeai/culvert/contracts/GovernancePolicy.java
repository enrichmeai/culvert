package com.enrichmeai.culvert.contracts;

import com.enrichmeai.culvert.governance.DataClassification;
import com.enrichmeai.culvert.governance.MaskingPolicy;
import com.enrichmeai.culvert.governance.RetentionPolicy;

import java.util.Optional;

/**
 * Resolves what masking, retention, and classification apply to a given field
 * or table.
 *
 * <p>Implementations may consult Dataplex (GCP), Glue Data Catalog (AWS),
 * Purview (Azure), or a static YAML file shipped with the project. The
 * framework's default is a static-file policy (added in Stage 3) that runs
 * without any cloud service.
 *
 * <p>Java mirror of the Python {@code GovernancePolicy} Protocol.
 */
public interface GovernancePolicy {

    /**
     * Return the sensitivity classification of {@code field} in {@code table}.
     *
     * <p>Defaults to {@link DataClassification#INTERNAL} when no policy attaches
     * — never throws.
     */
    DataClassification classify(String field, String table);

    /**
     * Return the masking policy for {@code field} in {@code table}, or empty
     * if no masking applies.
     */
    Optional<MaskingPolicy> maskingFor(String field, String table);

    /**
     * Return the retention policy for {@code table}, or empty if no retention
     * policy applies (data kept indefinitely).
     */
    Optional<RetentionPolicy> retentionFor(String table);
}
