package com.enrichmeai.culvert.orchestration;

import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * Unit tests for job-control wiring in {@link AirflowDagRenderer}
 * and (by delegation) {@link ComposerDagRenderer}.
 *
 * <p>DoD — issue #64 (T11.4):
 * <ol>
 *   <li>Rendered DAG includes {@code create_job} / {@code update_status} /
 *       {@code mark_failed} at the right task boundaries.</li>
 *   <li>Failure path: a failing task triggers {@code mark_failed} with the
 *       failure stage and error.</li>
 *   <li>{@code run_id} is consistent across all tasks in the DAG run
 *       (same expression in every callable).</li>
 * </ol>
 *
 * <p>All tests build {@link DagSpec} directly — no {@link PipelineToDagSpec}
 * involvement — to keep the renderer concern isolated.
 *
 * <p>Sprint-11 deliverable: issue #64 (T11.4).
 */
class JobControlWiringTest {

    // -------------------------------------------------------------------------
    // Fixtures
    // -------------------------------------------------------------------------

    /** A simple linear A → B chain. */
    private static DagSpec linearDag() {
        TaskSpec a = new TaskSpec("A", "A", List.of(), Map.of());
        TaskSpec b = new TaskSpec("B", "B", List.of("A"), Map.of());
        return new DagSpec("pipe-linear", "@daily", List.of(a, b),
                List.of(new DagSpec.Edge("A", "B")));
    }

    /** A single-task DAG. */
    private static DagSpec singleTaskDag() {
        TaskSpec t = new TaskSpec("extract", "extract", List.of(), Map.of());
        return new DagSpec("pipe-single", "@weekly", List.of(t), List.of());
    }

    private static JobControlConfig defaultConfig() {
        return JobControlConfig.builder("BigQueryJobControlRepository()")
                .systemId("test-system")
                .build();
    }

    // -------------------------------------------------------------------------
    // DoD #1: create_job on first task
    // -------------------------------------------------------------------------

    @Test
    void firstTask_containsCreateJob() {
        AirflowDagRenderer renderer = AirflowDagRenderer.withJobControl(defaultConfig());
        String output = renderer.render(linearDag());

        // create_job call must appear in the first callable (_callable_A)
        assertThat(output).contains("create_job(");
    }

    @Test
    void firstTask_createJobHasCorrectArguments() {
        AirflowDagRenderer renderer = AirflowDagRenderer.withJobControl(defaultConfig());
        String output = renderer.render(linearDag());

        assertThat(output).contains("system_id=\"test-system\"");
        assertThat(output).contains("pipeline_name=\"pipe-linear\"");
        assertThat(output).contains("status=\"created\"");
        assertThat(output).contains("extract_date=context[\"ds\"]");
    }

    @Test
    void firstTask_createJobPrecedesUpdateStatusRunning() {
        AirflowDagRenderer renderer = AirflowDagRenderer.withJobControl(defaultConfig());
        String output = renderer.render(linearDag());

        int createJobPos    = output.indexOf("create_job(");
        int updateRunningPos = output.indexOf("status=\"running\"");

        assertThat(createJobPos).isGreaterThanOrEqualTo(0);
        assertThat(updateRunningPos).isGreaterThanOrEqualTo(0);
        assertThat(createJobPos).isLessThan(updateRunningPos);
    }

    @Test
    void nonFirstTask_doesNotCallCreateJob() {
        AirflowDagRenderer renderer = AirflowDagRenderer.withJobControl(defaultConfig());
        String output = renderer.render(linearDag());

        // Only one create_job per DAG (on the first callable)
        long createJobCount = countOccurrences(output, "create_job(");
        assertThat(createJobCount).isEqualTo(1);
    }

    // -------------------------------------------------------------------------
    // DoD #1: update_status at task success
    // -------------------------------------------------------------------------

    @Test
    void everyTask_containsUpdateStatusRunning() {
        AirflowDagRenderer renderer = AirflowDagRenderer.withJobControl(defaultConfig());
        String output = renderer.render(linearDag());

        // Both tasks call update_status with "running"
        long runningCount = countOccurrences(output, "status=\"running\"");
        assertThat(runningCount).isEqualTo(2); // one per task (A and B)
    }

    @Test
    void everyTask_containsUpdateStatusSucceeded() {
        AirflowDagRenderer renderer = AirflowDagRenderer.withJobControl(defaultConfig());
        String output = renderer.render(linearDag());

        long succeededCount = countOccurrences(output, "status=\"succeeded\"");
        assertThat(succeededCount).isEqualTo(2); // one per task
    }

    @Test
    void terminalTask_updateStatusSucceeded_isLastTask() {
        AirflowDagRenderer renderer = AirflowDagRenderer.withJobControl(defaultConfig());
        String output = renderer.render(linearDag());

        // The last callable (B) must also contain "succeeded"
        int callableBStart = output.indexOf("_callable_B");
        assertThat(callableBStart).isGreaterThanOrEqualTo(0);

        String afterCallableB = output.substring(callableBStart);
        assertThat(afterCallableB).contains("status=\"succeeded\"");
    }

    // -------------------------------------------------------------------------
    // DoD #2: failure path — mark_failed
    // -------------------------------------------------------------------------

    @Test
    void everyTask_containsMarkFailed() {
        AirflowDagRenderer renderer = AirflowDagRenderer.withJobControl(defaultConfig());
        String output = renderer.render(linearDag());

        long markFailedCount = countOccurrences(output, "mark_failed(");
        assertThat(markFailedCount).isEqualTo(2); // one per task
    }

    @Test
    void markFailed_hasCorrectArguments() {
        AirflowDagRenderer renderer = AirflowDagRenderer.withJobControl(defaultConfig());
        String output = renderer.render(linearDag());

        // error_code and failure_stage must be set
        assertThat(output).contains("error_code=\"TASK_FAILED\"");
        assertThat(output).contains("failure_stage=\"unknown\"");
        // error_message captures the exception message
        assertThat(output).contains("error_message=str(_exc)");
        // error_file_path is None (no quarantine path at this level)
        assertThat(output).contains("error_file_path=None");
    }

    @Test
    void markFailed_appearsInExceptBlock() {
        AirflowDagRenderer renderer = AirflowDagRenderer.withJobControl(defaultConfig());
        String output = renderer.render(linearDag());

        // "except Exception" must precede "mark_failed"
        int exceptPos    = output.indexOf("except Exception as _exc:");
        int markFailedPos = output.indexOf("mark_failed(");

        assertThat(exceptPos).isGreaterThanOrEqualTo(0);
        assertThat(markFailedPos).isGreaterThanOrEqualTo(0);
        assertThat(exceptPos).isLessThan(markFailedPos);
    }

    @Test
    void markFailed_exceptBlockReraises() {
        AirflowDagRenderer renderer = AirflowDagRenderer.withJobControl(defaultConfig());
        String output = renderer.render(linearDag());

        // The except block must re-raise after marking failed
        int exceptPos = output.indexOf("except Exception as _exc:");
        String afterExcept = output.substring(exceptPos);

        int markFailedInBlock = afterExcept.indexOf("mark_failed(");
        int raiseInBlock      = afterExcept.indexOf("raise", markFailedInBlock);

        assertThat(markFailedInBlock).isGreaterThanOrEqualTo(0);
        assertThat(raiseInBlock).isGreaterThanOrEqualTo(0);
        assertThat(markFailedInBlock).isLessThan(raiseInBlock);
    }

    // -------------------------------------------------------------------------
    // DoD #3: run_id consistency across tasks
    // -------------------------------------------------------------------------

    @Test
    void runId_consistentAcrossAllTasks_fromContext() {
        AirflowDagRenderer renderer = AirflowDagRenderer.withJobControl(defaultConfig());
        String output = renderer.render(linearDag());

        // Each callable extracts run_id from context["run_id"]
        long runIdContextCount = countOccurrences(output, "context[\"run_id\"]");
        // Two tasks → two "run_id = context["run_id"]" assignments
        assertThat(runIdContextCount).isEqualTo(2);
    }

    @Test
    void runId_usedInAllJobControlCalls() {
        AirflowDagRenderer renderer = AirflowDagRenderer.withJobControl(defaultConfig());
        String output = renderer.render(linearDag());

        // Every call site uses the local run_id variable, not a literal
        assertThat(output).contains("run_id=run_id");
        // And does NOT embed the raw Airflow macro as a string literal
        assertThat(output).doesNotContain("run_id=\"{{ run_id }}\"");
    }

    // -------------------------------------------------------------------------
    // Repo variable: configurable, not hardcoded
    // -------------------------------------------------------------------------

    @Test
    void repoVariable_isEmittedVerbatimInOutput() {
        JobControlConfig config = JobControlConfig.builder("my_custom_repo_instance")
                .systemId("sys-x")
                .build();
        AirflowDagRenderer renderer = AirflowDagRenderer.withJobControl(config);
        String output = renderer.render(singleTaskDag());

        assertThat(output).contains("_job_ctrl = my_custom_repo_instance");
    }

    @Test
    void defaultRepoVariable_isNotBigQueryHardcoded() {
        // The renderer never hard-codes BigQueryJobControlRepository — the
        // repoVariable is whatever the caller supplies.
        JobControlConfig cfg = JobControlConfig.builder("AnyRepoImpl()")
                .build();
        AirflowDagRenderer renderer = AirflowDagRenderer.withJobControl(cfg);
        String output = renderer.render(singleTaskDag());

        assertThat(output).contains("_job_ctrl = AnyRepoImpl()");
        assertThat(output).doesNotContain("BigQueryJobControlRepository");
    }

    // -------------------------------------------------------------------------
    // Wiring uses PythonOperator, not EmptyOperator
    // -------------------------------------------------------------------------

    @Test
    void wiringEnabled_usesPythonOperator() {
        AirflowDagRenderer renderer = AirflowDagRenderer.withJobControl(defaultConfig());
        String output = renderer.render(linearDag());

        assertThat(output).contains("from airflow.operators.python import PythonOperator");
        assertThat(output).contains("PythonOperator(task_id=");
        assertThat(output).doesNotContain("EmptyOperator");
    }

    // -------------------------------------------------------------------------
    // Default (no-wiring) renderer is unaffected — regression guard
    // -------------------------------------------------------------------------

    @Test
    void defaultRenderer_noJobControlCalls() {
        AirflowDagRenderer renderer = new AirflowDagRenderer();
        String output = renderer.render(linearDag());

        assertThat(output).doesNotContain("create_job");
        assertThat(output).doesNotContain("update_status");
        assertThat(output).doesNotContain("mark_failed");
        assertThat(output).doesNotContain("PythonOperator");
        assertThat(output).contains("EmptyOperator");
    }

    // -------------------------------------------------------------------------
    // Task-id sanitisation for callable names
    // -------------------------------------------------------------------------

    @Test
    void taskIdWithHyphens_sanitisedToUnderscoresInCallableName() {
        TaskSpec t = new TaskSpec("my-extract", "my-extract", List.of(), Map.of());
        DagSpec dag = new DagSpec("d", "@daily", List.of(t), List.of());

        AirflowDagRenderer renderer = AirflowDagRenderer.withJobControl(defaultConfig());
        String output = renderer.render(dag);

        assertThat(output).contains("_callable_my_extract");
        // The operator still uses the original task id
        assertThat(output).contains("task_id=\"my-extract\"");
    }

    // -------------------------------------------------------------------------
    // ComposerDagRenderer propagates wiring (delegation test)
    // -------------------------------------------------------------------------

    @Test
    void composerRenderer_propagatesJobControlWiring() {
        AirflowDagRenderer wiredAirflow = AirflowDagRenderer.withJobControl(defaultConfig());
        ComposerDagRenderer composerRenderer = new ComposerDagRenderer(wiredAirflow);

        String output = composerRenderer.render(linearDag());

        // Composer header still present
        assertThat(output).contains("Generated by Culvert ComposerDagRenderer");
        // Job-control calls present (delegated via wired AirflowDagRenderer)
        assertThat(output).contains("create_job(");
        assertThat(output).contains("update_status(");
        assertThat(output).contains("mark_failed(");
    }

    // -------------------------------------------------------------------------
    // Single-task DAG: create_job + one success path
    // -------------------------------------------------------------------------

    @Test
    void singleTask_createJobAndSucceededOnlyOnce() {
        AirflowDagRenderer renderer = AirflowDagRenderer.withJobControl(defaultConfig());
        String output = renderer.render(singleTaskDag());

        assertThat(countOccurrences(output, "create_job(")).isEqualTo(1);
        assertThat(countOccurrences(output, "status=\"succeeded\"")).isEqualTo(1);
        assertThat(countOccurrences(output, "mark_failed(")).isEqualTo(1);
    }

    // -------------------------------------------------------------------------
    // Null-input guards on JobControlConfig
    // -------------------------------------------------------------------------

    @Test
    void jobControlConfig_blankRepoVariable_throws() {
        assertThatThrownBy(() -> JobControlConfig.builder("  "))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void jobControlConfig_nullRepoVariable_throws() {
        assertThatThrownBy(() -> JobControlConfig.builder(null))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void airflowDagRenderer_nullJobControlConfig_throws() {
        assertThatThrownBy(() -> new AirflowDagRenderer((JobControlConfig) null))
                .isInstanceOf(NullPointerException.class);
    }

    // -------------------------------------------------------------------------
    // JobControlConfig value semantics
    // -------------------------------------------------------------------------

    @Test
    void jobControlConfig_equalityAndHashCode() {
        JobControlConfig c1 = JobControlConfig.builder("repo()").systemId("s").build();
        JobControlConfig c2 = JobControlConfig.builder("repo()").systemId("s").build();

        assertThat(c1).isEqualTo(c2);
        assertThat(c1.hashCode()).isEqualTo(c2.hashCode());
    }

    @Test
    void jobControlConfig_defaultTemplates() {
        JobControlConfig c = JobControlConfig.builder("r").build();

        assertThat(c.runIdTemplate()).isEqualTo(JobControlConfig.DEFAULT_RUN_ID_TEMPLATE);
        assertThat(c.extractDateTemplate()).isEqualTo(JobControlConfig.DEFAULT_EXTRACT_DATE_TEMPLATE);
    }

    // -------------------------------------------------------------------------
    // Utility
    // -------------------------------------------------------------------------

    private static long countOccurrences(String text, String substring) {
        long count = 0;
        int idx = 0;
        while ((idx = text.indexOf(substring, idx)) != -1) {
            count++;
            idx += substring.length();
        }
        return count;
    }
}
