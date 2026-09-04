package com.enrichmeai.culvert.autoconfig.fixtures;

/**
 * A provider ServiceLoader cannot construct at all: no public no-arg constructor. The
 * resulting {@code ServiceConfigurationError} is raised while advancing the iterator rather
 * than while instantiating, which is a different code path from {@link ThrowingBlobStore}.
 */
public final class NoNoArgBlobStore extends FixtureBlobStore {

    @SuppressWarnings("unused")
    public NoNoArgBlobStore(String required) {
        // Intentionally no no-arg constructor.
    }
}
