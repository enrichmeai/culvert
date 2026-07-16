package com.enrichmeai.culvert.deployments.ingestion;

/**
 * Outcome of comparing the HDR/TRL envelope's declared record count against
 * the number of rows actually loaded into BigQuery.
 *
 * <p>Ports the retired Python reference's
 * {@code ReconciliationEngine.reconcile_with_bigquery} concept (predecessor
 * tree, removed 2026-07 — see git history); this record is the Java-side
 * equivalent shape (expected vs. actual counts, reconciled flag).
 *
 * @param expectedCount Declared count from the TRL trailer (row count only —
 *                       excludes any CSV header row).
 * @param actualCount   Rows reported loaded by {@link com.enrichmeai.culvert.contracts.Warehouse#loadFromUri}.
 */
public record ReconciliationResult(long expectedCount, long actualCount) {

    public boolean isReconciled() {
        return expectedCount == actualCount;
    }

    public long difference() {
        return actualCount - expectedCount;
    }
}
