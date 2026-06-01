package com.enrichmeai.culvert.orchestration;

import java.util.ArrayList;
import java.util.List;
import java.util.Objects;
import java.util.Optional;

/**
 * Renders a {@link DagSpec} into an Apache Airflow 2.9.x Python DAG definition.
 *
 * <h2>Target version</h2>
 * <p>This renderer targets <strong>Apache Airflow 2.9.x</strong>.
 * Specific assumptions:
 * <ul>
 *   <li>{@code from airflow.operators.empty import EmptyOperator} —
 *       {@code DummyOperator} was deprecated in 2.4 and removed in 2.9.
 *       Used in the base (no-wiring) path.</li>
 *   <li>{@code from airflow.operators.python import PythonOperator} —
 *       used in the job-control-wiring path so each task callable can
 *       read {@code context["run_id"]}.</li>
 *   <li>{@code schedule=} parameter on {@code DAG()} — the old
 *       {@code schedule_interval=} kwarg was deprecated in 2.4.</li>
 *   <li>{@code catchup=False} — safe default; prevents backfill on first deploy.</li>
 *   <li>{@code start_date=datetime(2024, 1, 1)} — a stable, non-future anchor.
 *       Downstream users should override this via DAG-level params if needed.</li>
 * </ul>
 *
 * <h2>Base output (no job-control wiring)</h2>
 * <pre>{@code
 * from datetime import datetime
 * from airflow import DAG
 * from airflow.operators.empty import EmptyOperator
 *
 * with DAG(
 *     dag_id="my_dag",
 *     schedule="@daily",
 *     start_date=datetime(2024, 1, 1),
 *     catchup=False,
 * ) as dag:
 *     tasks = {}
 *     tasks["A"] = EmptyOperator(task_id="A")
 *     tasks["B"] = EmptyOperator(task_id="B")
 *
 *     tasks["A"] >> tasks["B"]
 * }</pre>
 *
 * <h2>Job-control-wiring output</h2>
 * <p>When constructed via {@link #withJobControl(JobControlConfig)}, each
 * task is replaced by a {@code PythonOperator} whose callable:
 * <ol>
 *   <li>Reads {@code run_id} from the Airflow task context — the same value
 *       across all tasks in the same DAG run.</li>
 *   <li>First task only: calls {@code create_job(…)} (status {@code "created"})
 *       then {@code update_status(…, "running")}.</li>
 *   <li>Non-first tasks: calls {@code update_status(…, "running")}.</li>
 *   <li>On success: calls {@code update_status(…, "succeeded")}.</li>
 *   <li>On exception: calls {@code mark_failed(…, failure_stage="unknown")}
 *       then re-raises.</li>
 * </ol>
 *
 * <h2>Usage (no wiring)</h2>
 * <pre>{@code
 * DagSpec spec = PipelineToDagSpec.translate(pipeline, "@daily");
 * String pySource = new AirflowDagRenderer().render(spec);
 * // Write pySource to a .py file in the Airflow DAGs folder.
 * }</pre>
 *
 * <h2>Usage (with job-control wiring)</h2>
 * <pre>{@code
 * JobControlConfig config = JobControlConfig.builder("my_job_ctrl_repo")
 *         .systemId("my-system")
 *         .build();
 *
 * DagSpec spec = PipelineToDagSpec.translate(pipeline, "@daily");
 * String pySource = AirflowDagRenderer.withJobControl(config).render(spec);
 * }</pre>
 *
 * <h2>Design constraints</h2>
 * <ul>
 *   <li>Consumes only {@link DagSpec}/{@link TaskSpec} — never imports
 *       {@code Pipeline} or any runtime dependency.</li>
 *   <li>Cloud-neutral — no Airflow Java libraries (none exist); output is
 *       generated Python text.</li>
 *   <li>Task ids are referenced via a Python {@code dict} ({@code tasks["id"]})
 *       rather than bare variable names, so task ids that are not valid Python
 *       identifiers are handled safely.</li>
 *   <li>Status / failure-stage strings mirror
 *       {@link com.enrichmeai.culvert.jobcontrol.JobStatus#getValue()} and
 *       {@link com.enrichmeai.culvert.jobcontrol.FailureStage#getValue()} —
 *       no GCP type is imported.</li>
 * </ul>
 *
 * <p>Sprint-11 deliverables: issue #63 (T11.3) — base renderer;
 * issue #64 (T11.4) — job-control wiring.
 */
public final class AirflowDagRenderer implements DagRenderer {

    /** Optional job-control wiring configuration. */
    private final Optional<JobControlConfig> jobControlConfig;

    /**
     * Construct an {@code AirflowDagRenderer} without job-control wiring.
     * The renderer is stateless; a single instance may be used concurrently.
     */
    public AirflowDagRenderer() {
        this.jobControlConfig = Optional.empty();
    }

    /**
     * Construct an {@code AirflowDagRenderer} with the given job-control
     * wiring configuration.
     *
     * <p>Prefer the static factory {@link #withJobControl(JobControlConfig)}
     * for readability at call sites.
     *
     * @param jobControlConfig non-null wiring config.
     * @throws NullPointerException if {@code jobControlConfig} is null.
     */
    public AirflowDagRenderer(JobControlConfig jobControlConfig) {
        Objects.requireNonNull(jobControlConfig, "jobControlConfig must not be null");
        this.jobControlConfig = Optional.of(jobControlConfig);
    }

    /**
     * Factory — create a renderer with job-control wiring enabled.
     *
     * @param config non-null wiring config.
     * @return a new {@code AirflowDagRenderer} that injects job-control calls.
     * @throws NullPointerException if {@code config} is null.
     */
    public static AirflowDagRenderer withJobControl(JobControlConfig config) {
        return new AirflowDagRenderer(config);
    }

    /**
     * Render the {@link DagSpec} as an Airflow 2.9.x Python DAG definition.
     *
     * @param dagSpec the scheduler-agnostic DAG to render. Non-null.
     * @return a Python source string suitable for placement in the Airflow
     *         {@code dags/} directory.
     * @throws NullPointerException if {@code dagSpec} is null.
     */
    @Override
    public String render(DagSpec dagSpec) {
        Objects.requireNonNull(dagSpec, "dagSpec must not be null");
        return buildDagBody(dagSpec);
    }

    /**
     * Build the Python DAG body from the given {@link DagSpec}.
     * Package-private so {@link ComposerDagRenderer} can reuse it.
     *
     * @param dagSpec the spec to render.
     * @return the Airflow Python DAG source (without any wrapper header).
     */
    String buildDagBody(DagSpec dagSpec) {
        return jobControlConfig.isPresent()
                ? buildDagBodyWithJobControl(dagSpec, jobControlConfig.get())
                : buildDagBodyPlain(dagSpec);
    }

    // -------------------------------------------------------------------------
    // Plain (no-wiring) path — identical to the original T11.3 output
    // -------------------------------------------------------------------------

    private static String buildDagBodyPlain(DagSpec dagSpec) {
        String scheduleValue = dagSpec.schedule() != null
                ? "\"" + dagSpec.schedule() + "\""
                : "None";

        List<String> lines = new ArrayList<>();

        lines.add("from datetime import datetime");
        lines.add("from airflow import DAG");
        lines.add("from airflow.operators.empty import EmptyOperator");
        lines.add("");
        lines.add("with DAG(");
        lines.add("    dag_id=\"" + dagSpec.dagId() + "\",");
        lines.add("    schedule=" + scheduleValue + ",");
        lines.add("    start_date=datetime(2024, 1, 1),");
        lines.add("    catchup=False,");
        lines.add(") as dag:");
        lines.add("    tasks = {}");

        for (TaskSpec task : dagSpec.tasks()) {
            lines.add("    tasks[\"" + task.taskId() + "\"] = "
                    + "EmptyOperator(task_id=\"" + task.taskId() + "\")");
        }

        if (!dagSpec.edges().isEmpty()) {
            lines.add("");
            for (DagSpec.Edge edge : dagSpec.edges()) {
                lines.add("    tasks[\"" + edge.fromTaskId() + "\"] "
                        + ">> tasks[\"" + edge.toTaskId() + "\"]");
            }
        }

        return String.join("\n", lines) + "\n";
    }

    // -------------------------------------------------------------------------
    // Job-control wiring path
    // -------------------------------------------------------------------------

    /**
     * Emit a DAG where every task body is wrapped in job-control calls.
     *
     * <p>Status wire-values mirror
     * {@link com.enrichmeai.culvert.jobcontrol.JobStatus#getValue()}:
     * {@code "created"}, {@code "running"}, {@code "succeeded"}, {@code "failed"}.
     * Failure stage defaults to
     * {@link com.enrichmeai.culvert.jobcontrol.FailureStage#UNKNOWN}
     * ({@code "unknown"}) because individual tasks do not declare their stage.
     */
    private static String buildDagBodyWithJobControl(DagSpec dagSpec,
                                                     JobControlConfig config) {
        String scheduleValue = dagSpec.schedule() != null
                ? "\"" + dagSpec.schedule() + "\""
                : "None";

        List<String> lines = new ArrayList<>();

        // Imports
        lines.add("from datetime import datetime");
        lines.add("from airflow import DAG");
        lines.add("from airflow.operators.python import PythonOperator");
        lines.add("");

        // Module-level repo reference — consumers assign the real impl before the DAG loads.
        lines.add("# Job-control repository — assign your JobControlRepository impl here.");
        lines.add("_job_ctrl = " + config.repoVariable());
        lines.add("");

        // DAG block
        lines.add("with DAG(");
        lines.add("    dag_id=\"" + dagSpec.dagId() + "\",");
        lines.add("    schedule=" + scheduleValue + ",");
        lines.add("    start_date=datetime(2024, 1, 1),");
        lines.add("    catchup=False,");
        lines.add(") as dag:");
        lines.add("    tasks = {}");

        List<TaskSpec> tasks = dagSpec.tasks();
        for (int i = 0; i < tasks.size(); i++) {
            TaskSpec task = tasks.get(i);
            boolean isFirst = (i == 0);
            lines.add("");
            emitTaskCallable(lines, task, dagSpec.dagId(), config, isFirst);
            lines.add("    tasks[\"" + task.taskId() + "\"] = "
                    + "PythonOperator(task_id=\"" + task.taskId()
                    + "\", python_callable=_callable_" + sanitize(task.taskId()) + ")");
        }

        if (!dagSpec.edges().isEmpty()) {
            lines.add("");
            for (DagSpec.Edge edge : dagSpec.edges()) {
                lines.add("    tasks[\"" + edge.fromTaskId() + "\"] "
                        + ">> tasks[\"" + edge.toTaskId() + "\"]");
            }
        }

        return String.join("\n", lines) + "\n";
    }

    /**
     * Emit the {@code def _callable_<id>(**context)} block for one task.
     *
     * @param lines    the accumulator list.
     * @param task     the task to wrap.
     * @param dagId    the DAG id (used as {@code pipeline_name} in
     *                 {@code create_job}).
     * @param config   the wiring configuration.
     * @param isFirst  true only for the first task in topological order —
     *                 causes a {@code create_job} call before
     *                 {@code update_status("running")}.
     */
    private static void emitTaskCallable(List<String> lines,
                                         TaskSpec task,
                                         String dagId,
                                         JobControlConfig config,
                                         boolean isFirst) {
        String callableName = "_callable_" + sanitize(task.taskId());
        String repo = "_job_ctrl";

        lines.add("    def " + callableName + "(**context):");
        lines.add("        run_id = context[\"run_id\"]");

        if (isFirst) {
            // create_job: status=CREATED (wire value "created")
            lines.add("        " + repo + ".create_job(");
            lines.add("            run_id=run_id,");
            lines.add("            system_id=\"" + config.systemId() + "\",");
            lines.add("            pipeline_name=\"" + dagId + "\",");
            lines.add("            extract_date=context[\"ds\"],");
            lines.add("            status=\"created\",");
            lines.add("        )");
        }

        // update_status to RUNNING
        lines.add("        " + repo + ".update_status(");
        lines.add("            run_id=run_id,");
        lines.add("            status=\"running\",");
        lines.add("            total_records=None,");
        lines.add("        )");

        // try/except wrapping the task body
        lines.add("        try:");
        lines.add("            pass  # " + task.taskId() + " task body");
        // update_status to SUCCEEDED on success
        lines.add("            " + repo + ".update_status(");
        lines.add("                run_id=run_id,");
        lines.add("                status=\"succeeded\",");
        lines.add("                total_records=None,");
        lines.add("            )");
        lines.add("        except Exception as _exc:");
        // mark_failed on failure; failure_stage=UNKNOWN (wire value "unknown")
        lines.add("            " + repo + ".mark_failed(");
        lines.add("                run_id=run_id,");
        lines.add("                error_code=\"TASK_FAILED\",");
        lines.add("                error_message=str(_exc),");
        lines.add("                failure_stage=\"unknown\",");
        lines.add("                error_file_path=None,");
        lines.add("            )");
        lines.add("            raise");
    }

    /**
     * Convert a task id to a valid Python identifier suffix by replacing any
     * non-alphanumeric characters with underscores.
     *
     * <p>This is only for internal callable naming — the user-visible task id
     * in Airflow is always passed verbatim to {@code PythonOperator(task_id=…)}.
     */
    static String sanitize(String taskId) {
        return taskId.replaceAll("[^A-Za-z0-9]", "_");
    }
}
