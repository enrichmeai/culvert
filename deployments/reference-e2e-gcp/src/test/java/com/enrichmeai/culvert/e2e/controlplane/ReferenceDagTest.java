package com.enrichmeai.culvert.e2e.controlplane;

import com.enrichmeai.culvert.orchestration.DagSpec;
import com.enrichmeai.culvert.orchestration.StageGate;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * The rendered Composer DAG (#231) is committed at {@code dags/reference_e2e_control_plane.py};
 * this test renders it again and fails on any difference. Regenerate it with
 * {@code mvn test -Dculvert.e2e.regenerateDag=true}.
 */
class ReferenceDagTest {

    static final Path COMMITTED = Path.of("dags", ReferenceDag.DAG_ID + ".py");

    @Test
    void theCommittedDagIsWhatTheSpecRendersTo() throws IOException {
        String rendered = ReferenceDag.render(ReferenceDag.spec(ControlPlaneMain.DEFAULT_UNITS, 2));
        if (Boolean.getBoolean("culvert.e2e.regenerateDag")) {
            Files.writeString(COMMITTED, rendered, StandardCharsets.UTF_8);
        }
        assertThat(Files.readString(COMMITTED, StandardCharsets.UTF_8))
                .as("dags/ is stale: run mvn test -Dculvert.e2e.regenerateDag=true").isEqualTo(rendered);
    }

    @Test
    void theDagCarriesTheCapTheGatesAndJobControl() {
        String dag = ReferenceDag.render(ReferenceDag.spec(ControlPlaneMain.DEFAULT_UNITS, 2));
        assertThat(dag).contains("max_active_tasks=2,")
                .contains("_stage_gate = __import__(\"reference_e2e_control_plane_stores\").stage_claim()")
                .contains("_input_readiness = __import__(\"reference_e2e_control_plane_stores\").input_readiness()")
                .contains("_job_ctrl = __import__(\"reference_e2e_control_plane_stores\").job_control()")
                .contains("unit=context[\"task\"].task_id.split(\"__\")[0]");
        String publish = dag.substring(dag.indexOf("def _callable_orders__publish"));
        assertThat(publish.indexOf("_input_readiness.not_ready(")).isPositive()
                .isLessThan(publish.indexOf("_job_ctrl.update_status("));
        String load = dag.substring(dag.indexOf("def _callable_orders__load"),
                dag.indexOf("def _callable_orders__validate"));
        assertThat(load).doesNotContain("_stage_gate.completion(").doesNotContain("_input_readiness.not_ready(");
    }

    @Test
    void eachUnitIsAChainWithTheGatesTheJavaRunnerAlsoChecks() {
        DagSpec spec = ReferenceDag.spec(List.of("orders", "customers"), 2);
        assertThat(spec.tasks()).hasSize(6);
        assertThat(spec.maxConcurrency()).isEqualTo(2);
        assertThat(spec.edges()).extracting(e -> e.fromTaskId() + ">" + e.toTaskId()).containsExactly(
                "orders__load>orders__validate", "orders__validate>orders__publish",
                "customers__load>customers__validate", "customers__validate>customers__publish");
        assertThat(StageGate.isGated(ReferenceDag.task(spec, "orders", "load"))).isFalse();
        assertThat(StageGate.requiredStages(ReferenceDag.task(spec, "orders", "validate"))).containsExactly("load");
        assertThat(StageGate.requiredStages(ReferenceDag.task(spec, "orders", "publish")))
                .containsExactly("load", "validate");
        assertThat(StageGate.requiresReady(ReferenceDag.task(spec, "orders", "publish"))).isTrue();
        assertThat(StageGate.requiresReady(ReferenceDag.task(spec, "orders", "validate"))).isFalse();
    }

    @Test
    void theFaultSwitchesParseFromArgumentsAndRejectNonsense() {
        assertThat(Faults.parse(Map.of())).isEqualTo(Faults.NONE);
        Faults all = Faults.parse(Map.of("fault.kill-after", "3", "fault.kill-stage", "publish",
                "fault.fail-validation", "orders, customers", "fault.duplicate-trigger", "true"));
        assertThat(all).isEqualTo(new Faults(3, "publish", Set.of("orders", "customers"), true));
        assertThatThrownBy(() -> Faults.parse(Map.of("fault.kill-after", "x")))
                .isInstanceOf(IllegalArgumentException.class).hasMessageContaining("'x'");
        assertThatThrownBy(() -> Faults.parse(Map.of("fault.kill-stage", "transform")))
                .isInstanceOf(IllegalArgumentException.class).hasMessageContaining("'transform'");
        assertThatThrownBy(() -> Faults.parse(Map.of("fault.kill-after", "-1")))
                .isInstanceOf(IllegalArgumentException.class);
    }
}
