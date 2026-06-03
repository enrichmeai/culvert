/*
 * MODULE PLACEMENT DECISION (T13.3 gate — resolved before writing code)
 * -----------------------------------------------------------------------
 * Placed in: data-pipeline-core-java (cloud-neutral kernel).
 *
 * Rationale: BudgetGovernancePolicy compares a double (CostMetrics.estimatedCostUsd)
 * against a configurable ceiling using only java.util.logging and java.util.Optional.
 * CostMetrics itself lives in data-pipeline-core-java. No com.google.cloud.* or
 * org.apache.beam.* imports are required. A new data-pipeline-gcp-finops-java module
 * and parent-POM edit are NOT needed.
 *
 * The policy receives the *result* of an estimateDryRun call (a CostMetrics value),
 * never the cloud tracker itself. Cloud-specific code (BigQueryCostTracker) remains
 * exclusively in data-pipeline-gcp-bigquery-java.
 */
package com.enrichmeai.culvert.finops;

import com.enrichmeai.culvert.contracts.GovernancePolicy;
import com.enrichmeai.culvert.governance.DataClassification;
import com.enrichmeai.culvert.governance.MaskingPolicy;
import com.enrichmeai.culvert.governance.RetentionPolicy;

import java.util.Objects;
import java.util.Optional;
import java.util.logging.Logger;

/**
 * A {@link GovernancePolicy} implementation that enforces a cost ceiling on
 * pipeline runs.
 *
 * <h2>How it works</h2>
 * <ol>
 *   <li>Before submitting a pipeline run, call
 *       {@link #checkBudget(CostMetrics, String)} with the estimate produced by
 *       {@code BigQueryCostTracker.estimateDryRun()} (or equivalent).</li>
 *   <li>In {@link BudgetViolationMode#BLOCK} mode, the method throws
 *       {@link BudgetExceededException} if
 *       {@code projected.estimatedCostUsd() > ceilingUsd}. The run does not
 *       proceed.</li>
 *   <li>In {@link BudgetViolationMode#WARN} mode, the method logs a
 *       {@code WARNING} via {@code java.util.logging} and returns normally. The
 *       run continues.</li>
 * </ol>
 *
 * <h2>GovernancePolicy inherited methods</h2>
 * <p>The three methods inherited from {@link GovernancePolicy} ({@code classify},
 * {@code maskingFor}, {@code retentionFor}) provide no-op pass-through defaults:
 * every field is {@link DataClassification#INTERNAL}, no masking applies, and no
 * retention applies. These can be composed or overridden by wrapping this policy
 * with a delegating implementation when full governance is also needed.
 *
 * <h2>Wiring into DefaultRuntimeContext</h2>
 * <pre>{@code
 * BudgetGovernancePolicy budget =
 *         new BudgetGovernancePolicy(50.0, BudgetViolationMode.BLOCK);
 * RuntimeContext ctx = DefaultRuntimeContext.builder("run-1", "prod")
 *         .register(GovernancePolicy.class, budget)
 *         .build();
 *
 * // Pre-flight check before submitting the job:
 * CostMetrics estimate = costTracker.estimateDryRun(queryConfig, ctx.runId());
 * budget.checkBudget(estimate, ctx.runId()); // throws BudgetExceededException if over ceiling
 * }</pre>
 *
 * <h2>No GCP/Beam imports</h2>
 * <p>This class is intentionally cloud-neutral. It imports only types from
 * {@code java.*} and {@code com.enrichmeai.culvert.*}. Unit tests assert this
 * invariant via a source-file grep.
 */
public final class BudgetGovernancePolicy implements GovernancePolicy {

    private static final Logger LOG =
            Logger.getLogger(BudgetGovernancePolicy.class.getName());

    private final double ceilingUsd;
    private final BudgetViolationMode mode;

    /**
     * Constructs a new {@code BudgetGovernancePolicy}.
     *
     * @param ceilingUsd The maximum allowed projected cost in USD (inclusive).
     *                   A projected cost strictly greater than this value
     *                   triggers the violation action.
     * @param mode       The action to take on a violation: {@link BudgetViolationMode#BLOCK}
     *                   throws, {@link BudgetViolationMode#WARN} logs and continues.
     * @throws IllegalArgumentException if {@code ceilingUsd} is negative.
     * @throws NullPointerException     if {@code mode} is null.
     */
    public BudgetGovernancePolicy(double ceilingUsd, BudgetViolationMode mode) {
        if (ceilingUsd < 0.0) {
            throw new IllegalArgumentException("ceilingUsd must be non-negative, got: " + ceilingUsd);
        }
        this.ceilingUsd = ceilingUsd;
        this.mode = Objects.requireNonNull(mode, "mode must not be null");
    }

    /**
     * Checks whether the projected cost from {@code metrics} stays within the
     * configured ceiling.
     *
     * <p>If {@code metrics.estimatedCostUsd() > ceilingUsd}:
     * <ul>
     *   <li>{@link BudgetViolationMode#BLOCK}: throws {@link BudgetExceededException}.</li>
     *   <li>{@link BudgetViolationMode#WARN}: logs a {@code WARNING} and returns normally.</li>
     * </ul>
     * If {@code metrics.estimatedCostUsd() <= ceilingUsd}, this method always
     * returns normally regardless of mode.
     *
     * @param projected The projected cost estimate (typically from
     *                  {@code BigQueryCostTracker.estimateDryRun}).
     * @param runId     The pipeline run identifier, used in the exception message
     *                  and log warning.
     * @throws BudgetExceededException  if in BLOCK mode and cost exceeds the ceiling.
     * @throws NullPointerException     if {@code projected} or {@code runId} is null.
     */
    public void checkBudget(CostMetrics projected, String runId) throws BudgetExceededException {
        Objects.requireNonNull(projected, "projected must not be null");
        Objects.requireNonNull(runId, "runId must not be null");

        double estimatedCost = projected.estimatedCostUsd();
        if (estimatedCost <= ceilingUsd) {
            return; // within budget — no action needed
        }

        // Cost exceeds ceiling — take the configured action.
        if (mode == BudgetViolationMode.BLOCK) {
            throw new BudgetExceededException(runId, estimatedCost, ceilingUsd);
        } else {
            // WARN mode: log and continue
            LOG.warning(String.format(
                    "Budget ceiling exceeded for run '%s': projected cost $%.4f USD > ceiling $%.4f USD — " +
                    "run will proceed (WARN mode)",
                    runId, estimatedCost, ceilingUsd));
        }
    }

    /** The configured cost ceiling in USD. */
    public double getCeilingUsd() {
        return ceilingUsd;
    }

    /** The configured violation mode. */
    public BudgetViolationMode getMode() {
        return mode;
    }

    // -------------------------------------------------------------------------
    // GovernancePolicy pass-through methods (no-op defaults)
    //
    // This policy's concern is cost enforcement. The three GovernancePolicy
    // methods below provide inert defaults so BudgetGovernancePolicy can be
    // registered as the RuntimeContext's GovernancePolicy without mixing
    // masking/retention concerns into this class. Callers that need full
    // governance should compose this with a real GovernancePolicy delegate.
    // -------------------------------------------------------------------------

    /**
     * Returns {@link DataClassification#INTERNAL} for every field/table.
     * No data-catalog lookup is performed.
     */
    @Override
    public DataClassification classify(String field, String table) {
        return DataClassification.INTERNAL;
    }

    /**
     * Returns {@link Optional#empty()} — no masking policy is enforced by this
     * cost-governance implementation.
     */
    @Override
    public Optional<MaskingPolicy> maskingFor(String field, String table) {
        return Optional.empty();
    }

    /**
     * Returns {@link Optional#empty()} — no retention policy is enforced by this
     * cost-governance implementation.
     */
    @Override
    public Optional<RetentionPolicy> retentionFor(String table) {
        return Optional.empty();
    }
}
