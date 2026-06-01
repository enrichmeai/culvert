package com.enrichmeai.culvert.orchestration;

import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * Unit tests for {@link AirflowDagRenderer}.
 *
 * <p>All tests build {@link DagSpec} directly (never via
 * {@link PipelineToDagSpec}) to prove the renderer only consumes the model.
 *
 * <p>Target: Apache Airflow 2.9.x.
 */
class AirflowDagRendererTest {

    private final AirflowDagRenderer renderer = new AirflowDagRenderer();

    // -------------------------------------------------------------------------
    // Linear chain: A → B → C
    // -------------------------------------------------------------------------

    @Test
    void linearChain_containsCorrectTaskIds() {
        DagSpec dag = linearChainDag();

        String output = renderer.render(dag);

        assertThat(output).contains("task_id=\"A\"");
        assertThat(output).contains("task_id=\"B\"");
        assertThat(output).contains("task_id=\"C\"");
    }

    @Test
    void linearChain_containsCorrectEdges() {
        DagSpec dag = linearChainDag();

        String output = renderer.render(dag);

        assertThat(output).contains("tasks[\"A\"] >> tasks[\"B\"]");
        assertThat(output).contains("tasks[\"B\"] >> tasks[\"C\"]");
    }

    @Test
    void linearChain_containsCorrectDagId() {
        DagSpec dag = linearChainDag();

        String output = renderer.render(dag);

        assertThat(output).contains("dag_id=\"linear-chain\"");
    }

    @Test
    void linearChain_containsSchedule() {
        DagSpec dag = linearChainDag();

        String output = renderer.render(dag);

        assertThat(output).contains("schedule=\"@daily\"");
    }

    @Test
    void linearChain_containsAirflow29Imports() {
        DagSpec dag = linearChainDag();

        String output = renderer.render(dag);

        // Airflow 2.9: EmptyOperator (not DummyOperator)
        assertThat(output).contains("from airflow.operators.empty import EmptyOperator");
        assertThat(output).doesNotContain("DummyOperator");
        // Uses schedule= not schedule_interval= (Airflow 2.9 param name)
        assertThat(output).contains("schedule=");
        assertThat(output).doesNotContain("schedule_interval=");
    }

    @Test
    void linearChain_containsCatchupFalse() {
        DagSpec dag = linearChainDag();

        String output = renderer.render(dag);

        assertThat(output).contains("catchup=False");
    }

    // -------------------------------------------------------------------------
    // Diamond: A → B, A → C, B → D, C → D
    // -------------------------------------------------------------------------

    @Test
    void diamond_containsCorrectTaskIds() {
        DagSpec dag = diamondDag();

        String output = renderer.render(dag);

        assertThat(output).contains("task_id=\"A\"");
        assertThat(output).contains("task_id=\"B\"");
        assertThat(output).contains("task_id=\"C\"");
        assertThat(output).contains("task_id=\"D\"");
    }

    @Test
    void diamond_containsAllFourEdges() {
        DagSpec dag = diamondDag();

        String output = renderer.render(dag);

        assertThat(output).contains("tasks[\"A\"] >> tasks[\"B\"]");
        assertThat(output).contains("tasks[\"A\"] >> tasks[\"C\"]");
        assertThat(output).contains("tasks[\"B\"] >> tasks[\"D\"]");
        assertThat(output).contains("tasks[\"C\"] >> tasks[\"D\"]");
    }

    @Test
    void diamond_tasksDictUsed() {
        DagSpec dag = diamondDag();

        String output = renderer.render(dag);

        // Tasks referenced via dict — handles task ids that aren't Python identifiers
        assertThat(output).contains("tasks = {}");
        assertThat(output).contains("tasks[\"A\"] =");
        assertThat(output).contains("tasks[\"B\"] =");
        assertThat(output).contains("tasks[\"C\"] =");
        assertThat(output).contains("tasks[\"D\"] =");
    }

    // -------------------------------------------------------------------------
    // Null schedule → Python None
    // -------------------------------------------------------------------------

    @Test
    void nullSchedule_rendersAsPythonNone() {
        TaskSpec solo = new TaskSpec("solo_task", "solo_task", List.of(), Map.of());
        DagSpec dag = new DagSpec("manually-triggered", null, List.of(solo), List.of());

        String output = renderer.render(dag);

        assertThat(output).contains("schedule=None");
        assertThat(output).doesNotContain("schedule=\"null\"");
    }

    // -------------------------------------------------------------------------
    // Single-task DAG (no edges)
    // -------------------------------------------------------------------------

    @Test
    void singleTask_noEdges_rendersCorrectly() {
        TaskSpec solo = new TaskSpec("extract", "extract", List.of(), Map.of());
        DagSpec dag = new DagSpec("single-task-dag", "@weekly", List.of(solo), List.of());

        String output = renderer.render(dag);

        assertThat(output).contains("task_id=\"extract\"");
        assertThat(output).contains("schedule=\"@weekly\"");
        // No >> edge lines
        assertThat(output).doesNotContain(">>");
    }

    // -------------------------------------------------------------------------
    // Task id with special characters (safe via dict access)
    // -------------------------------------------------------------------------

    @Test
    void taskIdWithHyphens_referencedViaDictSafely() {
        TaskSpec t1 = new TaskSpec("my-extract-step", "my-extract-step", List.of(), Map.of());
        TaskSpec t2 = new TaskSpec("my-load-step", "my-load-step",
                List.of("my-extract-step"), Map.of());
        DagSpec dag = new DagSpec("hyphenated-dag", "@daily", List.of(t1, t2),
                List.of(new DagSpec.Edge("my-extract-step", "my-load-step")));

        String output = renderer.render(dag);

        // Dict access is safe regardless of Python identifier rules
        assertThat(output).contains("tasks[\"my-extract-step\"]");
        assertThat(output).contains("tasks[\"my-load-step\"]");
        assertThat(output).contains("tasks[\"my-extract-step\"] >> tasks[\"my-load-step\"]");
    }

    // -------------------------------------------------------------------------
    // Output structure: with DAG context manager
    // -------------------------------------------------------------------------

    @Test
    void output_usesWithDagContextManager() {
        DagSpec dag = linearChainDag();

        String output = renderer.render(dag);

        assertThat(output).contains("with DAG(");
        assertThat(output).contains(") as dag:");
    }

    // -------------------------------------------------------------------------
    // Null input guard
    // -------------------------------------------------------------------------

    @Test
    void nullDagSpec_throwsNullPointerException() {
        assertThatThrownBy(() -> renderer.render(null))
                .isInstanceOf(NullPointerException.class);
    }

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    /**
     * Build a linear-chain DagSpec: A → B → C, schedule @daily.
     * Tasks are constructed directly from {@link TaskSpec}/{@link DagSpec.Edge}
     * — no {@link PipelineToDagSpec} involvement.
     */
    private static DagSpec linearChainDag() {
        TaskSpec a = new TaskSpec("A", "A", List.of(), Map.of());
        TaskSpec b = new TaskSpec("B", "B", List.of("A"), Map.of());
        TaskSpec c = new TaskSpec("C", "C", List.of("B"), Map.of());
        List<DagSpec.Edge> edges = List.of(
                new DagSpec.Edge("A", "B"),
                new DagSpec.Edge("B", "C")
        );
        return new DagSpec("linear-chain", "@daily", List.of(a, b, c), edges);
    }

    /**
     * Build a diamond DagSpec: A → B, A → C, B → D, C → D, schedule @hourly.
     */
    private static DagSpec diamondDag() {
        TaskSpec a = new TaskSpec("A", "A", List.of(), Map.of());
        TaskSpec b = new TaskSpec("B", "B", List.of("A"), Map.of());
        TaskSpec c = new TaskSpec("C", "C", List.of("A"), Map.of());
        TaskSpec d = new TaskSpec("D", "D", List.of("B", "C"), Map.of());
        List<DagSpec.Edge> edges = List.of(
                new DagSpec.Edge("A", "B"),
                new DagSpec.Edge("A", "C"),
                new DagSpec.Edge("B", "D"),
                new DagSpec.Edge("C", "D")
        );
        return new DagSpec("diamond-dag", "0 * * * *", List.of(a, b, c, d), edges);
    }
}
