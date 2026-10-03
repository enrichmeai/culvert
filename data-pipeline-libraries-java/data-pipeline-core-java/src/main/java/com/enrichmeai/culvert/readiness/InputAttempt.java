package com.enrichmeai.culvert.readiness;

import java.util.Objects;
import java.util.Optional;

/**
 * One event in an attempt to produce {@code input} for {@code period}, appended to the readiness
 * ledger by the run that produces it.
 *
 * <p>An attempt is identified by its {@code runId}. A retry takes a new {@code runId} and names the
 * attempt it replaces in {@code retryOf}, as {@code docs/CONTRACT.md} §7 has a retry record its
 * {@code previous_run_id}. That link, and only that link, lets a later attempt supersede a failed
 * one: see {@link ReadinessResolver}.
 *
 * @param input   the input's name, as the expected-set catalogue lists it (for example an FDP)
 * @param period  the slice of time it covers, such as {@code 2026-10}
 * @param runId   the attempt
 * @param state   what the attempt has reached
 * @param retryOf the attempt this one retries, if it is a retry
 */
public record InputAttempt(String input, String period, String runId, AttemptState state,
                           Optional<String> retryOf) {

    public InputAttempt {
        requireText(input, "input");
        requireText(period, "period");
        requireText(runId, "runId");
        Objects.requireNonNull(state, "state must not be null");
        Objects.requireNonNull(retryOf, "retryOf must not be null (use Optional.empty())");
        retryOf.ifPresent(previous -> {
            requireText(previous, "retryOf");
            if (previous.equals(runId)) {
                throw new IllegalArgumentException("an attempt cannot retry itself: " + runId);
            }
        });
    }

    /** A first attempt, not a retry. */
    public static InputAttempt of(String input, String period, String runId, AttemptState state) {
        return new InputAttempt(input, period, runId, state, Optional.empty());
    }

    /** A retry of {@code previousRunId}. */
    public static InputAttempt retry(String input, String period, String runId, AttemptState state,
                                     String previousRunId) {
        return new InputAttempt(input, period, runId, state, Optional.of(previousRunId));
    }

    static String requireText(String value, String name) {
        Objects.requireNonNull(value, name + " must not be null");
        if (value.isBlank()) {
            throw new IllegalArgumentException(name + " must not be blank");
        }
        return value;
    }
}
