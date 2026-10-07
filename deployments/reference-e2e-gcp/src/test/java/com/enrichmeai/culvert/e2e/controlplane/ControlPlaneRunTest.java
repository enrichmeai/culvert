package com.enrichmeai.culvert.e2e.controlplane;

import com.enrichmeai.culvert.e2e.controlplane.ControlPlaneRun.Outcome;
import com.enrichmeai.culvert.e2e.controlplane.ControlPlaneRun.Report;
import com.enrichmeai.culvert.e2e.controlplane.ControlPlaneRun.StageResult;
import com.enrichmeai.culvert.contracts.InputReadiness;
import com.enrichmeai.culvert.readiness.InputAttempt;
import com.enrichmeai.culvert.readiness.Readiness;
import com.enrichmeai.culvert.stageclaim.Claim;
import com.enrichmeai.culvert.stageclaim.ClaimResult;
import com.enrichmeai.culvert.stageclaim.StageKey;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import javax.sql.DataSource;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * The fan-out on a real PostgreSQL 16 (#231). Every assertion reads the control store's own
 * tables, not the runner's word for it.
 */
class ControlPlaneRunTest {

    static final String PERIOD = "2026-10-06";
    static final List<String> UNITS = List.of("orders", "customers", "products");

    DataSource db;
    ControlPlane stores;

    @BeforeEach
    void freshStore() {
        db = EmbeddedControlStore.fresh();
        stores = EmbeddedControlStore.stores(db);
    }

    ControlPlaneRun run(List<String> stages, Faults faults) {
        return new ControlPlaneRun(stores, UNITS, PERIOD, stages, 2, 5, faults, () -> {
            throw new AssertionError("no kill was asked for");
        });
    }

    ControlPlaneRun run() {
        return run(ControlPlaneRun.STAGES, Faults.NONE);
    }

    List<String> completions() {
        return EmbeddedControlStore.rows(db,
                "SELECT unit, stage, period FROM job_control.stage_completions ORDER BY unit, stage");
    }

    /** Each job-control run's current state: entity, status, records, failure. */
    List<String> runs() {
        return EmbeddedControlStore.rows(db, "SELECT DISTINCT ON (run_id) entity_type, status, record_count, "
                + "coalesce(error_code, '-') FROM job_control.pipeline_jobs ORDER BY run_id, seq DESC")
                .stream().sorted().toList();
    }

    String readiness(String unit) {
        return stores.readiness().readiness(unit, PERIOD).inputs().toString();
    }

    @Test
    void everyStageOfEveryUnitRunsOnceAndEachUnitRecordsOneSucceededRun() {
        Report report = run().run("worker-a");

        assertThat(report.exitCode()).isZero();
        assertThat(report.results()).hasSize(9).allMatch(r -> r.outcome() == Outcome.DONE);
        assertThat(completions()).containsExactly(
                "customers|load|2026-10-06", "customers|publish|2026-10-06", "customers|validate|2026-10-06",
                "orders|load|2026-10-06", "orders|publish|2026-10-06", "orders|validate|2026-10-06",
                "products|load|2026-10-06", "products|publish|2026-10-06", "products|validate|2026-10-06");
        assertThat(runs()).containsExactly("customers|succeeded|15|-", "orders|succeeded|15|-",
                "products|succeeded|15|-");
        for (String unit : UNITS) {
            assertThat(stores.readiness().readiness(unit, PERIOD).isReady()).as(unit).isTrue();
            assertThat(stores.readiness().expected(unit)).containsExactly(unit + ".raw");
        }
    }

    @Test
    void aSecondRunSkipsEveryCompletedStageAndWritesNoJobControlRow() {
        run().run("worker-a");
        Report again = run().run("worker-b");

        assertThat(again.exitCode()).isZero();
        assertThat(again.results()).allMatch(r -> r.outcome() == Outcome.SKIPPED
                && r.detail().equals("completed by worker-a"));
        assertThat(runs()).hasSize(3);
    }

    @Test
    void aStageHeldByAnotherClaimantStopsThatUnitAndTheRunExitsTwo() {
        StageKey key = new StageKey("orders", ControlPlaneRun.LOAD, PERIOD);
        try (Claim held = ((ClaimResult.Acquired) stores.claims().tryClaim(key, "worker-x", Duration.ZERO)).claim()) {
            Report report = run().run("worker-a");

            assertThat(report.exitCode()).isEqualTo(2);
            assertThat(report.of("orders", ControlPlaneRun.LOAD)).extracting(StageResult::outcome)
                    .containsExactly(Outcome.HELD);
            assertThat(report.of("orders", ControlPlaneRun.VALIDATE)).isEmpty();
            assertThat(runs()).as("orders acquired nothing, so it wrote no run")
                    .containsExactly("customers|succeeded|15|-", "products|succeeded|15|-");
            assertThat(held.claimant()).isEqualTo("worker-x");
        }
    }

    /** Proof 1's shape: the same units, stages and period triggered twice at once. */
    @Test
    void aDuplicateTriggerDoesEachStageExactlyOnce() {
        Faults duplicate = new Faults(null, ControlPlaneRun.VALIDATE, Set.of(), true);
        Report report = run(ControlPlaneRun.STAGES, duplicate).run("worker");

        for (String unit : UNITS) {
            for (String stage : ControlPlaneRun.STAGES) {
                assertThat(report.of(unit, stage).stream().filter(r -> r.outcome() == Outcome.DONE))
                        .as(unit + "/" + stage + " done by exactly one trigger").hasSize(1);
            }
        }
        assertThat(report.results()).extracting(StageResult::outcome)
                .allMatch(o -> o == Outcome.DONE || o == Outcome.SKIPPED || o == Outcome.HELD);
        assertThat(completions()).hasSize(9);
        assertThat(EmbeddedControlStore.rows(db, "SELECT count(*) FROM job_control.readiness_attempts "
                + "WHERE state = 'produced'")).as("each input produced once").containsExactly("3");
    }

    /** Proof 4's shape: publish fired before anything upstream ran. */
    @Test
    void publishFiredEarlyIsStoppedByItsGateNamingStagesAndInputs() {
        Report report = run(List.of(ControlPlaneRun.PUBLISH), Faults.NONE).run("worker-a");

        assertThat(report.exitCode()).isEqualTo(1);
        assertThat(report.results()).hasSize(3).allMatch(r -> r.outcome() == Outcome.GATE_CLOSED);
        assertThat(report.of("orders", ControlPlaneRun.PUBLISH).get(0).detail())
                .isEqualTo("Gate closed for task 'orders__publish': not completed: ["
                        + new StageKey("orders", "load", PERIOD) + ", " + new StageKey("orders", "validate", PERIOD)
                        + "]; inputs not ready: [orders.raw=MISSING]");
        assertThat(completions()).isEmpty();
        assertThat(runs()).as("a closed gate starts no run").isEmpty();

        assertThat(run().run("worker-a").exitCode()).isZero();
        assertThat(completions()).hasSize(9);
    }

    /** Proof 5's shape: a failed input keeps publish shut; only a declared retry reopens it. */
    @Test
    void aFailedValidationKeepsThatUnitShutUntilARetryValidatesIt() {
        Faults failCustomers = new Faults(null, ControlPlaneRun.VALIDATE, Set.of("customers"), false);
        Report report = run(ControlPlaneRun.STAGES, failCustomers).run("worker-a");

        assertThat(report.exitCode()).isEqualTo(1);
        assertThat(report.of("customers", ControlPlaneRun.VALIDATE)).extracting(StageResult::outcome)
                .containsExactly(Outcome.FAILED);
        assertThat(report.of("customers", ControlPlaneRun.PUBLISH)).isEmpty();
        String failedRun = report.of("customers", ControlPlaneRun.LOAD).get(0).runId();
        assertThat(readiness("customers")).isEqualTo("[customers.raw=FAILED (" + failedRun + ")]");
        assertThat(runs()).contains("customers|failed|0|INPUT_INVALID", "orders|succeeded|15|-");

        // Fired on its own, publish is stopped by its gate: validate is not completed, the input failed.
        Report early = run(List.of(ControlPlaneRun.PUBLISH), Faults.NONE).run("worker-b");
        assertThat(early.of("customers", ControlPlaneRun.PUBLISH).get(0).detail())
                .contains("not completed: [" + new StageKey("customers", "validate", PERIOD) + "]")
                .contains("inputs not ready: [customers.raw=FAILED (" + failedRun + ")]");

        Report retry = run().run("worker-c");
        assertThat(retry.exitCode()).isZero();
        assertThat(retry.of("customers", ControlPlaneRun.LOAD)).extracting(StageResult::outcome)
                .containsExactly(Outcome.SKIPPED);
        assertThat(retry.of("customers", ControlPlaneRun.VALIDATE)).extracting(StageResult::outcome)
                .containsExactly(Outcome.DONE);
        assertThat(retry.of("customers", ControlPlaneRun.PUBLISH)).extracting(StageResult::outcome)
                .containsExactly(Outcome.DONE);
        String retryRun = retry.of("customers", ControlPlaneRun.VALIDATE).get(0).runId();
        assertThat(EmbeddedControlStore.rows(db, "SELECT run_id, state, coalesce(retry_of, '-') "
                + "FROM job_control.readiness_attempts WHERE input = 'customers.raw' ORDER BY seq"))
                .containsExactly(failedRun + "|produced|-", failedRun + "|failed|-",
                        retryRun + "|validated|" + failedRun);
        assertThat(stores.readiness().readiness("customers", PERIOD).isReady()).isTrue();
    }

    @Test
    void anUnknownStageOrABadPeriodIsRefusedBeforeAnythingRuns() {
        assertThatThrownBy(() -> run(List.of("transform"), Faults.NONE))
                .isInstanceOf(IllegalArgumentException.class).hasMessageContaining("'transform'");
        assertThatThrownBy(() -> new ControlPlaneRun(stores, UNITS, "06/10/2026", ControlPlaneRun.STAGES, 2, 5,
                Faults.NONE, () -> { })).isInstanceOf(java.time.format.DateTimeParseException.class);
        assertThat(completions()).isEmpty();
    }

    @Test
    void aKillThatCouldNeverFireIsRefused() {
        Faults tooLate = new Faults(6, ControlPlaneRun.VALIDATE, Set.of(), false);
        assertThatThrownBy(() -> run(ControlPlaneRun.STAGES, tooLate))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("--fault.kill-after=6 is more than --records=5, so the kill would never happen");
    }

    /** The in-process stand-in for a halted JVM: it unwinds without any of the run's own handling. */
    static final class Killed extends Error {
        private static final long serialVersionUID = 1L;
    }

    @Test
    void aKillAfterTheLastRecordStillFiresBeforeTheStageIsRecorded() {
        Faults atEnd = new Faults(5, ControlPlaneRun.LOAD, Set.of(), false);
        ControlPlaneRun run = new ControlPlaneRun(stores, List.of("orders"), PERIOD, ControlPlaneRun.STAGES, 1, 5,
                atEnd, () -> {
                    throw new Killed();
                });
        assertThatThrownBy(() -> run.run("worker-a")).isInstanceOf(Killed.class);
        assertThat(completions()).isEmpty();
        assertThat(readiness("orders")).as("killed before the input was published").isEqualTo("[orders.raw=MISSING]");
    }

    @Test
    void anUnexpectedStoreErrorFailsTheRunInsteadOfLeavingItRunning() {
        InputReadiness real = stores.readiness();
        InputReadiness broken = new InputReadiness() {
            @Override public void declareExpected(String unit, Set<String> inputs) {
                real.declareExpected(unit, inputs);
            }
            @Override public void declareExpected(String unit, String period, Set<String> inputs) {
                real.declareExpected(unit, period, inputs);
            }
            @Override public Set<String> expected(String unit) {
                return real.expected(unit);
            }
            @Override public Set<String> expected(String unit, String period) {
                return real.expected(unit, period);
            }
            @Override public void publish(InputAttempt attempt) {
                throw new IllegalStateException("connection reset");
            }
            @Override public Readiness readiness(String unit, String period) {
                return real.readiness(unit, period);
            }
        };
        ControlPlaneRun run = new ControlPlaneRun(new ControlPlane(stores.jobControl(), stores.claims(), broken),
                List.of("orders"), PERIOD, ControlPlaneRun.STAGES, 1, 5, Faults.NONE, () -> { });

        assertThatThrownBy(() -> run.run("worker-a")).hasMessageContaining("connection reset");
        assertThat(runs()).containsExactly("orders|failed|0|STAGE_ERROR");
        assertThat(completions()).as("the claim was released, not completed").isEmpty();
    }

    @Test
    void theStoresAreFoundThroughAutoConfigFromTheSettings() {
        Map<String, String> settings = Map.of("culvert.postgres.url", EmbeddedControlStore.url(),
                "culvert.postgres.user", "postgres",
                "culvert.jobcontrolrepository.provider", "PostgresJobControlRepository");
        settings.forEach(System::setProperty);
        try {
            ControlPlane found = ControlPlane.discover(com.enrichmeai.culvert.autoconfig.AutoConfig.discover());
            assertThat(found.jobControl().getClass().getSimpleName()).isEqualTo("PostgresJobControlRepository");
            assertThat(found.claims().getClass().getSimpleName()).isEqualTo("PostgresStageClaim");
            assertThat(found.readiness().getClass().getSimpleName()).isEqualTo("PostgresReadiness");
        } finally {
            settings.keySet().forEach(System::clearProperty);
        }
    }
}
