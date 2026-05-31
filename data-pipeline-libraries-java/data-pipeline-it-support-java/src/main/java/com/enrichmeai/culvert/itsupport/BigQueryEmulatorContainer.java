package com.enrichmeai.culvert.itsupport;

import com.google.cloud.NoCredentials;
import com.google.cloud.bigquery.BigQuery;
import com.google.cloud.bigquery.BigQueryOptions;
import org.testcontainers.containers.GenericContainer;
import org.testcontainers.containers.wait.strategy.Wait;
import org.testcontainers.utility.DockerImageName;

/**
 * Testcontainers fixture wrapping the
 * <a href="https://github.com/goccy/bigquery-emulator">goccy/bigquery-emulator</a>
 * image.
 *
 * <p>The emulator exposes an HTTP REST endpoint on port {@value #HTTP_PORT}
 * and a gRPC storage endpoint on port {@value #GRPC_PORT}. The Culvert
 * BigQuery adapter ({@code BigQueryWarehouse}, {@code BigQueryJobControlRepository},
 * {@code BigQueryFinOpsSink}) drives the REST endpoint, so {@link #newClient()}
 * points the SDK at the mapped HTTP port.
 *
 * <p>By default the emulator boots with a single {@code test} project and a
 * single {@code test} dataset (see {@link #DEFAULT_PROJECT_ID} /
 * {@link #DEFAULT_DATASET_ID}), which is enough for most adapter ITs. Use
 * {@link #BigQueryEmulatorContainer(String, String)} to override.
 *
 * <h2>Usage</h2>
 * <pre>{@code
 * @Testcontainers
 * class BigQueryWarehouseIT {
 *     @Container
 *     static final BigQueryEmulatorContainer EMULATOR = new BigQueryEmulatorContainer();
 *
 *     @Test
 *     void roundTrip() {
 *         BigQuery bq = EMULATOR.newClient();
 *         // ... exercise the adapter against bq ...
 *     }
 * }
 * }</pre>
 *
 * <p>Sprint-10 deliverable (T10.1).
 */
public final class BigQueryEmulatorContainer extends GenericContainer<BigQueryEmulatorContainer> {

    /** Default emulator image. Override via the {@link DockerImageName} constructor. */
    public static final DockerImageName DEFAULT_IMAGE =
            DockerImageName.parse("ghcr.io/goccy/bigquery-emulator:latest");

    /** HTTP (REST) port the emulator listens on inside the container. */
    public static final int HTTP_PORT = 9050;

    /** gRPC (storage API) port the emulator listens on inside the container. */
    public static final int GRPC_PORT = 9060;

    /** Project ID the emulator is seeded with by default. */
    public static final String DEFAULT_PROJECT_ID = "test";

    /** Dataset ID the emulator is seeded with by default. */
    public static final String DEFAULT_DATASET_ID = "test";

    private final String projectId;
    private final String datasetId;

    /**
     * Creates an emulator on {@link #DEFAULT_IMAGE} seeded with the
     * {@value #DEFAULT_PROJECT_ID} project and {@value #DEFAULT_DATASET_ID}
     * dataset.
     */
    public BigQueryEmulatorContainer() {
        this(DEFAULT_IMAGE, DEFAULT_PROJECT_ID, DEFAULT_DATASET_ID);
    }

    /**
     * Creates an emulator on {@link #DEFAULT_IMAGE} seeded with the given
     * project and dataset.
     *
     * @param projectId project the emulator is started with ({@code --project})
     * @param datasetId dataset the emulator is started with ({@code --dataset})
     */
    public BigQueryEmulatorContainer(String projectId, String datasetId) {
        this(DEFAULT_IMAGE, projectId, datasetId);
    }

    /**
     * Creates an emulator on a custom image seeded with the given project and
     * dataset.
     *
     * @param image     the emulator image to run
     * @param projectId project the emulator is started with ({@code --project})
     * @param datasetId dataset the emulator is started with ({@code --dataset})
     */
    public BigQueryEmulatorContainer(DockerImageName image, String projectId, String datasetId) {
        super(image);
        this.projectId = projectId;
        this.datasetId = datasetId;
    }

    /**
     * Configures exposed ports, start command and readiness wait.
     *
     * <p>Done in {@code configure()} rather than the constructor so that the
     * inherited {@code withX} self-typed mutators are not invoked on a
     * partially constructed instance (avoids the JDK {@code this-escape}
     * lint under {@code -Werror}). Testcontainers calls this exactly once,
     * just before the container starts.
     */
    @Override
    protected void configure() {
        withExposedPorts(HTTP_PORT, GRPC_PORT);
        withCommand(
                "--project=" + projectId,
                "--dataset=" + datasetId,
                "--port=" + HTTP_PORT,
                "--grpc-port=" + GRPC_PORT);
        // The emulator logs a "[bigquery-emulator] listening" line once the
        // REST endpoint is up; wait on the HTTP port being listenable.
        waitingFor(Wait.forListeningPort());
    }

    /** @return the project ID this emulator was seeded with. */
    public String getProjectId() {
        return projectId;
    }

    /** @return the dataset ID this emulator was seeded with. */
    public String getDatasetId() {
        return datasetId;
    }

    /**
     * @return the base HTTP (REST) endpoint of the running emulator, e.g.
     *         {@code http://localhost:32774}. Only valid once the container
     *         is started.
     */
    public String getEmulatorHttpEndpoint() {
        return "http://" + getHost() + ":" + getMappedPort(HTTP_PORT);
    }

    /**
     * Builds a {@link BigQuery} client pointed at this running emulator using
     * {@link NoCredentials} and the seeded project ID.
     *
     * <p>Only valid once the container is started. Equivalent to
     * {@code newClient(getProjectId())}.
     *
     * @return a BigQuery client targeting the emulator
     */
    public BigQuery newClient() {
        return newClient(projectId);
    }

    /**
     * Builds a {@link BigQuery} client pointed at this running emulator using
     * {@link NoCredentials} and the supplied project ID.
     *
     * <p>Only valid once the container is started.
     *
     * @param clientProjectId project ID the client should use
     * @return a BigQuery client targeting the emulator
     */
    public BigQuery newClient(String clientProjectId) {
        return BigQueryOptions.newBuilder()
                .setHost(getEmulatorHttpEndpoint())
                .setLocation(getEmulatorHttpEndpoint())
                .setProjectId(clientProjectId)
                .setCredentials(NoCredentials.getInstance())
                .build()
                .getService();
    }
}
