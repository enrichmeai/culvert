package com.enrichmeai.culvert.aws.s3;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * The {@code CULVERT_CLOUD} gate on the worker-side no-arg constructor.
 *
 * <p>Story 1.1 (AC 4) changed the shape of this gate: declining is now "report unavailable",
 * not "throw". A throwing constructor is what let one adapter truncate {@code AutoConfig}'s
 * whole provider list, so the gate must construct cleanly and answer
 * {@code isAvailable() == false} instead. Using the adapter anyway still fails loudly —
 * unavailable means "do not select me", not "silently do nothing".
 */
class S3WorkerAutoConfigTest {

    @BeforeEach
    @AfterEach
    void clearSelector() {
        System.clearProperty(S3BlobStore.SYSPROP_CULVERT_CLOUD);
    }

    @Test
    void noArgConstructionDoesNotThrowWhenTheAwsSelectorIsUnset() {
        assertThatCode(S3BlobStore::new).doesNotThrowAnyException();
    }

    @Test
    void reportsItselfUnavailableWhenTheAwsSelectorIsUnset() {
        assertThat(new S3BlobStore().isAvailable()).isFalse();
    }

    @Test
    void reportsItselfAvailableWhenTheAwsSelectorIsSet() {
        System.setProperty(S3BlobStore.SYSPROP_CULVERT_CLOUD, "aws");
        assertThat(new S3BlobStore().isAvailable()).isTrue();
    }

    @Test
    void usingAGatedOutInstanceStillFailsLoudly() {
        S3BlobStore store = new S3BlobStore();
        assertThatThrownBy(() -> store.exists("s3://bucket/key"))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("CULVERT_CLOUD");
    }
}
