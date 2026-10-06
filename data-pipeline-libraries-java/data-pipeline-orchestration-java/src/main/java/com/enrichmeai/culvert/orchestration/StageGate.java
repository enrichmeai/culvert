package com.enrichmeai.culvert.orchestration;

import com.enrichmeai.culvert.contracts.InputReadiness;
import com.enrichmeai.culvert.contracts.StageClaim;
import com.enrichmeai.culvert.readiness.InputStatus;
import com.enrichmeai.culvert.readiness.Readiness;
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
 * listed stage is completed for the task's unit and period.
 *
 * <p>The second kind (#230) is {@value #READY} = {@code Boolean.TRUE}: the task waits until
 * {@link InputReadiness#readiness(String, String)} says every input its unit expects for the period
 * is ready. An undeclared unit is never ready. A task may carry both keys; it is open only when both
 * hold. Both kinds stay in the untyped {@code params} rather than a new field on the serialized
 * {@code TaskSpec}: the two keys are checked together by the same validation and typo guard below,
 * and a {@code TaskSpec} serialized before #230 reads back unchanged.
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

    /** The {@code params} key for the first predicate kind: stages that must be completed. */
    public static final String COMPLETED = "culvert.gate.completed";

    /**
     * The {@code params} key for the second predicate kind (#230): {@code true} means the task waits
     * until every input its unit expects for the period is produced and validated
     * ({@link InputReadiness}).
     */
    public static final String READY = "culvert.gate.ready";

    /**
     * Every key starting with this, in any case, is a gate key; any but {@link #COMPLETED} and
     * {@link #READY} is a mistake.
     */
    static final String PREFIX = "culvert.gate";

    private final StageClaim stageClaim;
    private final InputReadiness readiness;

    /**
     * A gate that reads stage completions only. A task with a {@link #READY} gate is refused by
     * {@link #check}, because there is nothing to read readiness from.
     *
     * @param stageClaim where completions are read; {@code AutoConfig.stageClaim()} supplies it
     */
    public StageGate(StageClaim stageClaim) {
        this.stageClaim = Objects.requireNonNull(stageClaim, "stageClaim must not be null");
        this.readiness = null;
    }

    /** A gate that reads both stage completions and input readiness. */
    public StageGate(StageClaim stageClaim, InputReadiness readiness) {
        this.stageClaim = Objects.requireNonNull(stageClaim, "stageClaim must not be null");
        this.readiness = Objects.requireNonNull(readiness, "readiness must not be null");
    }

    private StageGate(InputReadiness readiness, Void readinessOnly) {
        this.stageClaim = null;
        this.readiness = Objects.requireNonNull(readiness, "readiness must not be null");
    }

    /**
     * A gate that reads input readiness only. A task with a {@link #COMPLETED} gate is refused by
     * {@link #check}. A factory rather than a constructor, so {@code new StageGate(null)} stays
     * unambiguous for existing callers.
     *
     * @param readiness where readiness is read; {@code AutoConfig.inputReadiness()} supplies it
     */
    public static StageGate forReadiness(InputReadiness readiness) {
        return new StageGate(readiness, null);
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
            if (isGateKey(key) && !key.equals(COMPLETED) && !key.equals(READY)) {
                throw malformed(task, "has an unknown gate key '" + key + "'. The gate predicates are '"
                        + COMPLETED + "' and '" + READY + "'");
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
     * Whether {@code task} waits for its unit's inputs to be ready ({@link #READY}).
     *
     * @throws IllegalArgumentException naming the task, if its gate is malformed
     */
    public static boolean requiresReady(TaskSpec task) {
        requiredStages(task); // the whole gate is validated, unknown keys included
        if (!task.params().containsKey(READY)) {
            return false;
        }
        Serializable value = task.params().get(READY);
        if (!Boolean.TRUE.equals(value)) {
            throw malformed(task, "has '" + READY + "' = " + value + ", but it must be true. Remove the key "
                    + "to leave the task ungated by readiness");
        }
        return true;
    }

    /** True if {@code task} carries a gate of either kind. Validates its gate first. */
    public static boolean isGated(TaskSpec task) {
        return requiresReady(task) || !requiredStages(task).isEmpty();
    }

    /**
     * Validate every task's gate. Renderers call this before emitting anything.
     *
     * @throws IllegalArgumentException naming the first task whose gate is malformed
     */
    public static void validate(DagSpec dagSpec) {
        Objects.requireNonNull(dagSpec, "dagSpec must not be null");
        for (TaskSpec task : dagSpec.tasks()) {
            requiresReady(task);
        }
    }

    /** True if any task in {@code dagSpec} carries a gate. Validates the DAG first. */
    static boolean anyGated(DagSpec dagSpec) {
        validate(dagSpec);
        return dagSpec.tasks().stream().anyMatch(StageGate::isGated);
    }

    /**
     * Re-check {@code task}'s gate for one unit and period. It only reads: completions through
     * {@link StageClaim#completion}, which never claims a stage, and readiness through
     * {@link InputReadiness#readiness}.
     *
     * @return the result; open when the task has no gate
     * @throws IllegalArgumentException if the gate is malformed, or {@code unit} or {@code period} is blank
     * @throws IllegalStateException naming the task, if it has a gate kind this {@code StageGate} was
     *         built without a store for (a task is never let through unchecked)
     */
    public Result check(TaskSpec task, String unit, String period) {
        List<String> stages = requiredStages(task);
        boolean ready = requiresReady(task);
        // Reject a bad unit or period on ungated tasks too, so a caller's mistake shows up early.
        new StageKey(unit, task.stageName(), period);
        if (!stages.isEmpty() && stageClaim == null) {
            throw new IllegalStateException("Task '" + task.taskId() + "' waits on stages (" + COMPLETED
                    + ") but this StageGate has no StageClaim to read them from");
        }
        if (ready && readiness == null) {
            throw new IllegalStateException("Task '" + task.taskId() + "' waits on its inputs (" + READY
                    + ") but this StageGate has no InputReadiness to read them from");
        }
        List<StageKey> waitingOn = new ArrayList<>();
        for (String stage : stages) {
            StageKey key = new StageKey(unit, stage, period);
            if (stageClaim.completion(key).isEmpty()) {
                waitingOn.add(key);
            }
        }
        List<String> inputsNotReady = new ArrayList<>();
        if (ready) {
            Readiness r = readiness.readiness(unit, period);
            if (!r.declared()) {
                inputsNotReady.add("no expected inputs are declared for unit '" + unit + "'");
            } else {
                for (InputStatus status : r.notReady()) {
                    inputsNotReady.add(status.toString());
                }
            }
        }
        return new Result(task.taskId(), waitingOn, inputsNotReady);
    }

    /**
     * {@link #check(TaskSpec, String, String)}, throwing when the gate is closed.
     *
     * @throws IllegalStateException naming the task and every stage and input it is still waiting on
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
     * @param taskId         the task checked
     * @param waitingOn      the required stages not yet completed for the unit and period
     * @param inputsNotReady each expected input that is not ready, as {@code name=STATE (run)}, or why
     *                       readiness could not open (an undeclared unit); empty when ready or ungated
     */
    public record Result(String taskId, List<StageKey> waitingOn, List<String> inputsNotReady) {

        public Result {
            Objects.requireNonNull(taskId, "taskId must not be null");
            waitingOn = List.copyOf(waitingOn);
            inputsNotReady = List.copyOf(inputsNotReady);
        }

        /** A result with no readiness gate: the shape {@code StageGate} returned before #230. */
        public Result(String taskId, List<StageKey> waitingOn) {
            this(taskId, waitingOn, List.of());
        }

        /** True when every required stage is completed and every expected input is ready. */
        public boolean isOpen() {
            return waitingOn.isEmpty() && inputsNotReady.isEmpty();
        }

        @Override
        public String toString() {
            if (isOpen()) {
                return "Gate open for task '" + taskId + "'";
            }
            List<String> why = new ArrayList<>();
            if (!waitingOn.isEmpty()) {
                why.add("not completed: " + waitingOn);
            }
            if (!inputsNotReady.isEmpty()) {
                why.add("inputs not ready: " + inputsNotReady);
            }
            return "Gate closed for task '" + taskId + "': " + String.join("; ", why);
        }
    }
}
