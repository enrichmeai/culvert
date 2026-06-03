package com.enrichmeai.culvert.finops;

/**
 * Determines the action taken by {@link BudgetGovernancePolicy} when a
 * pipeline run's projected cost exceeds the configured ceiling.
 *
 * <ul>
 *   <li>{@link #BLOCK} — aborts the run by throwing
 *       {@link BudgetExceededException}. Use in production or in automated
 *       CI jobs where runaway spend is unacceptable.</li>
 *   <li>{@link #WARN} — logs a {@code WARNING} via {@code java.util.logging}
 *       and allows the run to continue. Use in development or
 *       staging environments where visibility is more important than blocking.</li>
 * </ul>
 */
public enum BudgetViolationMode {

    /**
     * Throw {@link BudgetExceededException} when the projected cost exceeds
     * the ceiling. The run does not proceed.
     */
    BLOCK,

    /**
     * Log a WARNING via {@code java.util.logging} when the projected cost
     * exceeds the ceiling. The run continues.
     */
    WARN
}
