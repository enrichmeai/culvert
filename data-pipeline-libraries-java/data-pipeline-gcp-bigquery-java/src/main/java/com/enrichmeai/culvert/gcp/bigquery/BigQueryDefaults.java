package com.enrichmeai.culvert.gcp.bigquery;

import com.google.cloud.bigquery.BigQuery;
import com.google.cloud.bigquery.BigQueryOptions;

/**
 * Worker-side defaults for auto-config reconstruction of the BigQuery adapters.
 *
 * <p>When a {@code DefaultRuntimeContext} crosses to a Beam worker its adapter
 * registry is {@code transient} and is rebuilt from
 * {@code AutoConfig.discover()} (plain {@link java.util.ServiceLoader}). That
 * requires the config-carrying adapters ({@code BigQueryWarehouse},
 * {@code BigQueryJobControlRepository}) to be no-arg constructable. This helper
 * supplies the two values ServiceLoader can't — the GCP project and the dataset
 * region — from the worker's own environment (which already runs as the
 * pipeline's service account in the pipeline's project):
 *
 * <ul>
 *   <li>Project: {@code GCP_PROJECT} env, else {@code gcp.project} system
 *       property (test hook), else the Application Default project.</li>
 *   <li>Location: {@code GCP_LOCATION} env, else {@code gcp.location} system
 *       property, else the client default (US multi-region). Must be set to the
 *       dataset's region (e.g. {@code europe-west2}) for non-US datasets, or
 *       BigQuery load/query jobs fail with a cross-region error.</li>
 * </ul>
 *
 * Explicit driver-side construction with {@code new BigQueryWarehouse(project,
 * client)} is unaffected — this is only the fallback the worker rebuild uses.
 */
final class BigQueryDefaults {

    private BigQueryDefaults() {
    }

    /**
     * Cloud-selection gate for worker-side reconstruction. Fat jars can carry
     * BOTH the GCP and AWS adapter families, and the worker registry rebuild
     * takes the first ServiceLoader-constructable impl per contract — so each
     * family's no-arg constructors are gated on the {@code CULVERT_CLOUD}
     * selector ({@code culvert.cloud} system property as the test hook).
     * GCP adapters construct when the selector is unset or {@code gcp}
     * (backward-compatible default); any other value throws, which AutoConfig
     * treats as "skip this impl" — turning skip-on-failure into deterministic
     * cloud selection.
     */
    static void requireGcpSelected() {
        String cloud = resolve("CULVERT_CLOUD", "culvert.cloud");
        if (cloud != null && !cloud.equalsIgnoreCase("gcp")) {
            throw new IllegalStateException(
                    "BigQuery adapters are gated to CULVERT_CLOUD=gcp (or unset); current selector: "
                            + cloud);
        }
    }

    static String project() {
        String p = resolve("GCP_PROJECT", "gcp.project");
        if (p == null) {
            p = BigQueryOptions.getDefaultInstance().getProjectId();
        }
        if (p == null || p.isBlank()) {
            throw new IllegalStateException(
                    "BigQuery project not resolvable for worker-side auto-config: set the "
                            + "GCP_PROJECT environment variable (or run where an Application "
                            + "Default project is available).");
        }
        return p;
    }

    static BigQuery client() {
        BigQueryOptions.Builder builder = BigQueryOptions.newBuilder().setProjectId(project());
        String location = resolve("GCP_LOCATION", "gcp.location");
        if (location != null && !location.isBlank()) {
            builder.setLocation(location);
        }
        return builder.build().getService();
    }

    static String jobControlDataset() {
        String d = resolve("JOB_CONTROL_DATASET", "gcp.jobControlDataset");
        return d != null ? d : "job_control";
    }

    static String jobControlTable() {
        String t = resolve("JOB_CONTROL_TABLE", "gcp.jobControlTable");
        return t != null ? t : "pipeline_jobs";
    }

    private static String resolve(String envKey, String propKey) {
        String v = System.getenv(envKey);
        if (v == null || v.isBlank()) {
            v = System.getProperty(propKey);
        }
        return (v == null || v.isBlank()) ? null : v;
    }
}
