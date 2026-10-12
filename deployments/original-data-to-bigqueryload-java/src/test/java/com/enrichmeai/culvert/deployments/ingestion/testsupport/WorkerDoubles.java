package com.enrichmeai.culvert.deployments.ingestion.testsupport;

import com.enrichmeai.culvert.autoconfig.ProviderAvailability;
import com.enrichmeai.culvert.contracts.BlobMetadata;
import com.enrichmeai.culvert.contracts.BlobStore;
import com.enrichmeai.culvert.contracts.JobControlRepository;
import com.enrichmeai.culvert.contracts.LoadOptions;
import com.enrichmeai.culvert.contracts.Warehouse;
import com.enrichmeai.culvert.jobcontrol.EntityStatus;
import com.enrichmeai.culvert.jobcontrol.FailedJob;
import com.enrichmeai.culvert.jobcontrol.FailureStage;
import com.enrichmeai.culvert.jobcontrol.FdpJobStatus;
import com.enrichmeai.culvert.jobcontrol.JobStatus;
import com.enrichmeai.culvert.jobcontrol.PipelineJob;
import com.enrichmeai.culvert.schema.EntitySchema;

import java.io.InputStream;
import java.io.OutputStream;
import java.time.LocalDate;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * In-memory adapters a Beam worker can rebuild, so a DirectRunner run executes the whole ingestion
 * flow rather than stopping at the first real cloud call.
 *
 * <p>A worker never sees the adapters the driver registered: {@code DefaultRuntimeContext} rebuilds
 * its registry from {@code ServiceLoader} after Beam serializes it (see {@code IngestionStageTest}).
 * These three providers are registered in this module's test {@code META-INF/services}, and each
 * delegates to one shared double the test seeds and reads. The DirectRunner runs in the test's JVM,
 * so the worker and the test see the same instances.
 *
 * <p>They report themselves unavailable ({@link ProviderAvailability}) until {@link #install} turns
 * them on and selects them over the GCS and BigQuery providers, so no other test sees them.
 *
 * <p>The switch, the selectors and the doubles are JVM-wide (system properties and static
 * fields), so a test that installs them must not run in parallel with another test in the same
 * JVM. Surefire runs this module's tests one at a time today.
 */
public final class WorkerDoubles {

    private static final String SWITCH = "culvert.test.worker-doubles";
    private static final Map<String, String> SELECTORS = Map.of(
            "culvert.blobstore.provider", BlobStoreProvider.class.getSimpleName(),
            "culvert.warehouse.provider", WarehouseProvider.class.getSimpleName(),
            "culvert.jobcontrolrepository.provider", JobControlProvider.class.getSimpleName());

    private static InMemoryBlobStore blobStore;
    private static RecordingWarehouse warehouse;
    private static RecordingJobControlRepository jobControl;

    private WorkerDoubles() {
    }

    /** Use these doubles on every worker until {@link #uninstall}. */
    public static void install(InMemoryBlobStore store, RecordingWarehouse wh, RecordingJobControlRepository jc) {
        blobStore = store;
        warehouse = wh;
        jobControl = jc;
        System.setProperty(SWITCH, "true");
        SELECTORS.forEach(System::setProperty);
    }

    public static void uninstall() {
        System.clearProperty(SWITCH);
        SELECTORS.keySet().forEach(System::clearProperty);
        blobStore = null;
        warehouse = null;
        jobControl = null;
    }

    private static boolean on() {
        return Boolean.getBoolean(SWITCH);
    }

    public static final class BlobStoreProvider implements BlobStore, ProviderAvailability {
        @Override public boolean isAvailable() { return on(); }
        @Override public byte[] get(String uri) { return blobStore.get(uri); }
        @Override public InputStream openInput(String uri) { return blobStore.openInput(uri); }
        @Override public OutputStream openOutput(String uri) { return blobStore.openOutput(uri); }
        @Override public void put(String uri, byte[] data) { blobStore.put(uri, data); }
        @Override public Iterator<String> list(String prefix) { return blobStore.list(prefix); }
        @Override public boolean exists(String uri) { return blobStore.exists(uri); }
        @Override public BlobMetadata head(String uri) { return blobStore.head(uri); }
        @Override public void delete(String uri) { blobStore.delete(uri); }
        @Override public void copy(String src, String dst) { blobStore.copy(src, dst); }
    }

    public static final class WarehouseProvider implements Warehouse, ProviderAvailability {
        @Override public boolean isAvailable() { return on(); }
        @Override public Iterator<Map<String, Object>> query(String sql, Map<String, Object> params) {
            return warehouse.query(sql, params);
        }
        @Override public void execute(String sql, Map<String, Object> params) { warehouse.execute(sql, params); }
        @Override public long loadFromUri(String uri, String targetTable, EntitySchema schema, LoadOptions options) {
            return warehouse.loadFromUri(uri, targetTable, schema, options);
        }
        @Override public long merge(String sourceTable, String targetTable, List<String> keys) {
            return warehouse.merge(sourceTable, targetTable, keys);
        }
        @Override public long copy(String sourceTable, String targetTable) {
            return warehouse.copy(sourceTable, targetTable);
        }
        @Override public boolean tableExists(String fqtn) { return warehouse.tableExists(fqtn); }
    }

    public static final class JobControlProvider implements JobControlRepository, ProviderAvailability {
        @Override public boolean isAvailable() { return on(); }
        @Override public void createJob(PipelineJob job) { jobControl.createJob(job); }
        @Override public Optional<PipelineJob> getJob(String runId) { return jobControl.getJob(runId); }
        @Override public void updateStatus(String runId, JobStatus status, Optional<Long> totalRecords) {
            jobControl.updateStatus(runId, status, totalRecords);
        }
        @Override public void markFailed(String runId, String errorCode, String errorMessage,
                                         FailureStage failureStage, Optional<String> errorFilePath) {
            jobControl.markFailed(runId, errorCode, errorMessage, failureStage, errorFilePath);
        }
        @Override public void markRetrying(String runId, int retryCount) { jobControl.markRetrying(runId, retryCount); }
        @Override public List<PipelineJob> getPendingJobs(Optional<String> systemId) {
            return jobControl.getPendingJobs(systemId);
        }
        @Override public List<EntityStatus> getEntityStatus(String systemId, LocalDate extractDate) {
            return jobControl.getEntityStatus(systemId, extractDate);
        }
        @Override public List<FailedJob> getFailedJobs(String systemId, LocalDate extractDate) {
            return jobControl.getFailedJobs(systemId, extractDate);
        }
        @Override public Optional<FdpJobStatus> getFdpJobStatus(String systemId, LocalDate extractDate,
                                                               String modelName) {
            return jobControl.getFdpJobStatus(systemId, extractDate, modelName);
        }
        @Override public int cleanupPartialLoad(String runId, String tableId) {
            return jobControl.cleanupPartialLoad(runId, tableId);
        }
        @Override public void updateCostMetrics(String runId, double estimatedCostUsd,
                                                long billedBytesScanned, long billedBytesWritten) {
            jobControl.updateCostMetrics(runId, estimatedCostUsd, billedBytesScanned, billedBytesWritten);
        }
    }
}
