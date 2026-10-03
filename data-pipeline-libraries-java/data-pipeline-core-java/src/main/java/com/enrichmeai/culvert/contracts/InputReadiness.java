package com.enrichmeai.culvert.contracts;

import com.enrichmeai.culvert.readiness.InputAttempt;
import com.enrichmeai.culvert.readiness.Readiness;
import com.enrichmeai.culvert.readiness.ReadinessResolver;

import java.util.Set;

/**
 * Whether a unit's inputs are ready for a period (#198; control-plane epic #188). Inputs (an FDP,
 * a source extract) publish each attempt to the control store; a unit's gate opens only when every
 * input the catalogue expects for it has been produced <em>and validated</em> for the period.
 *
 * <h2>An anti-join, not a count</h2>
 * <p>The catalogue declares what each unit expects. Readiness is the expected set minus the
 * ready-and-validated set, and {@link Readiness} names each input that is missing, failed or still
 * pending. Counting rows that happen to be present would be satisfied by the wrong inputs.
 * {@link ReadinessResolver} holds the rule, including how terminal precedence and retries resolve;
 * every implementation uses it.
 *
 * <h2>An optional capability, not one of the shared contracts</h2>
 * <p>Like {@link StageClaim}, it is Java-only for now, and its tables are the adapter's own schema,
 * not wire-contract tables. Promote it to {@code docs/CONTRACT.md} when a second deployment needs
 * the same shape. On a deployment without a provider, {@code AutoConfig.inputReadiness()} is empty.
 */
public interface InputReadiness {

    /**
     * Declare the inputs {@code unit} expects, replacing any earlier declaration. The catalogue is
     * configuration, not ledger: replacing it changes the answer for every period.
     *
     * @throws IllegalArgumentException if {@code unit} or an input is blank, or {@code inputs} is
     *         empty: a unit that needs nothing should not be gated, and an empty set would be
     *         trivially ready
     */
    void declareExpected(String unit, Set<String> inputs);

    /** The inputs {@code unit} expects; empty if it was never declared. */
    Set<String> expected(String unit);

    /** Append one attempt event. Events are never changed or removed. */
    void publish(InputAttempt attempt);

    /**
     * The unit's readiness for {@code period}, read in one consistent view of the catalogue and the
     * ledger. An undeclared unit is not ready.
     */
    Readiness readiness(String unit, String period);
}
