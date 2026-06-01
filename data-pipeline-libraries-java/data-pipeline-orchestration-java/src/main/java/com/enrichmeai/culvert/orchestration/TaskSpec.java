package com.enrichmeai.culvert.orchestration;

import java.io.Serializable;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

/**
 * An immutable, scheduler-agnostic description of one unit of work in a
 * {@link DagSpec}.
 *
 * <p>Each {@code TaskSpec} corresponds to one {@link com.enrichmeai.culvert.contracts.PipelineStage}
 * in the source {@link com.enrichmeai.culvert.contracts.Pipeline}. The task id is
 * the stage name; {@code stageName} is kept explicit for forward-compatibility
 * (future translators may rename tasks independently of their underlying stage).
 *
 * <p>Upstream dependencies are expressed as a list of other task ids within
 * the same {@link DagSpec}. The translator populates these from the stage's
 * input/output edges.
 *
 * <p>The {@code params} map carries opaque, serializable key/value pairs that
 * a downstream renderer (Composer, Step Functions, etc.) may use to configure
 * the task. Values must be {@link Serializable}.
 *
 * <p>Instances are immutable: all collections are defensively copied at
 * construction and returned as unmodifiable views.
 */
public final class TaskSpec implements Serializable {

    private static final long serialVersionUID = 1L;

    private final String taskId;
    private final String stageName;
    private final ArrayList<String> upstreamTaskIds;
    private final HashMap<String, Serializable> params;

    /**
     * Construct a {@code TaskSpec}.
     *
     * @param taskId          Unique task id within the enclosing {@link DagSpec}. Required, non-blank.
     * @param stageName       The name of the {@link com.enrichmeai.culvert.contracts.PipelineStage}
     *                        this task wraps. Required, non-blank.
     * @param upstreamTaskIds Task ids that must complete before this task runs.
     *                        May be empty for root tasks. Required (pass empty list, not null).
     * @param params          Opaque, serializable parameters for downstream renderers.
     *                        May be empty. Required (pass empty map, not null).
     * @throws NullPointerException     if any argument is null.
     * @throws IllegalArgumentException if {@code taskId} or {@code stageName} is blank.
     */
    public TaskSpec(String taskId,
                    String stageName,
                    List<String> upstreamTaskIds,
                    Map<String, Serializable> params) {
        Objects.requireNonNull(taskId, "taskId must not be null");
        Objects.requireNonNull(stageName, "stageName must not be null");
        Objects.requireNonNull(upstreamTaskIds, "upstreamTaskIds must not be null");
        Objects.requireNonNull(params, "params must not be null");
        if (taskId.isBlank()) {
            throw new IllegalArgumentException("taskId must not be blank");
        }
        if (stageName.isBlank()) {
            throw new IllegalArgumentException("stageName must not be blank");
        }
        this.taskId = taskId;
        this.stageName = stageName;
        this.upstreamTaskIds = new ArrayList<>(upstreamTaskIds);
        this.params = new HashMap<>(params);
    }

    /** Unique task id within the enclosing {@link DagSpec}. */
    public String taskId() {
        return taskId;
    }

    /** The name of the wrapped {@link com.enrichmeai.culvert.contracts.PipelineStage}. */
    public String stageName() {
        return stageName;
    }

    /**
     * Task ids whose completion must precede this task's execution, in the
     * order established by the translator. Unmodifiable.
     */
    public List<String> upstreamTaskIds() {
        return Collections.unmodifiableList(upstreamTaskIds);
    }

    /**
     * Opaque, serializable parameters for downstream renderers. Unmodifiable.
     */
    public Map<String, Serializable> params() {
        return Collections.unmodifiableMap(params);
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof TaskSpec)) return false;
        TaskSpec that = (TaskSpec) o;
        return taskId.equals(that.taskId)
                && stageName.equals(that.stageName)
                && upstreamTaskIds.equals(that.upstreamTaskIds)
                && params.equals(that.params);
    }

    @Override
    public int hashCode() {
        return Objects.hash(taskId, stageName, upstreamTaskIds, params);
    }

    @Override
    public String toString() {
        return "TaskSpec{"
                + "taskId='" + taskId + '\''
                + ", stageName='" + stageName + '\''
                + ", upstreamTaskIds=" + upstreamTaskIds
                + ", params=" + params
                + '}';
    }
}
