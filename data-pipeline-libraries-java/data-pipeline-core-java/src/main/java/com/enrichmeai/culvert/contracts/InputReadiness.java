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
     * Declare the inputs {@code unit} expects in every period that has no declaration of its own,
     * replacing any earlier one. The catalogue is configuration, not ledger: replacing this default
     * changes the answer for every such period, past ones included. Declare a period's own set
     * ({@link #declareExpected(String, String, Set)}) to pin what it expected.
     *
     * @throws IllegalArgumentException if {@code unit} or an input is blank, or {@code inputs} is
     *         empty: a unit that needs nothing should not be gated, and an empty set would be
     *         trivially ready
     */
    void declareExpected(String unit, Set<String> inputs);

    /**
     * Declare the inputs {@code unit} expects in {@code period} only (a quarter-end file, a
     * holiday), replacing any earlier declaration for that period. It overrides the unit's default
     * for that period and no other.
     *
     * @throws IllegalArgumentException as {@link #declareExpected(String, Set)}, or if {@code period}
     *         is blank
     */
    void declareExpected(String unit, String period, Set<String> inputs);

    /** The inputs {@code unit} expects by default; empty if no default was declared. */
    Set<String> expected(String unit);

    /**
     * The inputs {@code unit} expects in {@code period}: the period's own declaration if there is
     * one, else the default. Empty if neither was declared.
     */
    Set<String> expected(String unit, String period);

    /** Append one attempt event. Events are never changed or removed. */
    void publish(InputAttempt attempt);

    /**
     * The unit's readiness for {@code period} against {@link #expected(String, String)}, read in one
     * consistent view of the catalogue and the ledger. An undeclared unit is not ready.
     *
     * <p>Nothing expires: an input stays failed until a retry naming the failed attempt is
     * published, and pending until its attempt records a terminal event. See
     * {@link ReadinessResolver} for the recovery.
     */
    Readiness readiness(String unit, String period);
}
