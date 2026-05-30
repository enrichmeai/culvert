/**
 * Reusable Testcontainers fixtures for the Culvert framework's integration
 * tests.
 *
 * <p>This module is a <em>test-support library</em>: an adapter module
 * (e.g. {@code data-pipeline-gcp-bigquery}, {@code data-pipeline-gcp-gcs})
 * depends on it in {@code test} scope and uses these fixtures from its
 * {@code *IT.java} tests, which run under the parent POM's {@code it}
 * profile (failsafe) against a running Docker daemon.
 *
 * <h2>Fixtures</h2>
 * <ul>
 *   <li>{@link com.enrichmeai.culvert.itsupport.BigQueryEmulatorContainer} —
 *       wraps {@code ghcr.io/goccy/bigquery-emulator} and builds a
 *       {@link com.google.cloud.bigquery.BigQuery} client pointed at the
 *       emulator with {@link com.google.cloud.NoCredentials}.</li>
 *   <li>{@link com.enrichmeai.culvert.itsupport.FakeGcsServerContainer} —
 *       wraps {@code fsouza/fake-gcs-server} and builds a
 *       {@link com.google.cloud.storage.Storage} client pointed at the
 *       emulator with {@link com.google.cloud.NoCredentials}.</li>
 * </ul>
 *
 * <h2>Pub/Sub</h2>
 * <p>There is intentionally no Pub/Sub fixture here. Testcontainers ships a
 * ready-made {@code org.testcontainers.containers.PubSubEmulatorContainer}
 * (in the {@code org.testcontainers:gcloud} module, which this library
 * already pulls in), so Pub/Sub ITs use that class directly. See the module
 * README for the wiring snippet.
 *
 * <p>Sprint-10 deliverable (T10.1).
 */
package com.enrichmeai.culvert.itsupport;
