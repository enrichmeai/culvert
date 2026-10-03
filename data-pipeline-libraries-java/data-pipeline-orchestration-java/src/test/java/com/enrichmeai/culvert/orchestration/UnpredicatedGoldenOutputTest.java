package com.enrichmeai.culvert.orchestration;

import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.MethodSource;

import java.io.IOException;
import java.io.InputStream;
import java.io.Serializable;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;
import java.util.function.Supplier;
import java.util.stream.Stream;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Gate predicates (#197) are additive: a {@link DagSpec} whose tasks carry no gate renders
 * byte-identically to the output before gates existed.
 *
 * <p>The files under {@code src/test/resources/golden/} were written by the renderers as they
 * were on {@code main} at 301b82a, before #197 changed any of them, and committed on their own
 * in 3b87caf. Each renderer, with and without
 * job-control wiring, is compared to its file byte for byte. Never regenerate them to make this
 * test pass: a difference is a change in what an existing user's DAG looks like.
 */
class UnpredicatedGoldenOutputTest {

    /** Fan-out, fan-in, a task id that is not a Python identifier, and non-gate params. */
    static DagSpec airflowSpec() {
        TaskSpec extract = new TaskSpec("extract", "extract", List.of(), Map.of());
        TaskSpec load = new TaskSpec("load-raw", "load-raw", List.of("extract"),
                Map.<String, Serializable>of("table", "raw.orders"));
        TaskSpec validate = new TaskSpec("validate", "validate", List.of("extract"), Map.of());
        TaskSpec publish = new TaskSpec("publish", "publish", List.of("load-raw", "validate"),
                Map.<String, Serializable>of("retries", 3));
        return new DagSpec("orders_daily", "@daily", List.of(extract, load, validate, publish),
                List.of(new DagSpec.Edge("extract", "load-raw"),
                        new DagSpec.Edge("extract", "validate"),
                        new DagSpec.Edge("load-raw", "publish"),
                        new DagSpec.Edge("validate", "publish")));
    }

    static DagSpec podSpec() {
        TaskSpec a = new TaskSpec("ingest", "ingest", List.of(),
                Map.<String, Serializable>of("image", "europe-docker.pkg.dev/p/r/ingest:1"));
        TaskSpec b = new TaskSpec("transform", "transform", List.of("ingest"),
                Map.<String, Serializable>of("image", "europe-docker.pkg.dev/p/r/transform:1"));
        return new DagSpec("orders_pods", null, List.of(a, b),
                List.of(new DagSpec.Edge("ingest", "transform")));
    }

    static DagSpec cloudRunSpec() {
        TaskSpec a = new TaskSpec("ingest", "ingest", List.of(),
                Map.<String, Serializable>of("cloud_run_job", "ingest-job", "region", "europe-west2"));
        return new DagSpec("orders_run", "0 3 * * *", List.of(a), List.of());
    }

    private static JobControlConfig jobControl() {
        return JobControlConfig.builder("BigQueryJobControlRepository()").systemId("orders").build();
    }

    record Case(String file, Supplier<String> render) {
        @Override
        public String toString() {
            return file;
        }
    }

    static Stream<Case> cases() {
        return Stream.of(
                new Case("airflow-plain.py", () -> new AirflowDagRenderer().render(airflowSpec())),
                new Case("airflow-job-control.py",
                        () -> AirflowDagRenderer.withJobControl(jobControl()).render(airflowSpec())),
                new Case("composer-plain.py", () -> new ComposerDagRenderer().render(airflowSpec())),
                new Case("composer-job-control.py",
                        () -> new ComposerDagRenderer(AirflowDagRenderer.withJobControl(jobControl()))
                                .render(airflowSpec())),
                new Case("substrate-composer2.py",
                        () -> new SubstrateDagRenderer(ExecutionSubstrate.COMPOSER_2_GKE_PODS)
                                .render(podSpec())),
                new Case("substrate-composer3.py",
                        () -> new SubstrateDagRenderer(ExecutionSubstrate.COMPOSER_3).render(podSpec())),
                new Case("substrate-cloud-run.py",
                        () -> new SubstrateDagRenderer(ExecutionSubstrate.CLOUD_RUN_JOBS)
                                .render(cloudRunSpec())));
    }

    @ParameterizedTest(name = "{0}")
    @MethodSource("cases")
    void anUnpredicatedSpecRendersExactlyAsBeforeGates(Case c) throws IOException {
        assertThat(c.render().get()).isEqualTo(golden(c.file()));
    }

    private static String golden(String file) throws IOException {
        try (InputStream in = UnpredicatedGoldenOutputTest.class.getResourceAsStream("/golden/" + file)) {
            assertThat(in).as("golden file %s", file).isNotNull();
            return new String(in.readAllBytes(), StandardCharsets.UTF_8);
        }
    }
}
