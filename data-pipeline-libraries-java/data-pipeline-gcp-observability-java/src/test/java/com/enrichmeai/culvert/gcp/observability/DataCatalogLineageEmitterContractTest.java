package com.enrichmeai.culvert.gcp.observability;

import com.enrichmeai.culvert.contracts.LineageEmitter;
import com.enrichmeai.culvert.contracttests.LineageEmitterContractTest;
import com.google.cloud.datacatalog.v1.CreateTagRequest;
import com.google.cloud.datacatalog.v1.DataCatalogClient;
import com.google.cloud.datacatalog.v1.Tag;

import java.util.OptionalInt;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

/**
 * {@link DataCatalogLineageEmitter} against the shared
 * {@link LineageEmitterContractTest}: a mocked {@link DataCatalogClient} (the
 * seam {@code DataCatalogLineageEmitterTest} uses) that counts each
 * {@code createTag}.
 *
 * <p>The emitter is deprecated: Data Catalog began its phased shutdown on
 * 2026-06-01, and the class is no longer registered for discovery. This
 * binding holds it to the contract while it ships. Its replacement over the
 * Data Lineage API extends the same suite.
 */
@SuppressWarnings("deprecation")
class DataCatalogLineageEmitterContractTest extends LineageEmitterContractTest {

    private int tags;

    @Override
    protected LineageEmitter emitter() {
        DataCatalogClient client = mock(DataCatalogClient.class);
        when(client.createTag(any(CreateTagRequest.class))).thenAnswer(inv -> {
            tags++;
            return Tag.getDefaultInstance();
        });
        return new DataCatalogLineageEmitter(client,
                "projects/contract-project/locations/us/entryGroups/culvert/entries/customers",
                "projects/contract-project/locations/us/tagTemplates/culvert_lineage");
    }

    @Override
    protected OptionalInt delivered() {
        return OptionalInt.of(tags);
    }
}
