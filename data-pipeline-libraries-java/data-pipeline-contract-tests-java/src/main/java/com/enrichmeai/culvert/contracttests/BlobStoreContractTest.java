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

    @Test
    void existsKnownTrue() {
        assertThat(store().exists(knownUri())).isTrue();
    }

    @Test
    void existsMissingFalse() {
        assertThat(store().exists(missingUri())).isFalse();
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
