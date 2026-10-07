package com.enrichmeai.culvert.e2e.controlplane;

import com.enrichmeai.culvert.orchestration.AirflowDagRenderer;
import com.enrichmeai.culvert.orchestration.ComposerDagRenderer;
import com.enrichmeai.culvert.orchestration.DagSpec;
import com.enrichmeai.culvert.orchestration.JobControlConfig;
import com.enrichmeai.culvert.orchestration.StageGate;
import com.enrichmeai.culvert.orchestration.StageGateConfig;
import com.enrichmeai.culvert.orchestration.TaskSpec;

import java.io.Serializable;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * The fan-out as a scheduler-agnostic {@link DagSpec}: per unit, {@code load >> validate >> publish},
 * with the units side by side and at most {@code maxConcurrency} tasks running at once (#199).
 *
 * <p>The gates are the same for the Java runner and the rendered DAG, because both read these
 * task specs: {@code validate} waits on {@code load} being completed, and {@code publish} on
 * {@code load} and {@code validate} being completed (#197) and on the unit's inputs being ready
 * (#230). The order is the scheduler's; the gates make it hold even when a task fires early.
 */
public final class ReferenceDag {

    /** The DAG id. */
    public static final String DAG_ID = "reference_e2e_control_plane";

    /** Task ids are {@code <unit>__<stage>}; the rendered DAG reads the unit back from them. */
    static final String SEPARATOR = "__";

    /**
     * The Python module the rendered DAG takes its stores from. The deployment supplies it on the
     * Airflow workers (#234); this repository does not ship one.
     */
    static final String STORES = "__import__(\"reference_e2e_control_plane_stores\")";

    private ReferenceDag() {
    }

    /** The spec for {@code units}, capped at {@code maxConcurrency} running tasks. */
    public static DagSpec spec(List<String> units, int maxConcurrency) {
        List<TaskSpec> tasks = new ArrayList<>();
        List<DagSpec.Edge> edges = new ArrayList<>();
        for (String unit : units) {
            String load = taskId(unit, ControlPlaneRun.LOAD);
            String validate = taskId(unit, ControlPlaneRun.VALIDATE);
            String publish = taskId(unit, ControlPlaneRun.PUBLISH);
            tasks.add(new TaskSpec(load, ControlPlaneRun.LOAD, List.of(), Map.of()));
            tasks.add(new TaskSpec(validate, ControlPlaneRun.VALIDATE, List.of(load),
                    gate(List.of(ControlPlaneRun.LOAD), false)));
            tasks.add(new TaskSpec(publish, ControlPlaneRun.PUBLISH, List.of(validate),
                    gate(List.of(ControlPlaneRun.LOAD, ControlPlaneRun.VALIDATE), true)));
            edges.add(new DagSpec.Edge(load, validate));
            edges.add(new DagSpec.Edge(validate, publish));
        }
        return new DagSpec(DAG_ID, "@daily", tasks, edges, maxConcurrency);
    }

    /** The task in {@code spec} that runs {@code stage} for {@code unit}. */
    static TaskSpec task(DagSpec spec, String unit, String stage) {
        String id = taskId(unit, stage);
        return spec.tasks().stream().filter(t -> t.taskId().equals(id)).findFirst()
                .orElseThrow(() -> new IllegalArgumentException("no task " + id + " in " + spec.dagId()));
    }

    static String taskId(String unit, String stage) {
        return unit + SEPARATOR + stage;
    }

    /**
     * The Composer DAG for {@code spec}: job control on every task, the stage and readiness gates
     * re-checked in the callable, and {@code max_active_tasks}.
     */
    public static String render(DagSpec spec) {
        AirflowDagRenderer airflow = AirflowDagRenderer
                .withJobControl(JobControlConfig.builder(STORES + ".job_control()")
                        .systemId("reference-e2e").build())
                .withStageGate(StageGateConfig.builder(STORES + ".stage_claim()")
                        .readinessVariable(STORES + ".input_readiness()")
                        .unitExpression("context[\"task\"].task_id.split(\"" + SEPARATOR + "\")[0]")
                        .build());
        return new ComposerDagRenderer(airflow).render(spec);
    }

    private static Map<String, Serializable> gate(List<String> completed, boolean ready) {
        Map<String, Serializable> params = new HashMap<>();
        params.put(StageGate.COMPLETED, new ArrayList<>(completed));
        if (ready) {
            params.put(StageGate.READY, Boolean.TRUE);
        }
        return params;
    }
}
