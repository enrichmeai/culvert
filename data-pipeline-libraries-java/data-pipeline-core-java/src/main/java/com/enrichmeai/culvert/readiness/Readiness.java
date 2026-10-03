package com.enrichmeai.culvert.readiness;

import java.util.List;
import java.util.Objects;

/**
 * Whether a unit's inputs are ready for a period: the expected set (from the catalogue) minus the
 * ready-and-validated set. It names every input that is not ready and says why, because an operator
 * needs the names, not a count.
 *
 * @param unit     the unit checked
 * @param period   the period checked
 * @param declared whether the catalogue has an expected set for the unit. An undeclared unit is
 *                 never ready: an empty expected set would otherwise open every gate.
 * @param inputs   one status per expected input, sorted by input name
 */
public record Readiness(String unit, String period, boolean declared, List<InputStatus> inputs) {

    public Readiness {
        InputAttempt.requireText(unit, "unit");
        InputAttempt.requireText(period, "period");
        inputs = List.copyOf(Objects.requireNonNull(inputs, "inputs must not be null"));
    }

    /** True when the unit is declared and every expected input is {@link InputState#READY}. */
    public boolean isReady() {
        return declared && inputs.stream().allMatch(s -> s.state() == InputState.READY);
    }

    /** The inputs not yet ready, in name order. */
    public List<InputStatus> notReady() {
        return inputs.stream().filter(s -> s.state() != InputState.READY).toList();
    }

    /** The names of the inputs in {@code state}, in name order. */
    public List<String> inState(InputState state) {
        return inputs.stream().filter(s -> s.state() == state).map(InputStatus::input).toList();
    }

    /** The expected inputs with no attempt at all for the period. */
    public List<String> missing() {
        return inState(InputState.MISSING);
    }

    /** The expected inputs whose standing attempt failed. */
    public List<String> failed() {
        return inState(InputState.FAILED);
    }

    @Override
    public String toString() {
        if (!declared) {
            return "Not ready: no expected inputs are declared for unit '" + unit + "'";
        }
        return isReady()
                ? "Ready: unit '" + unit + "' for " + period + " (" + inputs.size() + " inputs)"
                : "Not ready: unit '" + unit + "' for " + period + ": " + notReady();
    }
}
