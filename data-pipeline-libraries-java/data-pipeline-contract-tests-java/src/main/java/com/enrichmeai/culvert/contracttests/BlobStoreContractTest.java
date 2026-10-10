package com.enrichmeai.culvert.contracttests;

import com.enrichmeai.culvert.contracts.BlobStore;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * Contract tests every {@link BlobStore} implementation must pass.
 *
 * <p>Subclasses provide a {@link BlobStore} pre-populated with
 * {@code knownUri()} = "hello".getBytes(); {@code missingUri()} returns
 * 404 / FileNotFoundException-equivalent semantics.
 *
 * <p>Sprint-5 deliverable.
 */
public abstract class BlobStoreContractTest {

    protected abstract BlobStore store();

    protected abstract String knownUri();

    protected abstract String missingUri();

    @Test
    void getKnownReturnsBytes() {
        byte[] data = store().get(knownUri());
        assertThat(data).isEqualTo("hello".getBytes());
    }

    /**
     * {@code openInput} streams the known object's bytes. Subclasses whose fake client must be told
     * the content stub its streaming read too (a GCS {@code ReadChannel}, an S3 {@code getObject}),
     * not only the whole-object read {@code get} uses. Python: {@code test_open_input_known_streams_the_bytes}.
     */
    @Test
    void openInputKnownStreamsTheBytes() throws java.io.IOException {
        try (java.io.InputStream in = store().openInput(knownUri())) {
            assertThat(in).as("openInput's stream").isNotNull();
            assertThat(in.readAllBytes()).isEqualTo("hello".getBytes());
        }
    }

    /**
     * A missing object fails when it is opened, the way {@code get} does: not with a null stream,
     * and not later, on the first read. Python: {@code test_open_input_missing_fails_as_get_does}.
     */
    @Test
    void openInputMissingFailsAsGetDoes() {
        assertThatThrownBy(() -> store().openInput(missingUri()))
                .satisfiesAnyOf(
                        t -> assertThat(t).isInstanceOf(java.io.UncheckedIOException.class)
                                .hasCauseInstanceOf(java.io.FileNotFoundException.class),
                        t -> assertThat(t).isInstanceOf(java.io.FileNotFoundException.class));
    }

    @Test
    void existsKnownTrue() {
        assertThat(store().exists(knownUri())).isTrue();
    }

    @Test
    void existsMissingFalse() {
        assertThat(store().exists(missingUri())).isFalse();
    }

    /**
     * {@code head} describes the known object without reading it: the size of
     * "hello", a non-blank version token, and never a null field. Subclasses
     * whose fake client must be told the metadata (a mocked GCS {@code Blob}, a
     * built S3 {@code HeadObjectResponse}) stub size and ETag for the known
     * object — a fake that reports no ETag would make a loader keyed on it skip
     * nothing and load everything twice.
     */
    @Test
    void headKnownDescribesTheObjectWithoutReadingIt() {
        com.enrichmeai.culvert.contracts.BlobMetadata metadata = store().head(knownUri());
        assertThat(metadata.uri()).isEqualTo(knownUri());
        assertThat(metadata.size()).isEqualTo("hello".getBytes().length);
        assertThat(metadata.etag()).as("the store's version token").isNotBlank();
        assertThat(metadata.lastModified()).isNotNull();
        assertThat(metadata.metadata()).isNotNull();
    }

    /** A missing object fails the way {@code get} does, not with a null or an empty description. */
    @Test
    void headMissingFailsAsGetDoes() {
        assertThatThrownBy(() -> store().head(missingUri()))
                .satisfiesAnyOf(
                        t -> assertThat(t).isInstanceOf(java.io.UncheckedIOException.class)
                                .hasCauseInstanceOf(java.io.FileNotFoundException.class),
                        t -> assertThat(t).isInstanceOf(java.io.FileNotFoundException.class));
    }

    @Test
    void deleteMissingIsIdempotent() {
        // Should not throw — deleting an already-missing object is fine.
        store().delete(missingUri());
    }

    @Test
    void nullArgumentsRejected() {
        assertThatThrownBy(() -> store().get(null))
                .isInstanceOfAny(NullPointerException.class, IllegalArgumentException.class);
    }
}
