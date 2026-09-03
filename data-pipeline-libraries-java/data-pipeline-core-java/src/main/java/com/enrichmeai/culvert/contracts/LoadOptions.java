package com.enrichmeai.culvert.contracts;

import java.util.Objects;
import java.util.Optional;

/**
 * How a {@link Warehouse#loadFromUri} call should write into its target.
 *
 * <h2>Why this type exists</h2>
 * <p>Before it, {@code loadFromUri(uri, targetTable, schema)} carried no way to
 * say what should happen to data already in the target, so every backend was
 * free to pick — and picked differently. {@code BigQueryWarehouse} built a
 * {@code LoadJobConfiguration} with only a schema and a format, which means
 * BigQuery applied its own default of {@code WRITE_APPEND}: re-running the same
 * extract silently doubled the data, with nothing in the contract, the call
 * site, or the job-control record to indicate it had happened.
 *
 * <p>The fix is deliberately <strong>not</strong> a defaulted parameter or a
 * three-argument convenience overload. A default is exactly what caused the
 * bug: it lets a caller write an idempotency-critical load without ever
 * deciding what "re-run" means. Disposition is therefore required at every call
 * site, and choosing it is a visible act.
 *
 * <h2>On {@code targetPartition}</h2>
 * <p>{@link #targetPartition()} names a single partition to confine the write
 * to, so {@link WriteDisposition#TRUNCATE} can mean "replace just this
 * partition" rather than "replace the whole table". It is an opaque,
 * backend-parsed string for the same reason {@code fqtn} is
 * ({@code Warehouse} Javadoc): BigQuery spells it {@code 20260601} (a partition
 * decorator), other warehouses spell it differently.
 *
 * <p><strong>Honest limitation.</strong> Partition-scoped replace only helps
 * when the table is partitioned by the column that identifies a load — usually
 * an extract or ingestion date. A table partitioned on a <em>business</em> date
 * cannot express "replace this extract" as a partition operation at all,
 * because one extract spans many business dates. The Culvert reference ODP
 * tables are exactly this case: {@code odp_generic.customers} is partitioned on
 * {@code created_date} and {@code odp_generic.accounts} on {@code open_date}
 * (see {@code scripts/gcp/03_create_infrastructure.sh:117-129}), so they
 * achieve idempotency by deleting the extract's rows before appending, not by
 * partition replace. Pick the mechanism that matches the table, and do not
 * assume {@code TRUNCATE} + {@code targetPartition} is always available.
 *
 * <p>Java mirror of the Python {@code LoadOptions} dataclass
 * ({@code data-pipeline-libraries/data-pipeline-core/src/data_pipeline_core/contracts/warehouse.py}).
 *
 * @param writeDisposition What happens to rows already in the target. Required.
 * @param targetPartition  Partition to confine the write to, or empty for the
 *                         whole table.
 */
public record LoadOptions(WriteDisposition writeDisposition, Optional<String> targetPartition) {

    /** What a load does to data already present in the target. */
    public enum WriteDisposition {

        /**
         * Add rows, keeping everything already there.
         *
         * <p>Not idempotent: loading the same source twice yields two copies.
         * Correct for genuinely additive feeds (append-only event streams);
         * wrong for re-runnable batch extracts, which is the case that made
         * this enum necessary.
         */
        APPEND,

        /**
         * Replace the target's existing rows with the loaded ones.
         *
         * <p>Scoped to {@link LoadOptions#targetPartition()} when one is given,
         * and to the whole table when one is not — so a {@code TRUNCATE}
         * without a partition on a multi-extract table destroys the other
         * extracts. Implementations must not silently narrow this.
         */
        TRUNCATE,

        /**
         * Load only into an empty target; fail rather than write otherwise.
         *
         * <p>The safest option when a load is expected to happen exactly once
         * and a second attempt indicates a bug upstream.
         */
        ERROR_IF_EXISTS
    }

    public LoadOptions {
        Objects.requireNonNull(writeDisposition, "writeDisposition must not be null");
        Objects.requireNonNull(targetPartition, "targetPartition must not be null (use Optional.empty())");
        if (targetPartition.isPresent() && targetPartition.get().isBlank()) {
            throw new IllegalArgumentException("targetPartition must not be blank when present");
        }
    }

    /** Add rows, keeping what is already there. See {@link WriteDisposition#APPEND}. */
    public static LoadOptions append() {
        return new LoadOptions(WriteDisposition.APPEND, Optional.empty());
    }

    /** Replace the whole target table. See {@link WriteDisposition#TRUNCATE}. */
    public static LoadOptions truncate() {
        return new LoadOptions(WriteDisposition.TRUNCATE, Optional.empty());
    }

    /**
     * Replace only {@code partitionId} within the target.
     *
     * @param partitionId Backend-specific partition identifier — for BigQuery,
     *                    a partition decorator such as {@code 20260601}.
     */
    public static LoadOptions truncatePartition(String partitionId) {
        Objects.requireNonNull(partitionId, "partitionId must not be null");
        return new LoadOptions(WriteDisposition.TRUNCATE, Optional.of(partitionId));
    }

    /** Load only into an empty target. See {@link WriteDisposition#ERROR_IF_EXISTS}. */
    public static LoadOptions errorIfExists() {
        return new LoadOptions(WriteDisposition.ERROR_IF_EXISTS, Optional.empty());
    }
}
