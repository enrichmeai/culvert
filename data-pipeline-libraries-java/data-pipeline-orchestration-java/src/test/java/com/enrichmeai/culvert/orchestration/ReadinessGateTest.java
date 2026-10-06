package com.enrichmeai.culvert.orchestration;

import com.enrichmeai.culvert.contracts.InputReadiness;
import com.enrichmeai.culvert.readiness.AttemptState;
import com.enrichmeai.culvert.readiness.InputAttempt;
import com.enrichmeai.culvert.readiness.Readiness;
import com.enrichmeai.culvert.readiness.ReadinessResolver;
import com.enrichmeai.culvert.stageclaim.StageKey;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.MethodSource;

import java.io.Serializable;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Stream;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/** Readiness as a gate predicate (#230): the shape, the Java re-check, and the rendered re-check. */
class ReadinessGateTest {

    static final String UNIT = "orders";
    static final String PERIOD = "2026-10-03";

    /** Reads through {@link ReadinessResolver}, as every backend must. */
    static final class Ledger implements InputReadiness {
        final Map<String, Set<String>> catalogue = new HashMap<>();
        final List<InputAttempt> attempts = new ArrayList<>();

        @Override
        public void declareExpected(String unit, Set<String> inputs) {
            catalogue.put(unit, Set.copyOf(inputs));
        }

        @Override
        public void declareExpected(String unit, String period, Set<String> inputs) {
            catalogue.put(unit + "/" + period, Set.copyOf(inputs));
        }

        @Override
        public Set<String> expected(String unit) {
            return catalogue.getOrDefault(unit, Set.of());
        }

        @Override
        public Set<String> expected(String unit, String period) {
            Set<String> own = catalogue.get(unit + "/" + period);
            return own != null ? own : expected(unit);
        }

        @Override
        public void publish(InputAttempt attempt) {
            attempts.add(attempt);
        }

        @Override
        public Readiness readiness(String unit, String period) {
            return ReadinessResolver.resolve(unit, period, expected(unit, period), attempts);
        }
    }

    static TaskSpec task(String taskId, Map<String, Serializable> params) {
        return new TaskSpec(taskId, taskId, List.of(), params);
    }

    static TaskSpec readyGated(String taskId) {
        return task(taskId, Map.of(StageGate.READY, Boolean.TRUE));
    }

    static TaskSpec bothGated(String taskId) {
        Map<String, Serializable> params = new HashMap<>();
        params.put(StageGate.READY, Boolean.TRUE);
        params.put(StageGate.COMPLETED, new ArrayList<>(List.of("load")));
        return task(taskId, params);
    }

    // ---------------------------------------------------------------- shape

    @Test
    void aTaskWithoutTheKeyIsNotReadinessGated() {
        TaskSpec t = task("load", Map.of("table", "raw.orders"));
        assertThat(StageGate.requiresReady(t)).isFalse();
        assertThat(StageGate.isGated(t)).isFalse();
    }

    @Test
    void trueGatesTheTaskOnReadiness() {
        assertThat(StageGate.requiresReady(readyGated("publish"))).isTrue();
        assertThat(StageGate.isGated(readyGated("publish"))).isTrue();
        assertThat(StageGate.requiredStages(readyGated("publish"))).isEmpty();
    }

    static Stream<Serializable> notTrue() {
        return Stream.of(Boolean.FALSE, "true", 1, null, new ArrayList<>(List.of("orders")));
    }

    /** Anything but {@code true} is refused, so {@code false} or {@code "true"} cannot read as a gate or as none. */
    @ParameterizedTest
    @MethodSource("notTrue")
    void anythingButTrueIsRefusedNamingTheTask(Serializable value) {
        Map<String, Serializable> params = new HashMap<>();
        params.put(StageGate.READY, value);
        TaskSpec t = task("publish", params);
        assertThatThrownBy(() -> StageGate.requiresReady(t))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("'publish'")
                .hasMessageContaining("must be true");
        DagSpec dag = new DagSpec("orders_daily", "@daily", List.of(t), List.of());
        assertThatThrownBy(() -> StageGate.validate(dag)).isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("'publish'");
    }

    @Test
    void aTypoUnderThePrefixStillFailsAndNamesBothKeys() {
        TaskSpec t = task("publish", Map.of("culvert.gate.readY", Boolean.TRUE));
        assertThatThrownBy(() -> StageGate.requiresReady(t))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("culvert.gate.readY")
                .hasMessageContaining(StageGate.COMPLETED)
                .hasMessageContaining(StageGate.READY);
    }

    @Test
    void aMalformedStagesKeyIsReportedEvenWhenReadyIsWellFormed() {
        Map<String, Serializable> params = new HashMap<>();
        params.put(StageGate.READY, Boolean.TRUE);
        params.put(StageGate.COMPLETED, "load");
        assertThatThrownBy(() -> StageGate.requiresReady(task("publish", params)))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("'publish'");
    }

    // ---------------------------------------------------------------- Java re-check

    @Test
    void anUndeclaredUnitIsNeverReady() {
        StageGate.Result r = StageGate.forReadiness(new Ledger()).check(readyGated("publish"), UNIT, PERIOD);
        assertThat(r.isOpen()).isFalse();
        assertThat(r.waitingOn()).isEmpty();
        assertThat(r.inputsNotReady()).containsExactly("no expected inputs are declared for unit 'orders'");
    }

    @Test
    void theGateOpensOnlyWhenEveryExpectedInputIsValidated() {
        Ledger ledger = new Ledger();
        ledger.declareExpected(UNIT, Set.of("customers", "orders_raw"));
        StageGate gate = StageGate.forReadiness(ledger);
        TaskSpec publish = readyGated("publish");

        StageGate.Result none = gate.check(publish, UNIT, PERIOD);
        assertThat(none.isOpen()).isFalse();
        assertThat(none.inputsNotReady()).containsExactlyInAnyOrder("customers=MISSING", "orders_raw=MISSING");

        ledger.publish(InputAttempt.of("customers", PERIOD, "r1", AttemptState.VALIDATED));
        ledger.publish(InputAttempt.of("orders_raw", PERIOD, "r2", AttemptState.PRODUCED));
        StageGate.Result half = gate.check(publish, UNIT, PERIOD);
        assertThat(half.inputsNotReady()).containsExactly("orders_raw=PENDING (r2)");
        assertThat(half.toString())
                .isEqualTo("Gate closed for task 'publish': inputs not ready: [orders_raw=PENDING (r2)]");

        ledger.publish(InputAttempt.of("orders_raw", PERIOD, "r2", AttemptState.VALIDATED));
        assertThat(gate.check(publish, UNIT, PERIOD).isOpen()).isTrue();
        gate.requireOpen(publish, UNIT, PERIOD);
    }

    @Test
    void aFailedInputKeepsTheGateClosedAndIsNamed() {
        Ledger ledger = new Ledger();
        ledger.declareExpected(UNIT, Set.of("orders_raw"));
        ledger.publish(InputAttempt.of("orders_raw", PERIOD, "r1", AttemptState.FAILED));
        assertThatThrownBy(() -> StageGate.forReadiness(ledger).requireOpen(readyGated("publish"), UNIT, PERIOD))
                .isInstanceOf(IllegalStateException.class)
                .hasMessage("Gate closed for task 'publish': inputs not ready: [orders_raw=FAILED (r1)]");
    }

    @Test
    void readinessIsReadForTheTasksPeriodOnly() {
        Ledger ledger = new Ledger();
        ledger.declareExpected(UNIT, Set.of("orders_raw"));
        ledger.publish(InputAttempt.of("orders_raw", "2026-10-02", "r0", AttemptState.VALIDATED));
        assertThat(StageGate.forReadiness(ledger).check(readyGated("publish"), UNIT, PERIOD).inputsNotReady())
                .containsExactly("orders_raw=MISSING");
    }

    @Test
    void aTaskWithBothKindsIsOpenOnlyWhenBothHoldAndNamesEach() {
        Ledger ledger = new Ledger();
        ledger.declareExpected(UNIT, Set.of("orders_raw"));
        StageGateTest.CompletionsOnly claims = new StageGateTest.CompletionsOnly(new HashSet<>());
        StageGate gate = new StageGate(claims, ledger);
        TaskSpec publish = bothGated("publish");

        assertThat(gate.check(publish, UNIT, PERIOD).toString()).isEqualTo(
                "Gate closed for task 'publish': not completed: [" + new StageKey(UNIT, "load", PERIOD)
                        + "]; inputs not ready: [orders_raw=MISSING]");

        claims.completed.add(new StageKey(UNIT, "load", PERIOD));
        assertThat(gate.check(publish, UNIT, PERIOD).waitingOn()).isEmpty();
        assertThat(gate.check(publish, UNIT, PERIOD).isOpen()).as("inputs still missing").isFalse();

        ledger.publish(InputAttempt.of("orders_raw", PERIOD, "r1", AttemptState.VALIDATED));
        assertThat(gate.check(publish, UNIT, PERIOD).isOpen()).isTrue();
    }

    @Test
    void aGateKindWithNoStoreToReadIsRefusedRatherThanLetThrough() {
        StageGate claimsOnly = new StageGate(new StageGateTest.CompletionsOnly(Set.of()));
        assertThatThrownBy(() -> claimsOnly.check(readyGated("publish"), UNIT, PERIOD))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("'publish'")
                .hasMessageContaining(StageGate.READY);

        StageGate readinessOnly = StageGate.forReadiness(new Ledger());
        assertThatThrownBy(() -> readinessOnly.check(StageGateTest.gated("load_b", new ArrayList<>(List.of("load"))),
                UNIT, PERIOD))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("'load_b'")
                .hasMessageContaining(StageGate.COMPLETED);

        assertThat(readinessOnly.check(task("load", Map.of()), UNIT, PERIOD).isOpen()).isTrue();
    }

    @Test
    void nullStoresAreRefused() {
        assertThatThrownBy(() -> StageGate.forReadiness(null)).isInstanceOf(NullPointerException.class);
        assertThatThrownBy(() -> new StageGate(new StageGateTest.CompletionsOnly(Set.of()), null))
                .isInstanceOf(NullPointerException.class);
        assertThatThrownBy(() -> new StageGate(null, new Ledger())).isInstanceOf(NullPointerException.class);
    }

    @Test
    void theTwoArgumentResultKeepsItsPre230Meaning() {
        assertThat(new StageGate.Result("t", List.of()).isOpen()).isTrue();
        assertThat(new StageGate.Result("t", List.of()).inputsNotReady()).isEmpty();
    }

    // ---------------------------------------------------------------- rendering

    static final StageGateConfig READINESS = StageGateConfig.builder().readinessVariable("PostgresReadiness()").build();

    static DagSpec dag(TaskSpec... tasks) {
        return new DagSpec("orders_daily", "@daily", List.of(tasks), List.of());
    }

    @Test
    void airflowRendersAReadinessGateAsACallableThatReChecksFirst() {
        String out = new AirflowDagRenderer().withStageGate(READINESS)
                .render(dag(task("load", Map.of()), readyGated("publish")));

        assertThat(out).isEqualTo(String.join("\n",
                "from datetime import datetime",
                "from airflow import DAG",
                "from airflow.operators.empty import EmptyOperator",
                "from airflow.exceptions import AirflowException",
                "from airflow.operators.python import PythonOperator",
                "",
                "# Readiness checker: an object with not_ready(unit=, period=) that returns the",
                "# inputs not yet ready, empty only when all are (InputReadiness.readiness, #230).",
                "_input_readiness = PostgresReadiness()",
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
                "        _not_ready = list(_input_readiness.not_ready(unit=context[\"dag\"].dag_id, "
                        + "period=context[\"ds\"]))",
                "        if _not_ready:",
                "            raise AirflowException(",
                "                \"Gate closed for task 'publish': inputs not ready: \" + \", \".join("
                        + "str(_i) for _i in _not_ready)",
                "            )",
                "        pass  # publish task body",
                "    tasks[\"publish\"] = PythonOperator(task_id=\"publish\", python_callable=_callable_publish)",
                ""));
    }

    @Test
    void aTaskWithBothKindsChecksStagesThenInputsAndBothCheckersAreAssigned() {
        StageGateConfig both = StageGateConfig.builder("PostgresStageClaim()")
                .readinessVariable("PostgresReadiness()").build();
        String out = new AirflowDagRenderer().withStageGate(both).render(dag(bothGated("publish")));
        assertThat(out).contains("_stage_gate = PostgresStageClaim()")
                .contains("_input_readiness = PostgresReadiness()");
        assertThat(out.indexOf("_stage_gate.completion(")).isPositive()
                .isLessThan(out.indexOf("_input_readiness.not_ready("));
    }

    @Test
    void aCompletedOnlyDagDoesNotAssignTheReadinessChecker() {
        StageGateConfig both = StageGateConfig.builder("PostgresStageClaim()")
                .readinessVariable("PostgresReadiness()").build();
        String withBoth = new AirflowDagRenderer().withStageGate(both).render(GatedRenderingTest.gatedDag());
        String withChecker = new AirflowDagRenderer().withStageGate(GatedRenderingTest.GATE)
                .render(GatedRenderingTest.gatedDag());
        assertThat(withBoth).isEqualTo(withChecker).doesNotContain("_input_readiness");
    }

    @Test
    void withJobControlTheReadinessCheckComesBeforeAnyJobControlCall() {
        String out = AirflowDagRenderer.withJobControl(
                        JobControlConfig.builder("BigQueryJobControlRepository()").systemId("orders").build())
                .withStageGate(READINESS).render(dag(task("load", Map.of()), readyGated("publish")));
        String publish = out.substring(out.indexOf("def _callable_publish"));
        assertThat(publish.indexOf("_input_readiness.not_ready(")).isPositive()
                .isLessThan(publish.indexOf("run_id = context["));
        String load = out.substring(out.indexOf("def _callable_load"), out.indexOf("def _callable_publish"));
        assertThat(load).doesNotContain("_input_readiness");
        assertThat(out).contains("from airflow.exceptions import AirflowException").doesNotContain("_stage_gate");
    }

    @Test
    void aReadinessGateWithoutAVariableForItIsRefusedNamingTheTask() {
        DagSpec dag = dag(task("load", Map.of()), readyGated("publish"));
        assertThatThrownBy(() -> new AirflowDagRenderer().render(dag))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("'publish'").hasMessageContaining(StageGate.READY);
        assertThatThrownBy(() -> new AirflowDagRenderer().withStageGate(GatedRenderingTest.GATE).render(dag))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("'publish'").hasMessageContaining("readinessVariable");
        assertThatThrownBy(() -> new ComposerDagRenderer(new AirflowDagRenderer().withStageGate(GatedRenderingTest.GATE))
                .render(dag)).isInstanceOf(IllegalArgumentException.class).hasMessageContaining("'publish'");
    }

    @Test
    void aStagesGateWithAReadinessOnlyConfigIsRefusedNamingTheTask() {
        assertThatThrownBy(() -> new AirflowDagRenderer().withStageGate(READINESS).render(GatedRenderingTest.gatedDag()))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("'publish'").hasMessageContaining("checkerVariable");
    }

    @Test
    void theSubstrateRendererRefusesAReadinessGate() {
        for (ExecutionSubstrate s : ExecutionSubstrate.values()) {
            assertThatThrownBy(() -> new SubstrateDagRenderer(s).render(dag(readyGated("publish"))))
                    .isInstanceOf(IllegalArgumentException.class)
                    .hasMessageContaining("'publish'").hasMessageContaining(StageGate.READY);
        }
    }

    @Test
    void aConfigNeedsAtLeastOneChecker() {
        assertThatThrownBy(() -> StageGateConfig.builder().build()).isInstanceOf(IllegalStateException.class);
        assertThatThrownBy(() -> StageGateConfig.builder().readinessVariable(" "))
                .isInstanceOf(IllegalArgumentException.class);
        assertThat(READINESS.checkerVariable()).isNull();
        assertThat(READINESS).isEqualTo(StageGateConfig.builder().readinessVariable("PostgresReadiness()").build())
                .isNotEqualTo(GatedRenderingTest.GATE);
        assertThat(READINESS.toString()).contains("checkerVariable=null")
                .contains("readinessVariable='PostgresReadiness()'");
    }
}
