package com.enrichmeai.culvert.orchestration;

import java.io.Serializable;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Objects;

/**
 * An immutable, scheduler-agnostic description of a directed acyclic graph
 * (DAG) derived from a Culvert {@link com.enrichmeai.culvert.contracts.Pipeline}.
 *
 * <p>A {@code DagSpec} captures the full structure needed to submit a pipeline
 * to any task-scheduler (Apache Airflow, Google Cloud Composer, AWS Step
 * Functions, etc.) without importing any of those engines. The actual
 * submission is the responsibility of a <em>renderer</em> in a downstream
 * module.
 *
 * <p>Fields:
 * <ul>
 *   <li>{@code dagId} — unique identifier for the DAG in the target scheduler.</li>
 *   <li>{@code schedule} — opaque cron or interval string (e.g. {@code "@daily"},
 *       {@code "0 6 * * *"}). Renderers interpret this; the model does not
 *       parse it.</li>
 *   <li>{@code tasks} — one {@link TaskSpec} per pipeline stage, in topological
 *       order (dependencies before dependents).</li>
 *   <li>{@code edges} — explicit (producer task id → consumer task id) pairs.
 *       Redundant with {@link TaskSpec#upstreamTaskIds()} but provided for
 *       renderers that prefer an edge list over adjacency lists.</li>
 *   <li>{@code maxConcurrency} — optional; see {@link #maxConcurrency()}.</li>
 * </ul>
 *
 * <p>Instances are immutable: all collections are defensively copied at
 * construction and returned as unmodifiable views.
 */
public final class DagSpec implements Serializable {

    private static final long serialVersionUID = 1L;

    /**
     * An immutable directed edge from one task to another.
     *
     * <p>An edge {@code (from, to)} means: task {@code from} must complete
     * before task {@code to} starts.
     */
    public static final class Edge implements Serializable {

        private static final long serialVersionUID = 1L;

        private final String fromTaskId;
        private final String toTaskId;

        /**
         * @param fromTaskId Upstream task id. Required, non-blank.
         * @param toTaskId   Downstream task id. Required, non-blank.
         */
        public Edge(String fromTaskId, String toTaskId) {
            Objects.requireNonNull(fromTaskId, "fromTaskId must not be null");
            Objects.requireNonNull(toTaskId, "toTaskId must not be null");
            if (fromTaskId.isBlank()) {
                throw new IllegalArgumentException("fromTaskId must not be blank");
            }
            if (toTaskId.isBlank()) {
                throw new IllegalArgumentException("toTaskId must not be blank");
            }
            this.fromTaskId = fromTaskId;
            this.toTaskId = toTaskId;
        }

        /** The upstream task id. */
        public String fromTaskId() {
            return fromTaskId;
        }

        /** The downstream task id. */
        public String toTaskId() {
            return toTaskId;
        }

        @Override
        public boolean equals(Object o) {
            if (this == o) return true;
            if (!(o instanceof Edge)) return false;
            Edge edge = (Edge) o;
            return fromTaskId.equals(edge.fromTaskId) && toTaskId.equals(edge.toTaskId);
        }

        @Override
        public int hashCode() {
            return Objects.hash(fromTaskId, toTaskId);
        }

        @Override
        public String toString() {
            return "Edge{" + fromTaskId + " -> " + toTaskId + '}';
        }
    }

    private final String dagId;
    private final String schedule;
    private final ArrayList<TaskSpec> tasks;
    private final ArrayList<Edge> edges;
    private final Integer maxConcurrency;

    /**
     * Construct a {@code DagSpec} with no concurrency cap.
     *
     * @param dagId    Unique DAG identifier. Required, non-blank.
     * @param schedule Opaque schedule string for the target scheduler.
     *                 May be empty or {@code null} for manually-triggered DAGs.
     * @param tasks    The task list, in topological order. Required, non-null.
     *                 May not be empty.
     * @param edges    The directed dependency edges. Required, non-null.
     *                 May be empty (e.g. a single-task DAG).
     * @throws NullPointerException     if {@code dagId}, {@code tasks}, or
     *                                  {@code edges} is null.
     * @throws IllegalArgumentException if {@code dagId} is blank, or
     *                                  {@code tasks} is empty.
     */
    public DagSpec(String dagId,
                   String schedule,
                   List<TaskSpec> tasks,
                   List<Edge> edges) {
        this(dagId, schedule, tasks, edges, null);
    }

    /**
     * Construct a {@code DagSpec} whose tasks run at most {@code maxConcurrency}
     * at a time (#199). See {@link #maxConcurrency()}.
     *
     * <p>The value is checked when the DAG is rendered, not here, so the
     * renderer's message can name the DAG: every renderer rejects a value
     * below 1.
     *
     * @param maxConcurrency the cap, or {@code null} for none (today's behaviour).
     * @see #DagSpec(String, String, List, List)
     */
    public DagSpec(String dagId,
                   String schedule,
                   List<TaskSpec> tasks,
                   List<Edge> edges,
                   Integer maxConcurrency) {
        Objects.requireNonNull(dagId, "dagId must not be null");
        Objects.requireNonNull(tasks, "tasks must not be null");
        Objects.requireNonNull(edges, "edges must not be null");
        if (dagId.isBlank()) {
            throw new IllegalArgumentException("dagId must not be blank");
        }
        if (tasks.isEmpty()) {
            throw new IllegalArgumentException("tasks must not be empty");
        }
        this.dagId = dagId;
        this.schedule = schedule;
        this.tasks = new ArrayList<>(tasks);
        this.edges = new ArrayList<>(edges);
        this.maxConcurrency = maxConcurrency;
    }

    /** Unique DAG identifier. */
    public String dagId() {
        return dagId;
    }

    /**
     * Opaque schedule string (cron, interval, etc.) for the target scheduler.
     * May be {@code null} for manually-triggered DAGs.
     */
    public String schedule() {
        return schedule;
    }

    /**
     * The tasks in topological order (dependencies before dependents).
     * Unmodifiable.
     */
    public List<TaskSpec> tasks() {
        return Collections.unmodifiableList(tasks);
    }

    /**
     * Directed dependency edges. Unmodifiable.
     */
    public List<Edge> edges() {
        return Collections.unmodifiableList(edges);
    }

    /**
     * The most tasks of this DAG that may be active (queued or running) at
     * once, or {@code null} for no cap of the DAG's own. It is a ceiling: the
     * scheduler's environment can hold real parallelism lower.
     *
     * <p>This is the {@code max_concurrency} dial of a multi-unit fan-out
     * (scheduling idea 4): when the DAG runs one task per unit, isolated by its
     * unit key, the dial moves it from fully sequential ({@code 1}) to fully
     * parallel ({@code N}) with no change to the DAG. Raising it is safe only
     * because a stage is claimed atomically ({@code StageClaim}, #195): two
     * workers cannot start the same unit's stage.
     *
     * <p>Each renderer caps concurrency in its target scheduler's own idiom.
     * Without a cap, every renderer's output is unchanged.
     */
    public Integer maxConcurrency() {
        return maxConcurrency;
    }

    /**
     * The cap as a valid value, or {@code null} when there is none. Renderers
     * call this before emitting anything.
     *
     * @throws IllegalArgumentException naming the DAG, if the cap is below 1.
     */
    Integer validMaxConcurrency() {
        if (maxConcurrency != null && maxConcurrency < 1) {
            throw new IllegalArgumentException("DAG '" + dagId + "' has max_concurrency " + maxConcurrency
                    + ", but it must be at least 1 (1 runs the fan-out one task at a time). Leave it unset "
                    + "for no cap.");
        }
        return maxConcurrency;
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof DagSpec)) return false;
        DagSpec that = (DagSpec) o;
        return dagId.equals(that.dagId)
                && Objects.equals(schedule, that.schedule)
                && tasks.equals(that.tasks)
                && edges.equals(that.edges)
                && Objects.equals(maxConcurrency, that.maxConcurrency);
    }

    @Override
    public int hashCode() {
        return maxConcurrency == null
                ? Objects.hash(dagId, schedule, tasks, edges)
                : Objects.hash(dagId, schedule, tasks, edges, maxConcurrency);
    }

    @Override
    public String toString() {
        return "DagSpec{"
                + "dagId='" + dagId + '\''
                + ", schedule='" + schedule + '\''
                + ", tasks=" + tasks
                + ", edges=" + edges
                + (maxConcurrency == null ? "" : ", maxConcurrency=" + maxConcurrency)
                + '}';
    }
}
