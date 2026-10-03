package com.enrichmeai.culvert.orchestration;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.MethodSource;
import org.junit.jupiter.params.provider.ValueSource;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.ObjectInputStream;
import java.io.ObjectOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.function.Function;
import java.util.stream.Stream;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * {@code max_concurrency} on a fan-out (#199), per renderer, at 1 (fully sequential) and N.
 *
 * <p>Each expected output is the pinned golden file of the same DAG without a cap
 * ({@link UnpredicatedGoldenOutputTest}), with only the cap's own lines added. So the tests show
 * both the idiom each renderer emits and that nothing else in its output moves.
 */
class MaxConcurrencyTest {

    private static final JobControlConfig JOB_CONTROL =
            JobControlConfig.builder("BigQueryJobControlRepository()").systemId("orders").build();

    static DagSpec capped(DagSpec spec, Integer cap) {
        return new DagSpec(spec.dagId(), spec.schedule(), spec.tasks(), spec.edges(), cap);
    }

    record Case(String golden, DagSpec spec, Function<DagSpec, String> render, boolean pinsDeferrable) {
        @Override
        public String toString() {
            return golden;
        }
    }

    static Stream<Case> renderers() {
        return Stream.of(
                new Case("airflow-plain.py", UnpredicatedGoldenOutputTest.airflowSpec(),
                        s -> new AirflowDagRenderer().render(s), false),
                new Case("airflow-job-control.py", UnpredicatedGoldenOutputTest.airflowSpec(),
                        s -> AirflowDagRenderer.withJobControl(JOB_CONTROL).render(s), false),
                new Case("composer-plain.py", UnpredicatedGoldenOutputTest.airflowSpec(),
                        s -> new ComposerDagRenderer().render(s), false),
                new Case("composer-job-control.py", UnpredicatedGoldenOutputTest.airflowSpec(),
                        s -> new ComposerDagRenderer(AirflowDagRenderer.withJobControl(JOB_CONTROL)).render(s),
                        false),
                new Case("substrate-composer2.py", UnpredicatedGoldenOutputTest.podSpec(),
                        s -> new SubstrateDagRenderer(ExecutionSubstrate.COMPOSER_2_GKE_PODS).render(s), true),
                new Case("substrate-composer3.py", UnpredicatedGoldenOutputTest.podSpec(),
                        s -> new SubstrateDagRenderer(ExecutionSubstrate.COMPOSER_3).render(s), true),
                new Case("substrate-cloud-run.py", UnpredicatedGoldenOutputTest.cloudRunSpec(),
                        s -> new SubstrateDagRenderer(ExecutionSubstrate.CLOUD_RUN_JOBS).render(s), true));
    }

    /** The golden file with the cap's lines added, and nothing else. */
    private static String expected(Case c, int cap) throws IOException {
        List<String> lines = new ArrayList<>(List.of(golden(c.golden()).split("\n", -1)));
        int catchup = lines.indexOf("    catchup=False,");
        assertThat(catchup).as("%s has the DAG kwargs", c.golden()).isPositive();
        lines.add(catchup + 1, "    max_active_tasks=" + cap + ",");
        if (c.pinsDeferrable()) {
            for (int i = 0; i < lines.size(); i++) {
                // Each operator call in a substrate DAG closes with a 4-space ")" line.
                if (lines.get(i).equals("    )")) {
                    lines.add(i, "        deferrable=False,");
                    i++;
                }
            }
        }
        return String.join("\n", lines);
    }

    @ParameterizedTest(name = "{0}")
    @MethodSource("renderers")
    void aCapOfOneRunsTheFanOutOneTaskAtATime(Case c) throws IOException {
        assertThat(c.render().apply(capped(c.spec(), 1))).isEqualTo(expected(c, 1));
    }

    @ParameterizedTest(name = "{0}")
    @MethodSource("renderers")
    void aCapOfNLetsNTasksRunAtOnce(Case c) throws IOException {
        assertThat(c.render().apply(capped(c.spec(), 4))).isEqualTo(expected(c, 4));
    }

    @ParameterizedTest(name = "{0}")
    @MethodSource("renderers")
    void noCapRendersExactlyAsBefore(Case c) throws IOException {
        assertThat(c.render().apply(capped(c.spec(), null))).isEqualTo(golden(c.golden()));
    }

    @Test
    void airflowEmitsTheDagKwargLiterally() {
        String out = new AirflowDagRenderer().render(capped(UnpredicatedGoldenOutputTest.airflowSpec(), 1));
        assertThat(out).contains(String.join("\n",
                "with DAG(",
                "    dag_id=\"orders_daily\",",
                "    schedule=\"@daily\",",
                "    start_date=datetime(2024, 1, 1),",
                "    catchup=False,",
                "    max_active_tasks=1,",
                ") as dag:"));
    }

    @ParameterizedTest
    @ValueSource(ints = {0, -1, Integer.MIN_VALUE})
    void aCapBelowOneIsRejectedAtRenderTimeNamingTheDag(int cap) {
        List<DagRenderer> renderers = List.of(
                new AirflowDagRenderer(),
                AirflowDagRenderer.withJobControl(JOB_CONTROL),
                new ComposerDagRenderer(),
                new SubstrateDagRenderer(ExecutionSubstrate.COMPOSER_2_GKE_PODS));
        DagSpec airflow = capped(UnpredicatedGoldenOutputTest.airflowSpec(), cap);
        DagSpec pods = capped(UnpredicatedGoldenOutputTest.podSpec(), cap);
        for (DagRenderer r : renderers) {
            DagSpec spec = r instanceof SubstrateDagRenderer ? pods : airflow;
            assertThatThrownBy(() -> r.render(spec))
                    .as(r.getClass().getSimpleName())
                    .isInstanceOf(IllegalArgumentException.class)
                    .hasMessageContaining("DAG '" + spec.dagId() + "'")
                    .hasMessageContaining("max_concurrency " + cap)
                    .hasMessageContaining("at least 1");
        }
    }

    @Test
    void theCapIsPartOfTheSpecsValueAndSurvivesSerialization() throws Exception {
        DagSpec plain = UnpredicatedGoldenOutputTest.airflowSpec();
        DagSpec four = capped(plain, 4);
        assertThat(four).isNotEqualTo(plain).isNotEqualTo(capped(plain, 2)).isEqualTo(capped(plain, 4));
        assertThat(capped(plain, null)).isEqualTo(plain).hasSameHashCodeAs(plain);
        assertThat(plain.maxConcurrency()).isNull();
        assertThat(capped(plain, null).toString()).isEqualTo(plain.toString()).doesNotContain("maxConcurrency");
        assertThat(four.toString()).endsWith(", maxConcurrency=4}");

        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        try (ObjectOutputStream out = new ObjectOutputStream(bytes)) {
            out.writeObject(four);
        }
        try (ObjectInputStream in = new ObjectInputStream(new ByteArrayInputStream(bytes.toByteArray()))) {
            DagSpec back = (DagSpec) in.readObject();
            assertThat(back).isEqualTo(four);
            assertThat(back.maxConcurrency()).isEqualTo(4);
        }
    }

    private static String golden(String file) throws IOException {
        try (InputStream in = MaxConcurrencyTest.class.getResourceAsStream("/golden/" + file)) {
            assertThat(in).as("golden file %s", file).isNotNull();
            return new String(in.readAllBytes(), StandardCharsets.UTF_8);
        }
    }
}
