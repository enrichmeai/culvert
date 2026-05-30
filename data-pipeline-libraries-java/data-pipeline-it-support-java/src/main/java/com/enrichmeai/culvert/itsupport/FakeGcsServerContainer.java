package com.enrichmeai.culvert.itsupport;

import com.google.cloud.NoCredentials;
import com.google.cloud.storage.Storage;
import com.google.cloud.storage.StorageOptions;
import org.testcontainers.containers.GenericContainer;
import org.testcontainers.containers.wait.strategy.Wait;
import org.testcontainers.utility.DockerImageName;

/**
 * Testcontainers fixture wrapping the
 * <a href="https://github.com/fsouza/fake-gcs-server">fsouza/fake-gcs-server</a>
 * image — an in-memory Google Cloud Storage emulator.
 *
 * <p>The server is started with {@code -scheme http} and listens on port
 * {@value #PORT}. {@link #newClient()} builds a {@link Storage} client whose
 * host points at the mapped port with {@link NoCredentials}, so the Culvert
 * GCS adapter ({@code GcsBlobStore}) can be exercised against it without
 * touching real GCS.
 *
 * <h2>Usage</h2>
 * <pre>{@code
 * @Testcontainers
 * class GcsBlobStoreIT {
 *     @Container
 *     static final FakeGcsServerContainer GCS = new FakeGcsServerContainer();
 *
 *     @Test
 *     void roundTrip() {
 *         Storage storage = GCS.newClient();
 *         // ... exercise the adapter against storage ...
 *     }
 * }
 * }</pre>
 *
 * <p>Sprint-10 deliverable (T10.1).
 */
public final class FakeGcsServerContainer extends GenericContainer<FakeGcsServerContainer> {

    /** Default emulator image. Override via the {@link DockerImageName} constructor. */
    public static final DockerImageName DEFAULT_IMAGE =
            DockerImageName.parse("fsouza/fake-gcs-server:latest");

    /** HTTP port fake-gcs-server listens on inside the container. */
    public static final int PORT = 4443;

    /** Project ID the {@link #newClient()} helper uses; arbitrary for the emulator. */
    public static final String DEFAULT_PROJECT_ID = "test";

    /**
     * Creates a fake-gcs-server on {@link #DEFAULT_IMAGE}.
     */
    public FakeGcsServerContainer() {
        this(DEFAULT_IMAGE);
    }

    /**
     * Creates a fake-gcs-server on a custom image.
     *
     * @param image the emulator image to run
     */
    public FakeGcsServerContainer(DockerImageName image) {
        super(image);
    }

    /**
     * Configures the exposed port, start command and readiness wait.
     *
     * <p>Done in {@code configure()} rather than the constructor so that the
     * inherited {@code withX} self-typed mutators are not invoked on a
     * partially constructed instance (avoids the JDK {@code this-escape}
     * lint under {@code -Werror}). Testcontainers calls this exactly once,
     * just before the container starts.
     */
    @Override
    protected void configure() {
        withExposedPorts(PORT);
        // -scheme http keeps the emulator on plain HTTP (no self-signed TLS),
        // which is what the Storage client below is pointed at.
        withCommand("-scheme", "http");
        waitingFor(Wait.forListeningPort());
    }

    /**
     * @return the base HTTP endpoint of the running emulator, e.g.
     *         {@code http://localhost:32775}. Only valid once the container
     *         is started.
     */
    public String getEmulatorHttpEndpoint() {
        return "http://" + getHost() + ":" + getMappedPort(PORT);
    }

    /**
     * Builds a {@link Storage} client pointed at this running emulator using
     * {@link NoCredentials} and the {@value #DEFAULT_PROJECT_ID} project.
     *
     * <p>Only valid once the container is started. Equivalent to
     * {@code newClient(DEFAULT_PROJECT_ID)}.
     *
     * @return a Storage client targeting the emulator
     */
    public Storage newClient() {
        return newClient(DEFAULT_PROJECT_ID);
    }

    /**
     * Builds a {@link Storage} client pointed at this running emulator using
     * {@link NoCredentials} and the supplied project ID.
     *
     * <p>Only valid once the container is started.
     *
     * @param clientProjectId project ID the client should use
     * @return a Storage client targeting the emulator
     */
    public Storage newClient(String clientProjectId) {
        return StorageOptions.newBuilder()
                .setHost(getEmulatorHttpEndpoint())
                .setProjectId(clientProjectId)
                .setCredentials(NoCredentials.getInstance())
                .build()
                .getService();
    }
}
