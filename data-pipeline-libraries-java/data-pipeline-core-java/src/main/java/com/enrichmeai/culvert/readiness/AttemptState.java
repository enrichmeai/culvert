package com.enrichmeai.culvert.readiness;

/**
 * What one attempt at producing an input has reached. An input is ready only when an attempt is
 * {@link #VALIDATED}: produced and checked. Present is not ready.
 */
public enum AttemptState {

    /** Written, not yet validated. Not terminal. */
    PRODUCED("produced"),

    /** Written and validated. Terminal. */
    VALIDATED("validated"),

    /** Producing or validating it failed. Terminal. */
    FAILED("failed");

    private final String value;

    AttemptState(String value) {
        this.value = value;
    }

    /** The wire value stored by a backend. */
    public String getValue() {
        return value;
    }

    /** True for {@link #VALIDATED} and {@link #FAILED}: once reached, the attempt's outcome is fixed. */
    public boolean isTerminal() {
        return this != PRODUCED;
    }

    /** The state for a wire value. */
    public static AttemptState fromValue(String value) {
        for (AttemptState s : values()) {
            if (s.value.equals(value)) {
                return s;
            }
        }
        throw new IllegalArgumentException("unknown attempt state: " + value);
    }
}
