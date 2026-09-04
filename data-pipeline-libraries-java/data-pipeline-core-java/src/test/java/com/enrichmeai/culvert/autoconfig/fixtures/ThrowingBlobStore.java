package com.enrichmeai.culvert.autoconfig.fixtures;

/**
 * A provider whose constructor throws — the shape {@code S3BlobStore}'s {@code CULVERT_CLOUD}
 * gate used to have, and the one that used to truncate the whole provider list.
 */
public final class ThrowingBlobStore extends FixtureBlobStore {

    public ThrowingBlobStore() {
        throw new IllegalStateException("fixture refuses to be constructed");
    }
}
