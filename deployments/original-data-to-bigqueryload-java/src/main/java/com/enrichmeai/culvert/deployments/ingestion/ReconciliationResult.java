package com.enrichmeai.culvert.deployments.ingestion;

/**
 * Outcome of comparing the HDR/TRL envelope's declared record count against
 * what the run actually did with those records.
 *
 * <p>Ports the retired Python reference's
 * {@code ReconciliationEngine.reconcile_with_bigquery} concept (predecessor
 * tree, removed 2026-07 — see git history).
 *
 * <h2>Accounting, not just loading</h2>
 * <p>{@code accountedCount} is deliberately not "rows loaded". A record that
 * failed validation and was written to the quarantine bucket is
 * <em>accounted for</em> — it did not vanish, and an operator can go and read
 * it. Counting only loaded rows would make every quarantined row a
 * reconciliation failure, which would in turn make the whole quarantine path
 * pointless: the pipeline would abort precisely when it used the mechanism
 * built for not aborting.
 *
 * <p>So the rule is <strong>declared == loaded + quarantined</strong>. A
 * mismatch then means what it should mean: records went missing without
 * landing anywhere, which is worth failing a run over.
 *
 * <p>This is used for two distinct checks in {@link IngestionRunner}, and they
 * catch different faults — see that class's Javadoc:
 * <ol>
 *   <li><strong>Accounting</strong>, before anything is written to the target:
 *       does the file's declared count match what we parsed out of it?</li>
 *   <li><strong>Load integrity</strong>, after the load: did the warehouse
 *       report loading as many rows as we handed it?</li>
 * </ol>
 *
 * @param expectedCount  Declared count from the TRL trailer (row count only —
 *                       excludes any CSV header row).
 * @param accountedCount Records this run can account for. Its meaning depends
 *                       on which of the two checks built it: rows loaded plus
 *                       rows quarantined for the accounting check, rows the
 *                       warehouse reported loading for the load-integrity check.
 */
public record ReconciliationResult(long expectedCount, long accountedCount) {

    public boolean isReconciled() {
        return expectedCount == accountedCount;
    }

    /** Signed shortfall/excess: negative means records are unaccounted for. */
    public long difference() {
        return accountedCount - expectedCount;
    }
}
