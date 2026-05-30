package com.enrichmeai.culvert.gcp.dataflow;

import com.enrichmeai.culvert.contracts.BlobStore;
import com.enrichmeai.culvert.contracts.RuntimeContext;
import com.enrichmeai.culvert.gcp.gcs.GcsBlobStore;
import com.enrichmeai.culvert.itsupport.FakeGcsServerContainer;
import com.enrichmeai.culvert.runtime.DefaultRuntimeContext;
import com.google.cloud.storage.BucketInfo;
import com.google.cloud.storage.Storage;
import org.junit.jupiter.api.Test;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import java.nio.charset.StandardCharsets;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * T10.0 — real-adapter wiring integration test (deferred from Sprint 9 T9.4).
 *
 * <p>Proves {@link DefaultRuntimeContext} works with a REAL adapter instance
 * registered via {@link RuntimeContext#register(Class, Object)} — not a stub.
 * A real {@link GcsBlobStore}, backed by the {@code fake-gcs-server}
 * Testcontainers fixture from {@code data-pipeline-it-support}, is registered
 * under {@link BlobStore} and a full put/exists/get round-trip is driven
 * through the context-resolved instance.
 *
 * <p>This wiring lives in the dataflow adapter's test tree (not in core)
 * because {@code data-pipeline-core} is cloud-neutral and must not depend on
 * any GCP adapter; this module already depends on core and pulls gcs +
 * it-support in test scope.
 */
@Testcontainers
class DefaultRuntimeContextWiringIT {

    @Container
    static final FakeGcsServerContainer GCS = new FakeGcsServerContainer();

    private static final String BUCKET = "wiring-it-bucket";

    @Test
    void registersRealGcsBlobStoreAndRoundTripsThroughContext() {
        // Real GCS client pointed at the emulator; create the bucket the
        // round-trip will use.
        Storage storage = GCS.newClient();
        storage.create(BucketInfo.of(BUCKET));

        // A REAL adapter instance (not a mock/stub).
        GcsBlobStore blobStore = new GcsBlobStore(storage);

        // Wire it into the framework's DI container.
        RuntimeContext ctx = DefaultRuntimeContext.builder("run-wiring-it", "test")
                .register(BlobStore.class, blobStore)
                .build();

        // The context resolves the exact instance we registered.
        BlobStore resolved = ctx.get(BlobStore.class);
        assertThat(resolved).isSameAs(blobStore);

        // Full round-trip THROUGH the context-resolved instance, against the
        // running fake-gcs-server.
        String uri = "gs://" + BUCKET + "/wiring/object.txt";
        byte[] payload = "culvert-wiring".getBytes(StandardCharsets.UTF_8);

        assertThat(resolved.exists(uri)).isFalse();
        resolved.put(uri, payload);
        assertThat(resolved.exists(uri)).isTrue();
        assertThat(resolved.get(uri)).isEqualTo(payload);

        resolved.delete(uri);
        assertThat(resolved.exists(uri)).isFalse();
    }
}
