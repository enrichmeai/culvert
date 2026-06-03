package com.enrichmeai.culvert.finops;

/**
 * Checked exception thrown by {@link BudgetGovernancePolicy} when a pipeline
 * run's projected cost exceeds the configured ceiling and the policy is
 * operating in {@link BudgetViolationMode#BLOCK} mode.
 *
 * <p>The exception message is intentionally human-readable so that an error
 * handler can surface it directly in a log or alert without additional
 * formatting. It includes:
 * <ul>
 *   <li>the pipeline {@code runId} that triggered the check,</li>
 *   <li>the {@code projectedCostUsd} reported by {@link CostMetrics}, and</li>
 *   <li>the {@code ceilingUsd} that was exceeded.</li>
 * </ul>
 *
 * <p>Callers that want structured access to these values should use the typed
 * accessors rather than parsing the message string.
 */
public class BudgetExceededException extends Exception {

    private static final long serialVersionUID = 1L;

    private final String runId;
    private final double projectedCostUsd;
    private final double ceilingUsd;

    /**
     * Constructs a new {@code BudgetExceededException}.
     *
     * @param runId            The pipeline run identifier.
     * @param projectedCostUsd The projected cost in USD.
     * @param ceilingUsd       The configured cost ceiling in USD.
     */
    public BudgetExceededException(String runId, double projectedCostUsd, double ceilingUsd) {
        super(String.format(
                "Budget ceiling exceeded for run '%s': projected cost $%.4f USD > ceiling $%.4f USD",
                runId, projectedCostUsd, ceilingUsd));
        this.runId = runId;
        this.projectedCostUsd = projectedCostUsd;
        this.ceilingUsd = ceilingUsd;
    }

    /** The pipeline run identifier passed to {@link BudgetGovernancePolicy#checkBudget}. */
    public String getRunId() {
        return runId;
    }

    /** The projected cost in USD (from {@link CostMetrics#estimatedCostUsd()}). */
    public double getProjectedCostUsd() {
        return projectedCostUsd;
    }

    /** The cost ceiling in USD configured on the policy. */
    public double getCeilingUsd() {
        return ceilingUsd;
    }
}
