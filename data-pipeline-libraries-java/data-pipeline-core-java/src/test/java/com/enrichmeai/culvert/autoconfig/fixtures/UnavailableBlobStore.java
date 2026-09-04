package com.enrichmeai.culvert.autoconfig.fixtures;

import com.enrichmeai.culvert.autoconfig.ProviderAvailability;

/**
 * A provider that constructs cleanly and then declines — the non-throwing opt-out that
 * replaced the throwing gate (Story 1.1, AC 4).
 */
public final class UnavailableBlobStore extends FixtureBlobStore implements ProviderAvailability {

    @Override
    public boolean isAvailable() {
        return false;
    }
}
