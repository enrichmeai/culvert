package com.enrichmeai.culvert.readiness;

import java.util.Objects;
import java.util.Optional;

/**
 * One expected input's state, with the attempt that decided it: the failed attempt for
 * {@link InputState#FAILED}, the validated one for {@link InputState#READY}, the unfinished one for
 * {@link InputState#PENDING}, and none for {@link InputState#MISSING}.
 */
public record InputStatus(String input, InputState state, Optional<String> runId) {

    public InputStatus {
        InputAttempt.requireText(input, "input");
        Objects.requireNonNull(state, "state must not be null");
        Objects.requireNonNull(runId, "runId must not be null");
    }

    @Override
    public String toString() {
        return input + "=" + state + runId.map(r -> " (" + r + ")").orElse("");
    }
}
