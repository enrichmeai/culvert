package com.enrichmeai.culvert.tester;

import com.enrichmeai.culvert.contracts.BlobStore;
import org.mockito.Mockito;

import java.io.ByteArrayInputStream;
import java.io.FileNotFoundException;
import java.io.InputStream;
import java.io.UncheckedIOException;
import java.util.Collections;
import java.util.Map;
import java.util.Objects;
import java.util.TreeMap;

/**
 * Mockito-mock fixture builders for {@link BlobStore}.
 *
 * <p>Returned mocks expose a read-only in-memory blob store backed by the
 * supplied map. {@link BlobStore#get(String)} and
 * {@link BlobStore#openInput(String)} surface bytes for known URIs and
 * raise an {@link UncheckedIOException} wrapping {@link FileNotFoundException}
 * for unknown URIs (matching the documented contract). Write operations
 * ({@code put}, {@code openOutput}, {@code delete}, {@code copy}) are
 * no-ops on the returned mock — consumers add further stubbing when they
 * need to assert against writes.
 *
 * <p>This class is non-instantiable.
 */
public final class BlobStoreFixtures {

    private BlobStoreFixtures() {
        throw new AssertionError("no instances");
    }

    /**
     * Mock {@link BlobStore} where no objects exist.
     * {@code exists} returns false; {@code get} / {@code openInput} raise
     * the wrapped {@link FileNotFoundException}; {@code list} returns an
     * empty iterator.
     */
    public static BlobStore emptyBlobStore() {
        return blobStoreWith(Collections.emptyMap());
    }

    /**
     * Mock {@link BlobStore} backed by an in-memory URI -> bytes map.
     *
     * <p>For each URI in {@code contents}:
     * <ul>
     *     <li>{@code get(uri)} returns the matching byte array.</li>
     *     <li>{@code openInput(uri)} returns a {@link ByteArrayInputStream}
     *         over those bytes.</li>
     *     <li>{@code exists(uri)} returns true.</li>
     * </ul>
     * For any URI not in {@code contents}:
     * <ul>
     *     <li>{@code get / openInput} raise
     *         {@code UncheckedIOException(FileNotFoundException)}.</li>
     *     <li>{@code exists} returns false.</li>
     * </ul>
     * {@code list(prefix)} returns the URIs in {@code contents} that start
     * with {@code prefix}, in lexicographic order.
     *
     * @param contents URI -> bytes map. Must not be null.
     */
    public static BlobStore blobStoreWith(Map<String, byte[]> contents) {
        Objects.requireNonNull(contents, "contents must not be null");
        // Sort by URI for the lexicographic-order list() guarantee.
        TreeMap<String, byte[]> sorted = new TreeMap<>(contents);

        BlobStore mock = Mockito.mock(BlobStore.class);

        Mockito.when(mock.get(Mockito.anyString())).thenAnswer(invocation -> {
            String uri = invocation.getArgument(0);
            byte[] bytes = sorted.get(uri);
            if (bytes == null) {
                throw new UncheckedIOException(
                        new FileNotFoundException("No object at " + uri));
            }
            return bytes.clone();
        });

        Mockito.when(mock.openInput(Mockito.anyString())).thenAnswer(invocation -> {
            String uri = invocation.getArgument(0);
            byte[] bytes = sorted.get(uri);
            if (bytes == null) {
                throw new UncheckedIOException(
                        new FileNotFoundException("No object at " + uri));
            }
            return (InputStream) new ByteArrayInputStream(bytes);
        });

        Mockito.when(mock.exists(Mockito.anyString())).thenAnswer(invocation -> {
            String uri = invocation.getArgument(0);
            return sorted.containsKey(uri);
        });

        Mockito.when(mock.list(Mockito.anyString())).thenAnswer(invocation -> {
            String prefix = invocation.getArgument(0);
            return sorted.keySet().stream()
                    .filter(uri -> uri.startsWith(prefix))
                    .iterator();
        });

        // put / openOutput / delete / copy default to Mockito no-op /
        // null returns. Consumers stub these on top when needed.
        return mock;
    }
}
