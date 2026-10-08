package com.enrichmeai.culvert.e2e.proof;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/** The Composer runner (#234) against a stand-in gcloud that prints the arguments it was given. */
class AirflowRunnerComposerTest {

    private static final String DAG = "reference_e2e_control_plane";
    private static final String NEW = "dag = 'the uploaded version'\n";
    private static final String OLD = "dag = 'an earlier version'\n";

    @TempDir
    Path dir;

    private Path stores;
    private Path dag;

    @BeforeEach
    void files() throws IOException {
        stores = Files.writeString(dir.resolve("reference_e2e_control_plane_stores.py"), "STORES = 1\n");
        dag = Files.writeString(dir.resolve(DAG + ".py"), NEW);
    }

    private Path fakeGcloud(String body) throws IOException {
        Path gcloud = dir.resolve("gcloud");
        Files.writeString(gcloud, "#!/bin/sh\n" + body + "\n");
        assertThat(gcloud.toFile().setExecutable(true)).isTrue();
        return gcloud;
    }

    private AirflowRunner.Composer composer(Path gcloud, AirflowState state) {
        return new AirflowRunner.Composer(gcloud.toString(), "ref-e2e-composer", "europe-west2",
                List.of(stores, dag), DAG, state, 2, 50);
    }

    @Test
    void anAirflowCommandIsPassedAfterTheDoubleDash() throws IOException {
        Proc p = composer(fakeGcloud("echo \"$@\""), parses(0, NEW))
                .run("t", "tasks", "test", DAG, "orders__validate", "2025-01-04");
        assertThat(p.waitFor(30)).isZero();
        assertThat(p.out().strip()).isEqualTo("composer environments run ref-e2e-composer --location=europe-west2 "
                + "tasks test -- " + DAG + " orders__validate 2025-01-04");
    }

    @Test
    void aCommandWithNoArgumentsHasNoDoubleDash() throws IOException {
        Proc p = composer(fakeGcloud("echo \"$@\""), parses(0, NEW)).run("t", "dags", "list");
        p.waitFor(30);
        assertThat(p.out().strip()).isEqualTo("composer environments run ref-e2e-composer --location=europe-west2 dags list");
    }

    @Test
    void setupUploadsTheStoresThenTheDagThenWaitsUntilAirflowParsedTheUploadedDag() throws IOException {
        Path log = dir.resolve("calls");
        AtomicInteger looks = new AtomicInteger();
        // Not registered, then the earlier version, then the uploaded one.
        composer(fakeGcloud("echo \"$@\" >> " + log), state(looks, null, OLD, NEW)).setup();
        assertThat(Files.readAllLines(log)).containsExactly(
                "composer environments storage dags import --environment=ref-e2e-composer --location=europe-west2 "
                        + "--source=" + stores,
                "composer environments storage dags import --environment=ref-e2e-composer --location=europe-west2 "
                        + "--source=" + dag);
        assertThat(looks.get()).isEqualTo(3);
    }

    @Test
    void aFailingApiDuringTheWaitIsRetriedUntilTheDeadline() throws IOException {
        AtomicInteger looks = new AtomicInteger();
        AirflowState flaky = new FakeState(() -> {
            if (looks.incrementAndGet() <= 2) {
                throw new IllegalStateException("GET .../dags/x -> 503: restarting");
            }
            return NEW;
        });
        composer(fakeGcloud("true"), flaky).setup();
        assertThat(looks.get()).isEqualTo(3);

        AirflowState down = new FakeState(() -> {
            throw new IllegalStateException("GET .../dags/x -> 503: restarting");
        });
        assertThatThrownBy(() -> composer(fakeGcloud("true"), down).setup())
                .hasMessageContaining("the last call failed: GET .../dags/x -> 503");
    }

    @Test
    void aFailedUploadStopsTheSetup() throws IOException {
        assertThatThrownBy(() -> composer(fakeGcloud("echo PERMISSION_DENIED; exit 1"), parses(0, NEW)).setup())
                .hasMessageContaining("uploading " + stores + " failed").hasMessageContaining("PERMISSION_DENIED");
    }

    @Test
    void anEarlierVersionThatStaysRegisteredFailsAfterTheWaitAndSaysSo() throws IOException {
        assertThatThrownBy(() -> composer(fakeGcloud("true"), parses(Integer.MAX_VALUE, NEW)).setup())
                .hasMessageContaining("did not parse the uploaded file within 2s")
                .hasMessageContaining("it still runs an earlier version")
                .hasMessageContaining("ModuleNotFoundError");
    }

    @Test
    void itsExitCodeIsNotTakenAsTheAirflowCommands() throws IOException {
        assertThat(composer(fakeGcloud("true"), parses(0, NEW)).exitCodeIsTheCommands()).isFalse();
        assertThat(composer(fakeGcloud("true"), parses(0, NEW)).startScheduler(java.util.Map.of())).isNull();
    }

    /** Airflow serves the earlier version for {@code n} looks, then {@code source}. */
    private static AirflowState parses(int n, String source) {
        AtomicInteger looks = new AtomicInteger();
        return new FakeState(() -> looks.incrementAndGet() > n ? source : OLD);
    }

    /** Airflow serves each of {@code sources} in turn, the last one from then on. */
    private static AirflowState state(AtomicInteger looks, String... sources) {
        return new FakeState(() -> sources[Math.min(looks.getAndIncrement(), sources.length - 1)]);
    }

    private record FakeState(java.util.function.Supplier<String> sources) implements AirflowState {
        public String describe() {
            return "test state";
        }

        public String source(String dagId) {
            return sources.get();
        }

        public List<String> importErrors(String dagId) {
            return List.of(dagId + ".py: ModuleNotFoundError (an earlier upload's)");
        }

        public Boolean paused(String dagId) {
            return null;
        }

        public List<String> active(String dagId) {
            return List.of();
        }

        public String runState(String dagId, String runId) {
            return null;
        }

        public List<String> taskStates(String dagId, String runId) {
            return List.of();
        }
    }
}
