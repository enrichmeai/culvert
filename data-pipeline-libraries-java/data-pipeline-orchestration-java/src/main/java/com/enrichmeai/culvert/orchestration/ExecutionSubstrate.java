package com.enrichmeai.culvert.orchestration;

/**
 * Where a rendered DAG's tasks actually execute.
 *
 * <p>The substrate is a <strong>configuration choice, not a constant</strong>.
 * Two consumers of the same pipeline run on different platforms and the
 * pipeline code must not change between them:
 *
 * <ul>
 *   <li><strong>GCP 1.0 / CNE</strong> — Composer 2 and GKE pods.
 *       <em>No Cloud Run.</em> This is where the existing CDP pipelines run,
 *       so {@link #CLOUD_RUN_JOBS} must remain un-selectable there.</li>
 *   <li><strong>GCP 2.0</strong> — the newer landing zone, where Cloud Run and
 *       Composer 3 are available. The demo target.</li>
 * </ul>
 *
 * <h2>What the research changed about this design</h2>
 * <p>The obvious assumption is that Composer 3 needs a different task pattern
 * from Composer 2, because Composer 3 no longer exposes the GKE cluster. It
 * does not. Per Google's
 * <a href="https://docs.cloud.google.com/composer/docs/composer-3/use-kubernetes-pod-operator">Composer
 * 3 KubernetesPodOperator documentation</a>, {@code KubernetesPodOperator} is
 * fully supported on Composer 3 and uses the <em>same</em>
 * {@code config_file="/home/airflow/composer_kube_config"} idiom as Composer 2.
 *
 * <p>So {@link #COMPOSER_2_GKE_PODS} and {@link #COMPOSER_3} are one task
 * pattern under two <em>constraint profiles</em>, not two patterns — which is
 * why this is an enum carrying constraints rather than two renderers.
 * {@link #CLOUD_RUN_JOBS} genuinely is a different pattern
 * ({@code CloudRunExecuteJobOperator}), so it gets different emission.
 *
 * <p>The Composer 3 constraints below are real and enforced at render time,
 * because each one fails at DAG-run time on the cluster rather than at deploy
 * time — a silent-until-production failure is exactly what a renderer should
 * catch.
 */
public enum ExecutionSubstrate {

    /**
     * Cloud Composer 2, launching pods on the environment's GKE cluster.
     *
     * <p>The cluster lives in the user's own project, so any namespace they
     * have created is addressable and pods are configured freely.
     */
    COMPOSER_2_GKE_PODS(
            "composer-2-airflow-2",
            /* podNamespace */ null,
            /* allowsCustomNamespace */ true,
            /* maxSidecars */ Integer.MAX_VALUE,
            /* supportsKubernetesSecretsApi */ true),

    /**
     * Cloud Composer 3 (branded "Managed Airflow Gen 3" in Google's docs).
     *
     * <p>The environment's cluster is in the <em>tenant</em> project —
     * <q>it's not possible to configure it</q> — and the constraints that
     * follow from that are enforced rather than discovered in production:
     * <ul>
     *   <li>Pods <q>always run in the {@code composer-user-workloads}
     *       namespace, even if a different namespace is specified</q>. Silently
     *       ignoring a requested namespace is worse than refusing it.</li>
     *   <li>At most one extra sidecar, and only if named
     *       {@code airflow-xcom-sidecar}.</li>
     *   <li>Secrets and ConfigMaps <q>can't be created using Kubernetes
     *       API</q> — they come from gcloud, Terraform, or the Composer API.</li>
     * </ul>
     *
     * <p>Note on versions: Composer 3 offers <em>both</em> Airflow 2 and
     * Airflow 3, and Airflow 3 still carries documented gaps (upgrades via
     * snapshots and in-place upgrades are "not yet supported"). The image
     * family here is therefore the Airflow 2 line — the conservative default
     * for a deployment that must simply work. Composer 3 is evergreen, so the
     * image family matters far less than it did on Composer 2.
     */
    COMPOSER_3(
            "composer-3-airflow-2",
            /* podNamespace */ "composer-user-workloads",
            /* allowsCustomNamespace */ false,
            /* maxSidecars */ 1,
            /* supportsKubernetesSecretsApi */ false),

    /**
     * Cloud Run jobs, triggered from Airflow via
     * {@code CloudRunExecuteJobOperator}.
     *
     * <p>Not available on GCP 1.0 / CNE. A deployment targeting that landing
     * zone must fail closed rather than render a DAG that cannot run there;
     * see {@code deployments/data-pipeline-orchestrator/terraform}, which
     * refuses this substrate unless Cloud Run is declared available.
     */
    CLOUD_RUN_JOBS(
            /* composerImageVersion */ null,
            /* podNamespace */ null,
            /* allowsCustomNamespace */ false,
            /* maxSidecars */ 0,
            /* supportsKubernetesSecretsApi */ false);

    private final String composerImageVersion;
    private final String podNamespace;
    private final boolean allowsCustomNamespace;
    private final int maxSidecars;
    private final boolean supportsKubernetesSecretsApi;

    ExecutionSubstrate(String composerImageVersion,
                       String podNamespace,
                       boolean allowsCustomNamespace,
                       int maxSidecars,
                       boolean supportsKubernetesSecretsApi) {
        this.composerImageVersion = composerImageVersion;
        this.podNamespace = podNamespace;
        this.allowsCustomNamespace = allowsCustomNamespace;
        this.maxSidecars = maxSidecars;
        this.supportsKubernetesSecretsApi = supportsKubernetesSecretsApi;
    }

    /** True if tasks run as Kubernetes pods rather than Cloud Run jobs. */
    public boolean launchesPods() {
        return this == COMPOSER_2_GKE_PODS || this == COMPOSER_3;
    }

    /**
     * The Composer image family Terraform should request, or {@code null} for
     * substrates that do not involve Composer.
     */
    public String composerImageVersion() {
        return composerImageVersion;
    }

    /**
     * The namespace pods are pinned to, or {@code null} when the substrate
     * lets the caller choose.
     */
    public String podNamespace() {
        return podNamespace;
    }

    public boolean allowsCustomNamespace() {
        return allowsCustomNamespace;
    }

    public int maxSidecars() {
        return maxSidecars;
    }

    /** True if Kubernetes Secrets/ConfigMaps can be created through the K8s API. */
    public boolean supportsKubernetesSecretsApi() {
        return supportsKubernetesSecretsApi;
    }

    /**
     * Resolve a substrate from configuration text, so a deployment can be
     * pointed at a different substrate without a code change.
     *
     * <p>Accepts the enum name in any case, and hyphens for underscores, so
     * {@code composer-3} and {@code COMPOSER_3} both work — Terraform
     * variables and Airflow config conventionally use hyphens.
     *
     * @throws IllegalArgumentException naming the valid values, because this
     *                                  is read from human-edited config and a
     *                                  bare enum-parse failure is unhelpful.
     */
    public static ExecutionSubstrate fromConfig(String value) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(
                    "execution substrate must be set; valid values: "
                            + String.join(", ", names()));
        }
        String normalised = value.trim().toUpperCase(java.util.Locale.ROOT).replace('-', '_');
        for (ExecutionSubstrate substrate : values()) {
            if (substrate.name().equals(normalised)) {
                return substrate;
            }
        }
        throw new IllegalArgumentException(
                "Unknown execution substrate '" + value + "'; valid values: "
                        + String.join(", ", names()));
    }

    private static String[] names() {
        ExecutionSubstrate[] all = values();
        String[] out = new String[all.length];
        for (int i = 0; i < all.length; i++) {
            out[i] = all[i].name();
        }
        return out;
    }
}
