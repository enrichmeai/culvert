package com.enrichmeai.culvert.orchestration;

import com.enrichmeai.culvert.contracts.StageClaim;
import com.enrichmeai.culvert.stageclaim.StageKey;

import java.io.Serializable;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Objects;
import java.util.Set;

/**
 * A gate predicate on a {@link TaskSpec}, and its runtime re-check (#197).
 *
 * <p><strong>The scheduler's order is advisory; the control store is authoritative.</strong> A
 * gated task lists the stages that must be completed, for the same unit and period, before it may
 * do any work. The runtime re-checks them through {@link StageClaim#completion(StageKey)} just
 * before the task runs. A scheduler that fires the task early, or out of order, therefore cannot
 * advance a stage the metadata says is not ready.
 *
 * <h2>The shape</h2>
 * <p>The predicate rides in {@link TaskSpec#params()} under {@value #COMPLETED}. Its value is a
 * {@link List} of stage names, for example
 * {@code Map.<String, Serializable>of(StageGate.COMPLETED, new ArrayList<>(List.of("load", "validate")))}.
 * The gate is open when every
 * listed stage is completed for the task's unit and period. There is one predicate kind today, so
 * it stays in the untyped {@code params} rather than adding a field to the serialized
 * {@code TaskSpec}; a second kind is the moment to revisit that.
 *
 * <h2>Validated when the DAG is rendered</h2>
 * <p>Every renderer calls {@link #validate(DagSpec)} first, so a malformed predicate fails when the
 * DAG is generated, with the task named, rather than at run time. Any other key that starts with
 * {@code culvert.gate}, in any case ({@code culvert.gates.completed}, {@code Culvert.Gate.Completed},
 * {@code culvert.gate_completed}), is rejected as well, so a typo under that prefix cannot drop a
 * gate silently. A key misspelt before the prefix ({@code culvrt.gate...}) is not caught.
 * A task with no gate key renders exactly as it did before gates existed.
 *
 * <h2>Where the re-check runs</h2>
 * <ul>
 *   <li>A Java runner calls {@link #check(TaskSpec, String, String)} or
 *       {@link #requireOpen(TaskSpec, String, String)} before the stage does work.
 *   <li>{@link AirflowDagRenderer} and {@link ComposerDagRenderer}, given a
 *       {@link StageGateConfig}, emit the same check at the top of the task's Python callable.
 *   <li>{@link SubstrateDagRenderer} refuses a gated task: its pods and Cloud Run jobs run outside
 *       the Airflow worker, and rendering the task without the check would drop the gate.
 * </ul>
 */
public final class StageGate {

    /** The {@code params} key for the one predicate kind: stages that must be completed. */
    public static final String COMPLETED = "culvert.gate.completed";

    /** Every key starting with this, in any case, is a gate key; any but {@link #COMPLETED} is a mistake. */
    static final String PREFIX = "culvert.gate";

    private final StageClaim stageClaim;

    /**
     * @param stageClaim where completions are read; {@code AutoConfig.stageClaim()} supplies it
     */
    public StageGate(StageClaim stageClaim) {
        this.stageClaim = Objects.requireNonNull(stageClaim, "stageClaim must not be null");
    }

    /**
     * The stages {@code task} waits on, in the order given; empty if the task has no gate.
     *
     * @throws IllegalArgumentException naming the task, if its gate is malformed
     */
    public static List<String> requiredStages(TaskSpec task) {
        Objects.requireNonNull(task, "task must not be null");
        // Unknown keys first, so the error does not depend on the map's order. Any key that starts
        // with "culvert.gate", in any case, is a gate key: "culvert.gates.completed" or
        // "Culvert.Gate.Completed" is a typo for the one kind, and must not leave the task ungated.
        for (String key : task.params().keySet()) {
            if (isGateKey(key) && !key.equals(COMPLETED)) {
                throw malformed(task, "has an unknown gate key '" + key + "'. The only gate predicate is '"
                        + COMPLETED + "'");
            }
        }
        if (!task.params().containsKey(COMPLETED)) {
            return List.of();
        }
        Serializable value = task.params().get(COMPLETED);
        if (!(value instanceof List<?> list)) {
            throw malformed(task, "has '" + COMPLETED + "' = " + value + ", but it must be a List of stage "
                    + "names, for example new ArrayList<>(List.of(\"load\"))");
        }
        if (list.isEmpty()) {
            throw malformed(task, "has an empty '" + COMPLETED + "' list. Remove the key to leave the task "
                    + "ungated");
        }
        List<String> stages = new ArrayList<>(list.size());
        Set<String> seen = new HashSet<>();
        for (Object stage : list) {
            if (!(stage instanceof String name) || name.isBlank()) {
                throw malformed(task, "lists '" + stage + "' in '" + COMPLETED + "'. Every entry must be a "
                        + "non-blank stage name");
            }
            if (name.equals(task.stageName())) {
                throw malformed(task, "waits on its own stage '" + name + "'. The gate could never open");
            }
            if (!seen.add(name)) {
                throw malformed(task, "lists stage '" + name + "' twice in '" + COMPLETED + "'");
            }
            stages.add(name);
        }
        return List.copyOf(stages);
    }

    /**
     * Validate every task's gate. Renderers call this before emitting anything.
     *
     * @throws IllegalArgumentException naming the first task whose gate is malformed
     */
    public static void validate(DagSpec dagSpec) {
        Objects.requireNonNull(dagSpec, "dagSpec must not be null");
        for (TaskSpec task : dagSpec.tasks()) {
            requiredStages(task);
        }
    }

    /** True if any task in {@code dagSpec} carries a gate. Validates the DAG first. */
    static boolean anyGated(DagSpec dagSpec) {
        validate(dagSpec);
        return dagSpec.tasks().stream().anyMatch(t -> !requiredStages(t).isEmpty());
    }

    /**
     * Re-check {@code task}'s gate for one unit and period. Reads completions only: it never claims
     * a stage, so it cannot make a real claimant see {@code Held}.
     *
     * @return the result; open when the task has no gate
     * @throws IllegalArgumentException if the gate is malformed, or {@code unit} or {@code period} is blank
     */
    public Result check(TaskSpec task, String unit, String period) {
        List<String> stages = requiredStages(task);
        // Reject a bad unit or period on ungated tasks too, so a caller's mistake shows up early.
        new StageKey(unit, task.stageName(), period);
        List<StageKey> waitingOn = new ArrayList<>();
        for (String stage : stages) {
            StageKey key = new StageKey(unit, stage, period);
            if (stageClaim.completion(key).isEmpty()) {
                waitingOn.add(key);
            }
        }
        return new Result(task.taskId(), waitingOn);
    }

    /**
     * {@link #check(TaskSpec, String, String)}, throwing when the gate is closed.
     *
     * @throws IllegalStateException naming the task and every stage it is still waiting on
     */
    public void requireOpen(TaskSpec task, String unit, String period) {
        Result result = check(task, unit, period);
        if (!result.isOpen()) {
            throw new IllegalStateException(result.toString());
        }
    }

    private static boolean isGateKey(String key) {
        return key.toLowerCase(Locale.ROOT).startsWith(PREFIX);
    }

    private static IllegalArgumentException malformed(TaskSpec task, String problem) {
        return new IllegalArgumentException("Gate predicate on task '" + task.taskId() + "' " + problem + ".");
    }

    /**
     * The outcome of one re-check.
     *
     * @param taskId    the task checked
     * @param waitingOn the required stages not yet completed for the unit and period; empty means open
     */
    public record Result(String taskId, List<StageKey> waitingOn) {

        public Result {
            Objects.requireNonNull(taskId, "taskId must not be null");
            waitingOn = List.copyOf(waitingOn);
        }

        /** True when every required stage is completed (or the task has no gate). */
        public boolean isOpen() {
            return waitingOn.isEmpty();
        }

        @Override
        public String toString() {
            return isOpen()
                    ? "Gate open for task '" + taskId + "'"
                    : "Gate closed for task '" + taskId + "': not completed: " + waitingOn;
        }
    }
}
