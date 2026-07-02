package com.enrichmeai.culvert.deployments.ingestion.stages;

import com.enrichmeai.culvert.contracts.BlobStore;
import com.enrichmeai.culvert.contracts.JobControlRepository;
import com.enrichmeai.culvert.contracts.RuntimeContext;
import com.enrichmeai.culvert.contracts.Warehouse;
import com.enrichmeai.culvert.deployments.ingestion.testsupport.EnvelopeFixtures;
import com.enrichmeai.culvert.deployments.ingestion.testsupport.InMemoryBlobStore;
import com.enrichmeai.culvert.deployments.ingestion.testsupport.RecordingJobControlRepository;
import com.enrichmeai.culvert.deployments.ingestion.testsupport.RecordingWarehouse;
import com.enrichmeai.culvert.runtime.DefaultRuntimeContext;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Exercises {@link IngestionStage#execute} directly (no Beam pipeline, no
 * serialization boundary) against in-memory adapters registered on a
 * {@link DefaultRuntimeContext}.
 *
 * <p>This is the counterpart to {@link IngestionStageTest}'s DirectRunner test:
 * it proves the {@link IngestionStage} <-> {@link com.enrichmeai.culvert.deployments.ingestion.IngestionRunner}
 * wiring (adapter resolution via {@code context.get(...)}, request
 * construction, result capture) works correctly, without running into the
 * driver-vs-worker registry boundary that blocks a full run through
 * {@code StageTransform} with non-ServiceLoader-discoverable adapters (see
 * {@link IngestionStageTest} class Javadoc for the detailed explanation).
 */
class IngestionStageDirectExecuteTest {

    private static final String SOURCE_URI = "gs://landing/generic/customers/generic_customers_20260601.csv";
    private static final String TARGET_TABLE = "proj.odp_generic.customers";
    private static final String CSV_HEADER =
            "customer_id,first_name,last_name,ssn,dob,status,created_date";

    @Test
    void executeResolvesAdaptersFromContextAndRunsTheFullFlow() {
        InMemoryBlobStore blobStore = new InMemoryBlobStore();
        RecordingWarehouse warehouse = new RecordingWarehouse();
        RecordingJobControlRepository jobControlRepository = new RecordingJobControlRepository();
        warehouse.returnRowCount(1);

        blobStore.seed(SOURCE_URI, EnvelopeFixtures.buildFileBytes(
                "Generic", "customers", "20260601", CSV_HEADER,
                List.of("cust-1,Ada,Lovelace,123-45-6789,1990-01-01,A,2020-01-01")));

        IngestionStage stage = new IngestionStage(
                "run-direct-execute", "customers", SOURCE_URI, "20260601", TARGET_TABLE,
                "gs://staging/staging", "gs://errors/errors");

        RuntimeContext context = DefaultRuntimeContext.builder("run-direct-execute", "test")
                .register(BlobStore.class, blobStore)
                .register(Warehouse.class, warehouse)
                .register(JobControlRepository.class, jobControlRepository)
                .config(Map.of("deployment", "original-data-to-bigqueryload-java"))
                .build();

        stage.execute(context);

        assertThat(stage.lastResult()).isNotNull();
        assertThat(stage.lastResult().validRowCount()).isEqualTo(1);
        assertThat(stage.lastResult().loadedRowCount()).isEqualTo(1);
        assertThat(stage.lastResult().reconciliation().isReconciled()).isTrue();

        assertThat(warehouse.loadCalls).hasSize(1);
        assertThat(jobControlRepository.job("run-direct-execute")).isPresent();
    }
}
