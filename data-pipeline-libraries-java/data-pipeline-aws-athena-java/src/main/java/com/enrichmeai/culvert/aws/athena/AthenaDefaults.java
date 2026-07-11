package com.enrichmeai.culvert.aws.athena;

import software.amazon.awssdk.services.athena.AthenaClient;

/**
 * Worker-side defaults for auto-config reconstruction of {@link AthenaWarehouse}
 * (mirror of the GCP family's {@code BigQueryDefaults} — see that class and the
 * worker-rebuild rationale on the no-arg constructor).
 *
 * <p>Gated on {@code CULVERT_CLOUD=aws}: fat jars can carry both cloud families,
 * and the worker registry rebuild takes the first ServiceLoader-constructable
 * impl per contract — the selector makes that deterministic. Configuration:
 * {@code ATHENA_DATABASE} and {@code ATHENA_OUTPUT_LOCATION} env vars
 * ({@code athena.database}/{@code athena.outputLocation} system properties as
 * test hooks); client/region/credentials from the AWS default chains.
 */
final class AthenaDefaults {

    private AthenaDefaults() {
    }

    static void requireAwsSelected() {
        String cloud = resolve("CULVERT_CLOUD", "culvert.cloud");
        if (cloud == null || !cloud.equalsIgnoreCase("aws")) {
            throw new IllegalStateException(
                    "AWS adapters are gated to CULVERT_CLOUD=aws; current selector: " + cloud);
        }
    }

    static String database() {
        return require("ATHENA_DATABASE", "athena.database");
    }

    static String outputLocation() {
        return require("ATHENA_OUTPUT_LOCATION", "athena.outputLocation");
    }

    static AthenaClient client() {
        return AthenaClient.create();
    }

    private static String require(String envKey, String propKey) {
        String v = resolve(envKey, propKey);
        if (v == null) {
            throw new IllegalStateException(
                    envKey + " must be set for worker-side AthenaWarehouse auto-config.");
        }
        return v;
    }

    private static String resolve(String envKey, String propKey) {
        String v = System.getenv(envKey);
        if (v == null || v.isBlank()) {
            v = System.getProperty(propKey);
        }
        return (v == null || v.isBlank()) ? null : v;
    }
}
