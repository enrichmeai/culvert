package com.enrichmeai.culvert.orchestration;

import org.junit.jupiter.api.Test;

import java.io.Serializable;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/** Gate predicates through the renderers (#197): the emitted re-check, and the render-time refusals. */
class GatedRenderingTest {

    static final StageGateConfig GATE = StageGateConfig.builder("PostgresStageClaim()").build();

    /** load → publish, where publish is gated on load and validate (validate runs in another DAG). */
    static DagSpec gatedDag() {
        TaskSpec load = new TaskSpec("load", "load", List.of(), Map.of());
        TaskSpec publish = new TaskSpec("publish", "publish", List.of("load"),
                Map.<String, Serializable>of(StageGate.COMPLETED, new ArrayList<>(List.of("load", "validate"))));
        return new DagSpec("orders_daily", "@daily", List.of(load, publish),
                List.of(new DagSpec.Edge("load", "publish")));
    }

    static DagSpec malformedDag() {
        TaskSpec publish = new TaskSpec("publish", "publish", List.of(),
                Map.<String, Serializable>of(StageGate.COMPLETED, "load"));
        return new DagSpec("orders_daily", "@daily", List.of(publish), List.of());
    }

    @Test
    void airflowRendersTheGatedTaskAsACallableThatReChecksFirst() {
        String out = new AirflowDagRenderer().withStageGate(GATE).render(gatedDag());

        assertThat(out).isEqualTo(String.join("\n",
                "from datetime import datetime",
                "from airflow import DAG",
                "from airflow.operators.empty import EmptyOperator",
                "from airflow.exceptions import AirflowException",
                "from airflow.operators.python import PythonOperator",
                "",
                "# Stage-gate checker: an object with completion(unit=, stage=, period=) that",
                "# returns None until the stage is completed (StageClaim.completion, #197).",
                "_stage_gate = PostgresStageClaim()",
                "",
                "with DAG(",
                "    dag_id=\"orders_daily\",",
                "    schedule=\"@daily\",",
                "    start_date=datetime(2024, 1, 1),",
                "    catchup=False,",
                ") as dag:",
                "    tasks = {}",
                "    tasks[\"load\"] = EmptyOperator(task_id=\"load\")",
                "",
                "    def _callable_publish(**context):",
                "        _waiting_on = [",
                "            _stage for _stage in [\"load\", \"validate\"]",
                "            if _stage_gate.completion(unit=context[\"dag\"].dag_id, stage=_stage, "
                        + "period=context[\"ds\"]) is None",
                "        ]",
                "        if _waiting_on:",
                "            raise AirflowException(",
                "                \"Gate closed for task 'publish': not completed: \" + \", \".join(_waiting_on)",
                "            )",
                "        pass  # publish task body",
                "    tasks[\"publish\"] = PythonOperator(task_id=\"publish\", python_callable=_callable_publish)",
                "",
                "    tasks[\"load\"] >> tasks[\"publish\"]",
                ""));
    }

    @Test
    void withJobControlTheGateIsCheckedBeforeAnyJobControlCall() {
        String out = AirflowDagRenderer.withJobControl(
                JobControlConfig.builder("BigQueryJobControlRepository()").systemId("orders").build())
                .withStageGate(GATE).render(gatedDag());

        String publish = out.substring(out.indexOf("def _callable_publish"));
        assertThat(publish.indexOf("_stage_gate.completion(")).isPositive()
                .isLessThan(publish.indexOf("_job_ctrl.update_status("));
        String load = out.substring(out.indexOf("def _callable_load"), out.indexOf("def _callable_publish"));
        assertThat(load).as("the ungated task has no check").doesNotContain("_stage_gate");
        assertThat(out).contains("from airflow.exceptions import AirflowException")
                .contains("_stage_gate = PostgresStageClaim()")
                .contains("_job_ctrl = BigQueryJobControlRepository()");
    }

    @Test
    void theUnitAndPeriodExpressionsAreConfigurable() {
        StageGateConfig gate = StageGateConfig.builder("my_gate")
                .unitExpression("context[\"params\"][\"unit\"]")
                .periodExpression("context[\"data_interval_start\"].strftime(\"%Y-%m\")")
                .build();
        String out = new AirflowDagRenderer().withStageGate(gate).render(gatedDag());
        assertThat(out).contains("_stage_gate = my_gate")
                .contains("completion(unit=context[\"params\"][\"unit\"], stage=_stage, "
                        + "period=context[\"data_interval_start\"].strftime(\"%Y-%m\"))");
    }

    @Test
    void composerCarriesTheSameReCheckUnderItsHeader() {
        String out = new ComposerDagRenderer(new AirflowDagRenderer().withStageGate(GATE)).render(gatedDag());
        assertThat(out).startsWith("# Generated by Culvert ComposerDagRenderer")
                .endsWith(new AirflowDagRenderer().withStageGate(GATE).render(gatedDag()));
    }

    @Test
    void aStageNameIsEscapedIntoThePythonLiteral() {
        TaskSpec t = new TaskSpec("publish", "publish", List.of(),
                Map.<String, Serializable>of(StageGate.COMPLETED, new ArrayList<>(List.of("a\"b\\c\nd"))));
        String out = new AirflowDagRenderer().withStageGate(GATE)
                .render(new DagSpec("d", null, List.of(t), List.of()));
        assertThat(out).contains("for _stage in [\"a\\\"b\\\\c\\nd\"]");
    }

    @Test
    void aGatedTaskWithoutAGateConfigIsRefusedRatherThanRenderedUnchecked() {
        assertThatThrownBy(() -> new AirflowDagRenderer().render(gatedDag()))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("Task 'publish' has a gate predicate")
                .hasMessageContaining("withStageGate");
        assertThatThrownBy(() -> new ComposerDagRenderer().render(gatedDag()))
                .hasMessageContaining("Task 'publish' has a gate predicate");
        assertThatThrownBy(() -> AirflowDagRenderer.withJobControl(JobControlConfig.builder("r").build())
                .render(gatedDag()))
                .hasMessageContaining("Task 'publish' has a gate predicate");
    }

    @Test
    void aMalformedGateFailsAtRenderTimeInEveryRendererNamingTheTask() {
        List<DagRenderer> renderers = List.of(
                new AirflowDagRenderer(),
                new AirflowDagRenderer().withStageGate(GATE),
                AirflowDagRenderer.withJobControl(JobControlConfig.builder("r").build()).withStageGate(GATE),
                new ComposerDagRenderer(new AirflowDagRenderer().withStageGate(GATE)),
                new SubstrateDagRenderer(ExecutionSubstrate.COMPOSER_2_GKE_PODS),
                new SubstrateDagRenderer(ExecutionSubstrate.CLOUD_RUN_JOBS));
        for (DagRenderer r : renderers) {
            assertThatThrownBy(() -> r.render(malformedDag()))
                    .as(r.getClass().getSimpleName())
                    .isInstanceOf(IllegalArgumentException.class)
                    .hasMessageContaining("Gate predicate on task 'publish'")
                    .hasMessageContaining("must be a List of stage names");
        }
    }

    @Test
    void theSubstrateRendererRefusesAGatedTaskBecauseItCannotReCheckIt() {
        TaskSpec ingest = new TaskSpec("ingest", "ingest", List.of(), Map.<String, Serializable>of(
                "image", "europe-docker.pkg.dev/p/r/ingest:1",
                StageGate.COMPLETED, new ArrayList<>(List.of("land"))));
        DagSpec dag = new DagSpec("pods", null, List.of(ingest), List.of());
        for (ExecutionSubstrate s : List.of(ExecutionSubstrate.COMPOSER_2_GKE_PODS, ExecutionSubstrate.COMPOSER_3)) {
            assertThatThrownBy(() -> new SubstrateDagRenderer(s).render(dag))
                    .isInstanceOf(IllegalArgumentException.class)
                    .hasMessageContaining("Task 'ingest' has a gate predicate")
                    .hasMessageContaining("StageGate.requireOpen");
        }
    }

    @Test
    void withStageGateKeepsTheOriginalRendererUnchanged() {
        AirflowDagRenderer plain = new AirflowDagRenderer();
        plain.withStageGate(GATE);
        assertThatThrownBy(() -> plain.render(gatedDag())).hasMessageContaining("no StageGateConfig");
        assertThatThrownBy(() -> plain.withStageGate(null)).isInstanceOf(NullPointerException.class);
        assertThatThrownBy(() -> StageGateConfig.builder(" ")).isInstanceOf(IllegalArgumentException.class);
    }
}
