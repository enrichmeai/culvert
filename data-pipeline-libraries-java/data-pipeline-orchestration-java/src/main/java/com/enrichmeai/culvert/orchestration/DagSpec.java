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

    /**
     * Construct a {@code DagSpec}.
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

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof DagSpec)) return false;
        DagSpec that = (DagSpec) o;
        return dagId.equals(that.dagId)
                && Objects.equals(schedule, that.schedule)
                && tasks.equals(that.tasks)
                && edges.equals(that.edges);
    }

    @Override
    public int hashCode() {
        return Objects.hash(dagId, schedule, tasks, edges);
    }

    @Override
    public String toString() {
        return "DagSpec{"
                + "dagId='" + dagId + '\''
                + ", schedule='" + schedule + '\''
                + ", tasks=" + tasks
                + ", edges=" + edges
                + '}';
    }
}
