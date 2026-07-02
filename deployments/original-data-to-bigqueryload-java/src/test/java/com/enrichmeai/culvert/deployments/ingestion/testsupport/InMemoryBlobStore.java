package com.enrichmeai.culvert.deployments.ingestion.testsupport;

import com.enrichmeai.culvert.contracts.BlobStore;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.FileNotFoundException;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * In-memory {@link BlobStore} test double.
 *
 * <p>Mirrors {@code deployments/reference-e2e-gcp}'s
 * {@code com.enrichmeai.culvert.e2e.dq.InMemoryBlobStore} (T14.5 pattern) —
 * stores bytes keyed by URI in a {@link LinkedHashMap}, no real GCS/network.
 */
public final class InMemoryBlobStore implements BlobStore {

    private final Map<String, byte[]> store = new LinkedHashMap<>();

    public List<String> writtenUris() {
        return Collections.unmodifiableList(new ArrayList<>(store.keySet()));
    }

    public byte[] getOrNull(String uri) {
        return store.get(uri);
    }

    public void seed(String uri, byte[] data) {
        store.put(uri, data);
    }

    @Override
    public byte[] get(String uri) {
        byte[] bytes = store.get(uri);
        if (bytes == null) {
            throw new RuntimeException(new FileNotFoundException("no object at: " + uri));
        }
        return bytes;
    }

    @Override
    public InputStream openInput(String uri) {
        return new ByteArrayInputStream(get(uri));
    }

    @Override
    public OutputStream openOutput(String uri) {
        return new ByteArrayOutputStream() {
            @Override
            public void close() {
                store.put(uri, toByteArray());
            }
        };
    }

    @Override
    public void put(String uri, byte[] data) {
        store.put(uri, data);
    }

    @Override
    public Iterator<String> list(String prefix) {
        return store.keySet().stream().filter(k -> k.startsWith(prefix)).iterator();
    }

    @Override
    public boolean exists(String uri) {
        return store.containsKey(uri);
    }

    @Override
    public void delete(String uri) {
        store.remove(uri);
    }

    @Override
    public void copy(String src, String dst) {
        store.put(dst, get(src));
    }
}
