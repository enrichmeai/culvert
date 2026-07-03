package com.enrichmeai.culvert.aws.s3;

import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInstance;
import org.testcontainers.containers.localstack.LocalStackContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;
import software.amazon.awssdk.auth.credentials.AwsBasicCredentials;
import software.amazon.awssdk.auth.credentials.StaticCredentialsProvider;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.S3ClientBuilder;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.testcontainers.containers.localstack.LocalStackContainer.Service.S3;

/**
 * Integration tests for {@link S3BlobStore} exercised against a real S3 API
 * emulator (localstack/localstack) via Testcontainers.
 *
 * <p>Where {@code S3BlobStoreTest} mocks {@link S3Client} and asserts on the
 * calls the adapter issues, and {@code S3BlobStoreContractTest} binds the
 * shared {@code BlobStoreContractTest} suite against a mocked client, this IT
 * drives the adapter end-to-end against the running LocalStack container: it
 * creates a real bucket, then exercises the full
 * {@link com.enrichmeai.culvert.contracts.BlobStore} surface ({@code put} /
 * {@code openOutput} / {@code get} / {@code openInput} / {@code exists} /
 * {@code list} / {@code delete} / {@code copy}) and asserts on the bytes and
 * URIs that actually come back from the emulator.
 *
 * <p>Mirrors {@code GcsBlobStoreIT} in {@code data-pipeline-gcp-gcs-java}.
 * Suffixed {@code IT} so the default {@code mvn test} (surefire) skips it;
 * it only runs under {@code mvn -P it verify} (failsafe), which requires a
 * running Docker daemon.
 *
 * <p>Sprint-21 deliverable (T21.1, issue #145).
 */
@Testcontainers
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class S3BlobStoreLocalStackIT {

    @Container
    static final LocalStackContainer LOCALSTACK =
            new LocalStackContainer(DockerImageName.parse("localstack/localstack:3.4.0"))
                    .withServices(S3);

    private static final String BUCKET = "culvert-it-bucket";

    private S3Client client;
    private S3BlobStore store;

    @BeforeAll
    void setUp() {
        S3ClientBuilder builder = S3Client.builder()
                .endpointOverride(LOCALSTACK.getEndpointOverride(S3))
                .region(Region.of(LOCALSTACK.getRegion()))
                .credentialsProvider(StaticCredentialsProvider.create(
                        AwsBasicCredentials.create(LOCALSTACK.getAccessKey(), LOCALSTACK.getSecretKey())))
                // LocalStack's S3 emulator serves path-style, not the
                // virtual-hosted-style S3Client defaults to.
                .forcePathStyle(true);
        client = builder.build();
        client.createBucket(b -> b.bucket(BUCKET));
        store = new S3BlobStore(client);
    }

    @AfterAll
    void tearDown() {
        if (client != null) {
            client.close();
        }
    }

    private static String uri(String key) {
        return "s3://" + BUCKET + "/" + key;
    }

    @Test
    void putGetExistsDeleteRoundTrip() {
        String key = uri("round-trip/object.txt");
        byte[] payload = "hello localstack".getBytes(StandardCharsets.UTF_8);

        assertThat(store.exists(key)).isFalse();

        store.put(key, payload);
        assertThat(store.exists(key)).isTrue();
        assertThat(store.get(key)).isEqualTo(payload);

        // Delete is idempotent: a second delete against the now-missing
        // object must not throw.
        store.delete(key);
        assertThat(store.exists(key)).isFalse();
        store.delete(key);
    }

    @Test
    void getMissingObjectThrowsFileNotFound() {
        String key = uri("does-not-exist.txt");

        assertThat(store.exists(key)).isFalse();
        assertThatThrownBy(() -> store.get(key))
                .isInstanceOf(UncheckedIOException.class)
                .hasCauseInstanceOf(java.io.FileNotFoundException.class);
    }

    @Test
    void openOutputThenOpenInputStreamsBytes() throws IOException {
        String key = uri("streamed/payload.bin");
        byte[] payload = "streamed-content-via-s3-put".getBytes(StandardCharsets.UTF_8);

        // Streaming write: the write commits on close() (buffer-and-put).
        try (OutputStream out = store.openOutput(key)) {
            out.write(payload);
        }

        assertThat(store.exists(key)).isTrue();

        byte[] read;
        try (InputStream in = store.openInput(key)) {
            read = in.readAllBytes();
        }
        assertThat(read).isEqualTo(payload);
        assertThat(store.get(key)).isEqualTo(payload);

        store.delete(key);
    }

    @Test
    void listWithPrefixYieldsAbsoluteUris() {
        String a = uri("list-prefix/a.txt");
        String b = uri("list-prefix/b.txt");
        String other = uri("list-other/c.txt");
        store.put(a, "a".getBytes(StandardCharsets.UTF_8));
        store.put(b, "b".getBytes(StandardCharsets.UTF_8));
        store.put(other, "c".getBytes(StandardCharsets.UTF_8));

        Iterator<String> it = store.list(uri("list-prefix/"));
        List<String> found = new ArrayList<>();
        it.forEachRemaining(found::add);

        assertThat(found)
                .containsExactlyInAnyOrder(a, b)
                .doesNotContain(other);

        store.delete(a);
        store.delete(b);
        store.delete(other);
    }

    @Test
    void copyDuplicatesObjectWithinTheSameStore() {
        String src = uri("copy-src/object.txt");
        String dst = uri("copy-dst/object.txt");
        byte[] payload = "copy-me".getBytes(StandardCharsets.UTF_8);
        store.put(src, payload);

        store.copy(src, dst);

        assertThat(store.exists(dst)).isTrue();
        assertThat(store.get(dst)).isEqualTo(payload);
        // Source is untouched by copy.
        assertThat(store.exists(src)).isTrue();

        store.delete(src);
        store.delete(dst);
    }
}
