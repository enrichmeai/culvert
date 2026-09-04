package com.enrichmeai.culvert.autoconfig.fixtures;

import com.enrichmeai.culvert.contracts.BlobStore;

import java.io.InputStream;
import java.io.OutputStream;
import java.util.Iterator;

/**
 * Base for the {@link BlobStore} test doubles that {@code AutoConfigTest} registers in
 * throwaway {@code META-INF/services} fixtures. Discovery only ever constructs these and
 * reads their identity; none of the store operations is exercised.
 */
public abstract class FixtureBlobStore implements BlobStore {

    @Override
    public byte[] get(String uri) {
        throw new UnsupportedOperationException("discovery fixture");
    }

    @Override
    public InputStream openInput(String uri) {
        throw new UnsupportedOperationException("discovery fixture");
    }

    @Override
    public OutputStream openOutput(String uri) {
        throw new UnsupportedOperationException("discovery fixture");
    }

    @Override
    public void put(String uri, byte[] data) {
        throw new UnsupportedOperationException("discovery fixture");
    }

    @Override
    public Iterator<String> list(String prefix) {
        throw new UnsupportedOperationException("discovery fixture");
    }

    @Override
    public boolean exists(String uri) {
        throw new UnsupportedOperationException("discovery fixture");
    }

    @Override
    public void delete(String uri) {
        throw new UnsupportedOperationException("discovery fixture");
    }

    @Override
    public void copy(String src, String dst) {
        throw new UnsupportedOperationException("discovery fixture");
    }
}
