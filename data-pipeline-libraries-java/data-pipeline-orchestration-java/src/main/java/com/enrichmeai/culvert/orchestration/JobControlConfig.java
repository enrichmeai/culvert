package com.enrichmeai.culvert.orchestration;

import java.util.Objects;

/**
 * Configuration for injecting job-control state calls into a rendered DAG.
 *
 * <p>When a {@link JobControlConfig} is supplied to {@link AirflowDagRenderer},
 * the renderer wraps each task body with Python calls to a
 * {@code JobControlRepository} implementation:
 * <ul>
 *   <li>First task: {@code create_job(…)} (status {@code CREATED}) then
 *       {@code update_status(…, "running")} at task entry.</li>
 *   <li>All tasks: {@code update_status(…, "succeeded")} on success,
 *       {@code mark_failed(…)} in the {@code except} block.</li>
 *   <li>Final task (on success): {@code update_status(…, "succeeded")} is
 *       the terminal transition.</li>
 * </ul>
 *
 * <p>All fields are used verbatim as Python expressions, so callers can supply
 * Python variable references, Airflow template strings, or literals.
 *
 * <h2>Status / FailureStage values</h2>
 * <p>The generated Python strings mirror the wire values from
 * {@link com.enrichmeai.culvert.jobcontrol.JobStatus} and
 * {@link com.enrichmeai.culvert.jobcontrol.FailureStage} ({@code getValue()})
 * — keeping the generated Python in sync with the Java contract without
 * importing any GCP type.
 *
 * <h2>run_id threading</h2>
 * <p>{@link #runIdTemplate()} defaults to Airflow's
 * {@code {{ run_id }}} macro, which is unique per DAG run and identical
 * across all task instances in a run — guaranteeing consistency by design.
 *
 * <h2>Example</h2>
 * <pre>{@code
 * JobControlConfig config = JobControlConfig.builder("job_ctrl_repo")
 *         .systemId("my-system")
 *         .build();
 *
 * AirflowDagRenderer renderer = AirflowDagRenderer.withJobControl(config);
 * String pySource = renderer.render(dagSpec);
 * }</pre>
 *
 * <p>Sprint-11 deliverable: issue #64 (T11.4).
 */
public final class JobControlConfig {

    /**
     * Default Airflow run-id template — unique per DAG run, identical across
     * all tasks in the same run.
     */
    public static final String DEFAULT_RUN_ID_TEMPLATE = "{{ run_id }}";

    /**
     * Default Airflow extract-date template (YYYY-MM-DD logical date of the
     * DAG run).
     */
    public static final String DEFAULT_EXTRACT_DATE_TEMPLATE = "{{ ds }}";

    /** Python expression that evaluates to the {@code JobControlRepository} instance. */
    private final String repoVariable;

    /** System identifier embedded in the created job row. */
    private final String systemId;

    /**
     * Python expression for the run id — shared across all tasks in a DAG run.
     * Defaults to {@link #DEFAULT_RUN_ID_TEMPLATE}.
     */
    private final String runIdTemplate;

    /**
     * Python expression for the extract date passed to {@code create_job}.
     * Defaults to {@link #DEFAULT_EXTRACT_DATE_TEMPLATE}.
     */
    private final String extractDateTemplate;

    private JobControlConfig(Builder builder) {
        this.repoVariable       = builder.repoVariable;
        this.systemId           = builder.systemId;
        this.runIdTemplate      = builder.runIdTemplate;
        this.extractDateTemplate = builder.extractDateTemplate;
    }

    // -------------------------------------------------------------------------
    // Accessors
    // -------------------------------------------------------------------------

    /**
     * Python expression that evaluates to the {@code JobControlRepository}
     * instance (e.g. {@code "BigQueryJobControlRepository()"} or a module
     * import alias).
     */
    public String repoVariable() {
        return repoVariable;
    }

    /** System identifier used in the job row. */
    public String systemId() {
        return systemId;
    }

    /**
     * Python expression for the run id — e.g. the Airflow
     * {@code {{ run_id }}} macro or a literal string for tests.
     */
    public String runIdTemplate() {
        return runIdTemplate;
    }

    /**
     * Python expression for the extract date — e.g. the Airflow
     * {@code {{ ds }}} macro or a literal {@code datetime.date.today()}.
     */
    public String extractDateTemplate() {
        return extractDateTemplate;
    }

    // -------------------------------------------------------------------------
    // Builder
    // -------------------------------------------------------------------------

    /**
     * Create a builder pre-loaded with the required {@code repoVariable}.
     *
     * @param repoVariable Python expression resolving to the
     *                     {@code JobControlRepository} instance. Non-blank.
     * @return a mutable {@link Builder}.
     * @throws NullPointerException     if {@code repoVariable} is null.
     * @throws IllegalArgumentException if {@code repoVariable} is blank.
     */
    public static Builder builder(String repoVariable) {
        return new Builder(repoVariable);
    }

    /** Builder for {@link JobControlConfig}. */
    public static final class Builder {

        private final String repoVariable;
        private String systemId           = "culvert";
        private String runIdTemplate      = DEFAULT_RUN_ID_TEMPLATE;
        private String extractDateTemplate = DEFAULT_EXTRACT_DATE_TEMPLATE;

        private Builder(String repoVariable) {
            Objects.requireNonNull(repoVariable, "repoVariable must not be null");
            if (repoVariable.isBlank()) {
                throw new IllegalArgumentException("repoVariable must not be blank");
            }
            this.repoVariable = repoVariable;
        }

        /**
         * Set the system identifier embedded in the job row.
         * Default: {@code "culvert"}.
         */
        public Builder systemId(String systemId) {
            Objects.requireNonNull(systemId, "systemId must not be null");
            this.systemId = systemId;
            return this;
        }

        /**
         * Override the run-id Python expression.
         * Default: {@link JobControlConfig#DEFAULT_RUN_ID_TEMPLATE}.
         */
        public Builder runIdTemplate(String runIdTemplate) {
            Objects.requireNonNull(runIdTemplate, "runIdTemplate must not be null");
            this.runIdTemplate = runIdTemplate;
            return this;
        }

        /**
         * Override the extract-date Python expression.
         * Default: {@link JobControlConfig#DEFAULT_EXTRACT_DATE_TEMPLATE}.
         */
        public Builder extractDateTemplate(String extractDateTemplate) {
            Objects.requireNonNull(extractDateTemplate, "extractDateTemplate must not be null");
            this.extractDateTemplate = extractDateTemplate;
            return this;
        }

        /** Build an immutable {@link JobControlConfig}. */
        public JobControlConfig build() {
            return new JobControlConfig(this);
        }
    }

    // -------------------------------------------------------------------------
    // Value semantics
    // -------------------------------------------------------------------------

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof JobControlConfig)) return false;
        JobControlConfig that = (JobControlConfig) o;
        return repoVariable.equals(that.repoVariable)
                && systemId.equals(that.systemId)
                && runIdTemplate.equals(that.runIdTemplate)
                && extractDateTemplate.equals(that.extractDateTemplate);
    }

    @Override
    public int hashCode() {
        return Objects.hash(repoVariable, systemId, runIdTemplate, extractDateTemplate);
    }

    @Override
    public String toString() {
        return "JobControlConfig{"
                + "repoVariable='" + repoVariable + '\''
                + ", systemId='" + systemId + '\''
                + ", runIdTemplate='" + runIdTemplate + '\''
                + ", extractDateTemplate='" + extractDateTemplate + '\''
                + '}';
    }
}
