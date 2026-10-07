package com.enrichmeai.culvert.e2e.controlplane;

import org.junit.jupiter.api.Test;

import javax.sql.DataSource;
import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.TimeUnit;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Proof 2's shape with a real kill (#231): {@link ControlPlaneMain} runs in its own JVM, which halts
 * partway through stage 2 of 3 with no cleanup. Its PostgreSQL session dies with it, so its claim
 * is released by the server, not by the worker. The re-run then picks up exactly where it stopped.
 */
class KilledWorkerTest {

    static final String PERIOD = "2026-10-06";

    /** Run {@link ControlPlaneMain} in a new JVM; returns its exit code and output. */
    static Result main(String... args) throws IOException, InterruptedException {
        List<String> command = new ArrayList<>(List.of(
                ProcessHandle.current().info().command().orElse("java"),
                "-cp", System.getProperty("surefire.test.class.path", System.getProperty("java.class.path")),
                "-Dculvert.postgres.url=" + EmbeddedControlStore.url(),
                "-Dculvert.postgres.user=postgres",
                "-Dculvert.jobcontrolrepository.provider=PostgresJobControlRepository",
                "-Dorg.slf4j.simpleLogger.defaultLogLevel=warn",
                ControlPlaneMain.class.getName()));
        command.addAll(List.of(args));
        Process p = new ProcessBuilder(command).redirectErrorStream(true).start();
        String out = new String(p.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
        assertThat(p.waitFor(120, TimeUnit.SECONDS)).as("worker finished").isTrue();
        return new Result(p.exitValue(), out);
    }

    record Result(int exit, String out) {
        List<String> lines(String prefix) {
            return out.lines().filter(l -> l.startsWith(prefix)).toList();
        }
    }

    @Test
    void aWorkerKilledInStageTwoResumesWithoutRedoingStageOne() throws Exception {
        DataSource db = EmbeddedControlStore.fresh();
        String[] common = {"--period=" + PERIOD, "--units=orders,customers", "--max-concurrency=1", "--records=5"};

        Result killed = main(concat(common, "--claimant=worker-1", "--fault.kill-after=2"));
        assertThat(killed.exit()).as(killed.out()).isEqualTo(137);
        assertThat(killed.out()).contains("KILLED (fault.kill-after)");
        assertThat(EmbeddedControlStore.rows(db,
                "SELECT unit, stage, completed_by FROM job_control.stage_completions ORDER BY unit, stage"))
                .as("only orders/load finished before the kill").containsExactly("orders|load|worker-1");
        assertThat(EmbeddedControlStore.rows(db, "SELECT DISTINCT ON (run_id) entity_type, status "
                + "FROM job_control.pipeline_jobs ORDER BY run_id, seq DESC"))
                .as("the killed run is left running: nothing marked it, as nothing would")
                .containsExactly("orders|running");

        Result resumed = main(concat(common, "--claimant=worker-2"));
        assertThat(resumed.exit()).as(resumed.out()).isZero();
        assertThat(resumed.lines("orders/")).containsExactly(
                "orders/load SKIPPED claimant=worker-2 :: completed by worker-1",
                resumed.lines("orders/validate").get(0),
                resumed.lines("orders/publish").get(0));
        assertThat(resumed.lines("orders/validate").get(0)).startsWith("orders/validate DONE claimant=worker-2")
                .endsWith("records=5");
        assertThat(resumed.lines("orders/publish").get(0)).startsWith("orders/publish DONE claimant=worker-2");
        assertThat(resumed.lines("customers/")).hasSize(3).allMatch(l -> l.contains(" DONE claimant=worker-2"));
        assertThat(EmbeddedControlStore.rows(db,
                "SELECT unit, stage, completed_by FROM job_control.stage_completions ORDER BY unit, stage"))
                .containsExactly("customers|load|worker-2", "customers|publish|worker-2",
                        "customers|validate|worker-2", "orders|load|worker-1", "orders|publish|worker-2",
                        "orders|validate|worker-2");
        assertThat(EmbeddedControlStore.rows(db, "SELECT count(*) FROM job_control.readiness_attempts "
                + "WHERE input = 'orders.raw' AND state = 'produced'")).as("orders was loaded once")
                .containsExactly("1");
    }

    @Test
    void aBadArgumentExitsSixtyFour() throws Exception {
        EmbeddedControlStore.fresh();
        Result bad = main("--period=" + PERIOD, "--records=many");
        assertThat(bad.exit()).isEqualTo(64);
        assertThat(bad.out()).contains("--records must be a number, got 'many'");
    }

    private static String[] concat(String[] a, String... b) {
        String[] out = new String[a.length + b.length];
        System.arraycopy(a, 0, out, 0, a.length);
        System.arraycopy(b, 0, out, a.length, b.length);
        return out;
    }
}
