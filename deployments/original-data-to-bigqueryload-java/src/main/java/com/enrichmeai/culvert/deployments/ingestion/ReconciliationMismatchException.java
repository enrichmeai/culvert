package com.enrichmeai.culvert.deployments.ingestion;

/**
 * Thrown when a load's row count does not match the count declared in the
 * source file's TRL trailer.
 *
 * <h2>Why this is an exception and not a flag on the result</h2>
 * <p>It used to be the latter, and that was the bug. {@code process()} recorded
 * the mismatch with {@code markFailed(runId, "RECONCILIATION_MISMATCH", …)} and
 * then returned normally, so {@code run()}'s try-block completed without an
 * exception and went straight on to
 * {@code updateStatus(runId, JobStatus.SUCCEEDED, …)} — an {@code UPDATE … SET
 * status} that overwrote the failure it had just written. A load that did not
 * reconcile ended green, in the one table an operator would check to find out.
 *
 * <p>The old behaviour was deliberate — it mirrored the Python reference, which
 * logs a reconciliation warning rather than raising, and
 * {@code IngestionRunnerTest} asserted it on purpose. Parity with a permissive
 * reference is not a good enough reason to report a bad load as a good one, so
 * this reverses that decision. A mismatch is terminal: it fails the run, fails
 * the Beam/Dataflow job wrapping it, and leaves {@code FAILED} in job control.
 *
 * <p>Carrying the counts on the exception keeps them available to the
 * job-control record and to whatever logs the failure, which is what the
 * result object was being used for at the point where it stopped being
 * returned.
 */
public final class ReconciliationMismatchException extends RuntimeException {

    private static final long serialVersionUID = 1L;

    private final transient ReconciliationResult reconciliation;

    public ReconciliationMismatchException(ReconciliationResult reconciliation) {
        super("Reconciliation failed: declared " + reconciliation.expectedCount()
                + " rows, staged " + reconciliation.accountedCount()
                + ". The target table was NOT written.");
        this.reconciliation = reconciliation;
    }

    /** The declared-vs-actual comparison that failed. */
    public ReconciliationResult reconciliation() {
        return reconciliation;
    }
}
