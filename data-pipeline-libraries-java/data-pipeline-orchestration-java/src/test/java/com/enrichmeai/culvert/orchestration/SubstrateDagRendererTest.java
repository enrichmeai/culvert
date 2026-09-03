package com.enrichmeai.culvert.orchestration;

import org.junit.jupiter.api.Test;

import java.io.Serializable;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * The substrate must be a configuration choice, not a constant: the same
 * {@link DagSpec} has to render for Composer 2 + GKE pods (GCP 1.0 / CNE),
 * Composer 3, and Cloud Run jobs (GCP 2.0) with no change to the pipeline.
 */
class SubstrateDagRendererTest {

    private static DagSpec podSpec() {
        return new DagSpec("ingest_dag", "@daily",
                List.of(new TaskSpec("ingest", "ingest", List.of(),
                        Map.of("image", "gcr.io/proj/ingestion:1.0.0"))),
                List.of());
    }

    private static DagSpec cloudRunSpec() {
        return new DagSpec("ingest_dag", "@daily",
                List.of(new TaskSpec("ingest", "ingest", List.of(),
                        Map.of("cloud_run_job", "generic-ingestion", "region", "europe-west2"))),
                List.of());
    }

    @Test
    void composer2RendersAPodOperatorAgainstTheEnvironmentCluster() {
        String dag = new SubstrateDagRenderer(ExecutionSubstrate.COMPOSER_2_GKE_PODS)
                .render(podSpec());

        assertThat(dag)
                .contains("KubernetesPodOperator")
                .contains("config_file=\"/home/airflow/composer_kube_config\"")
                .contains("composer-2-airflow-2")
                .contains("image=\"gcr.io/proj/ingestion:1.0.0\"");
    }

    @Test
    void composer3RendersTheSamePodOperatorIdiom() {
        // The point of the Composer 3 research: the operator and the
        // config_file path are UNCHANGED from Composer 2, despite the cluster
        // moving into the tenant project. If this ever diverges, the two
        // substrates need separate renderers and this test should fail first.
        String dag = new SubstrateDagRenderer(ExecutionSubstrate.COMPOSER_3).render(podSpec());

        assertThat(dag)
                .contains("KubernetesPodOperator")
                .contains("config_file=\"/home/airflow/composer_kube_config\"")
                .contains("composer-3-airflow-2");
    }

    @Test
    void composer3PinsPodsToTheComposerUserWorkloadsNamespace() {
        String dag = new SubstrateDagRenderer(ExecutionSubstrate.COMPOSER_3).render(podSpec());

        assertThat(dag).contains("namespace=\"composer-user-workloads\"");
    }

    @Test
    void composer3RefusesACustomNamespaceRatherThanSilentlyIgnoringIt() {
        DagSpec spec = new DagSpec("ingest_dag", "@daily",
                List.of(new TaskSpec("ingest", "ingest", List.of(),
                        Map.of("image", "img", "namespace", "my-team"))),
                List.of());

        // Composer 3 runs the pod in composer-user-workloads regardless. A DAG
        // that passed the namespace through would deploy, run, and quietly put
        // the workload elsewhere — a production-only surprise.
        assertThatThrownBy(() -> new SubstrateDagRenderer(ExecutionSubstrate.COMPOSER_3)
                .render(spec))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("composer-user-workloads")
                .hasMessageContaining("silently ignores");
    }

    @Test
    void composer2AllowsACustomNamespaceBecauseTheClusterIsTheUsers() {
        DagSpec spec = new DagSpec("ingest_dag", "@daily",
                List.of(new TaskSpec("ingest", "ingest", List.of(),
                        Map.of("image", "img", "namespace", "my-team"))),
                List.of());

        assertThat(new SubstrateDagRenderer(ExecutionSubstrate.COMPOSER_2_GKE_PODS).render(spec))
                .contains("namespace=\"my-team\"");
    }

    @Test
    void composer3RejectsMoreThanOneSidecar() {
        Map<String, Serializable> params = Map.of("image", "img", "sidecars", 2);
        DagSpec spec = new DagSpec("ingest_dag", "@daily",
                List.of(new TaskSpec("ingest", "ingest", List.of(), params)), List.of());

        assertThatThrownBy(() -> new SubstrateDagRenderer(ExecutionSubstrate.COMPOSER_3)
                .render(spec))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("airflow-xcom-sidecar");
    }

    @Test
    void cloudRunRendersACloudRunJobOperatorInstead() {
        String dag = new SubstrateDagRenderer(ExecutionSubstrate.CLOUD_RUN_JOBS)
                .render(cloudRunSpec());

        assertThat(dag)
                .contains("CloudRunExecuteJobOperator")
                .contains("job_name=\"generic-ingestion\"")
                .contains("region=\"europe-west2\"")
                .doesNotContain("KubernetesPodOperator");
        // The GCP 1.0 / CNE constraint is recorded in the artefact itself, so
        // an operator reading the DAG sees it without consulting a doc.
        assertThat(dag).contains("Cloud Run is NOT available on GCP 1.0 / CNE");
    }

    @Test
    void theSamePipelineRendersForEverySubstrateWithNoPipelineChange() {
        // The headline requirement: substrate selected by configuration alone.
        for (ExecutionSubstrate substrate : ExecutionSubstrate.values()) {
            DagSpec spec = substrate.launchesPods() ? podSpec() : cloudRunSpec();
            assertThat(new SubstrateDagRenderer(substrate).render(spec))
                    .as("substrate %s", substrate)
                    .contains("dag_id=\"ingest_dag\"")
                    .contains("task_id=\"ingest\"");
        }
    }

    @Test
    void substrateIsResolvedFromHumanEditedConfigText() {
        assertThat(ExecutionSubstrate.fromConfig("composer-3"))
                .isEqualTo(ExecutionSubstrate.COMPOSER_3);
        assertThat(ExecutionSubstrate.fromConfig("COMPOSER_2_GKE_PODS"))
                .isEqualTo(ExecutionSubstrate.COMPOSER_2_GKE_PODS);
        assertThat(ExecutionSubstrate.fromConfig("  cloud-run-jobs "))
                .isEqualTo(ExecutionSubstrate.CLOUD_RUN_JOBS);
    }

    @Test
    void anUnknownSubstrateNamesTheValidOnes() {
        assertThatThrownBy(() -> ExecutionSubstrate.fromConfig("composer-4"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("COMPOSER_3")
                .hasMessageContaining("CLOUD_RUN_JOBS");
    }

    @Test
    void aPodTaskWithoutAnImageIsRefused() {
        DagSpec spec = new DagSpec("d", null,
                List.of(new TaskSpec("t", "t", List.of(), Map.of())), List.of());

        assertThatThrownBy(() -> new SubstrateDagRenderer(ExecutionSubstrate.COMPOSER_2_GKE_PODS)
                .render(spec))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("image");
    }
}
