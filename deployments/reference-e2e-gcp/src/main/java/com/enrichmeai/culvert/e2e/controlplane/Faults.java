package com.enrichmeai.culvert.e2e.controlplane;

import java.util.Arrays;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * The switches the proof harness (#232) flips. All off by default.
 *
 * @param killAfterRecords  if set, the process dies after this many records of {@code killStage},
 *                          in the first unit that reaches it (proof 2: a worker killed partway)
 * @param killStage         the stage the kill happens in; default {@code validate}, stage 2 of 3
 * @param failValidation    units whose validation fails (proof 5: a failed input)
 * @param duplicateTrigger  start the whole run twice at once, with two claimants (proof 1)
 * @param hangAfterRecords  if set, the worker stops making progress after this many records of
 *                          {@code killStage} but stays connected, holding its claim, as a hung or
 *                          partitioned worker would (proof 3). Only the server can release it.
 */
public record Faults(Integer killAfterRecords, String killStage, Set<String> failValidation,
                     boolean duplicateTrigger, Integer hangAfterRecords) {

    /** No faults. */
    public static final Faults NONE = new Faults(null, ControlPlaneRun.VALIDATE, Set.of(), false);

    /** The switches without a hang. */
    public Faults(Integer killAfterRecords, String killStage, Set<String> failValidation, boolean duplicateTrigger) {
        this(killAfterRecords, killStage, failValidation, duplicateTrigger, null);
    }

    public Faults {
        Objects.requireNonNull(killStage, "killStage must not be null");
        if (!ControlPlaneRun.STAGES.contains(killStage)) {
            throw new IllegalArgumentException("--fault.kill-stage must be one of " + ControlPlaneRun.STAGES
                    + ", got '" + killStage + "'");
        }
        if (killAfterRecords != null && killAfterRecords < 0) {
            throw new IllegalArgumentException("--fault.kill-after must be 0 or more, got " + killAfterRecords);
        }
        if (hangAfterRecords != null && hangAfterRecords < 0) {
            throw new IllegalArgumentException("--fault.hang-after must be 0 or more, got " + hangAfterRecords);
        }
        if (hangAfterRecords != null && killAfterRecords != null) {
            throw new IllegalArgumentException("--fault.kill-after and --fault.hang-after cannot both be set");
        }
        failValidation = Set.copyOf(failValidation);
    }

    /**
     * Read the switches from parsed {@code --key=value} arguments: {@code --fault.kill-after=N},
     * {@code --fault.kill-stage=load|validate|publish}, {@code --fault.fail-validation=unit[,unit]},
     * {@code --fault.duplicate-trigger}, {@code --fault.hang-after=N}.
     */
    public static Faults parse(Map<String, String> opts) {
        Integer killAfter = number(opts, "fault.kill-after");
        Integer hangAfter = number(opts, "fault.hang-after");
        String failing = opts.getOrDefault("fault.fail-validation", "");
        Set<String> fail = Arrays.stream(failing.split(","))
                .map(String::trim).filter(s -> !s.isEmpty()).collect(Collectors.toSet());
        return new Faults(killAfter, opts.getOrDefault("fault.kill-stage", ControlPlaneRun.VALIDATE), fail,
                Boolean.parseBoolean(opts.getOrDefault("fault.duplicate-trigger", "false")), hangAfter);
    }

    private static Integer number(Map<String, String> opts, String key) {
        String value = opts.get(key);
        try {
            return value == null ? null : Integer.valueOf(value);
        } catch (NumberFormatException e) {
            throw new IllegalArgumentException("--" + key + " must be a number, got '" + value + "'");
        }
    }
}
