package com.enrichmeai.culvert.tester;

import com.enrichmeai.culvert.contracts.BlobStore;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.io.InputStream;
import java.io.UncheckedIOException;
import java.util.Iterator;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class BlobStoreFixturesTest {

    @Test
    void emptyBlobStoreHasNoObjects() {
        BlobStore bs = BlobStoreFixtures.emptyBlobStore();

        assertThat(bs.exists("gs://b/o")).isFalse();
        assertThat(bs.list("gs://b/")).isExhausted();
        assertThatThrownBy(() -> bs.get("gs://b/o"))
                .isInstanceOf(UncheckedIOException.class);
    }

    @Test
    void blobStoreWithReturnsBytesAndStreamsForKnownUris() throws IOException {
        byte[] hello = "hello".getBytes();
        byte[] world = "world".getBytes();
        BlobStore bs = BlobStoreFixtures.blobStoreWith(Map.of(
                "gs://b/a.txt", hello,
                "gs://b/b.txt", world));

        assertThat(bs.exists("gs://b/a.txt")).isTrue();
        assertThat(bs.get("gs://b/a.txt")).isEqualTo(hello);

        try (InputStream in = bs.openInput("gs://b/b.txt")) {
            assertThat(in.readAllBytes()).isEqualTo(world);
        }

        assertThat(bs.exists("gs://b/missing")).isFalse();
        assertThatThrownBy(() -> bs.openInput("gs://b/missing"))
                .isInstanceOf(UncheckedIOException.class);
    }

    @Test
    void listReturnsMatchingUrisInLexicographicOrder() {
        BlobStore bs = BlobStoreFixtures.blobStoreWith(Map.of(
                "gs://b/data/2.txt", new byte[0],
                "gs://b/data/1.txt", new byte[0],
                "gs://b/other/x.txt", new byte[0]));

        Iterator<String> listed = bs.list("gs://b/data/");
        List<String> all = new java.util.ArrayList<>();
        listed.forEachRemaining(all::add);
        assertThat(all).containsExactly("gs://b/data/1.txt", "gs://b/data/2.txt");
    }
}
