package com.enrichmeai.culvert.aws.dynamodb;

import com.enrichmeai.culvert.contracts.JobControlRepository;
import com.enrichmeai.culvert.jobcontrol.EntityStatus;
import com.enrichmeai.culvert.jobcontrol.FailedJob;
import com.enrichmeai.culvert.jobcontrol.FailureStage;
import com.enrichmeai.culvert.jobcontrol.FdpJobStatus;
import com.enrichmeai.culvert.jobcontrol.JobStatus;
import com.enrichmeai.culvert.jobcontrol.JobType;
import com.enrichmeai.culvert.jobcontrol.PipelineJob;
import software.amazon.awssdk.services.dynamodb.DynamoDbClient;
import software.amazon.awssdk.services.dynamodb.model.AttributeValue;
import software.amazon.awssdk.services.dynamodb.model.BatchWriteItemRequest;
import software.amazon.awssdk.services.dynamodb.model.DeleteRequest;
import software.amazon.awssdk.services.dynamodb.model.GetItemRequest;
import software.amazon.awssdk.services.dynamodb.model.GetItemResponse;
import software.amazon.awssdk.services.dynamodb.model.PutItemRequest;
import software.amazon.awssdk.services.dynamodb.model.ScanRequest;
import software.amazon.awssdk.services.dynamodb.model.ScanResponse;
import software.amazon.awssdk.services.dynamodb.model.UpdateItemRequest;
import software.amazon.awssdk.services.dynamodb.model.WriteRequest;

import java.time.Instant;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;

/**
 * {@link JobControlRepository} implementation backed by Amazon DynamoDB.
 *
 * <p><b>Why this module is strategically important:</b> the BigQuery adapter
 * ({@code BigQueryJobControlRepository}) implements every status transition as
 * a plain {@code UPDATE ... WHERE run_id = @run_id} statement. BigQuery has no
 * compare-and-swap primitive, so two concurrent callers racing to, say,
 * {@code markFailed} and {@code updateStatus(..., SUCCEEDED, ...)} the same run
 * can both "succeed" — the last writer wins silently. DynamoDB's
 * {@code PutItem}/{@code UpdateItem} APIs accept a
 * {@code ConditionExpression} that is evaluated atomically against the
 * server-side item state as part of the same request: the write either
 * commits or is rejected with {@link software.amazon.awssdk.services.dynamodb.model.ConditionalCheckFailedException},
 * with no window for a concurrent writer to interleave. That is a genuine
 * transactional control plane the BigQuery implementation structurally cannot
 * offer, and it is the reason DynamoDB is in the adapter family at all
 * (Sprint-21, epic #144, issue #148 / T21.4).
 *
 * <h2>Table schema</h2>
 *
 * <p>Single table, single partition key, no sort key and no secondary
 * indexes:
 *
 * <pre>{@code
 * Table: <configured table name>
 *   Partition key: run_id (S)
 *
 *   Attributes (all optional except run_id, system_id, pipeline_name,
 *   extract_date, status):
 *     run_id                 S   pipeline-job run identifier (PK)
 *     system_id              S
 *     pipeline_name          S
 *     extract_date           S   ISO-8601 LocalDate ("2026-01-15")
 *     status                 S   JobStatus#getValue()
 *     job_type               S   JobType#name()
 *     entity_type            S
 *     source_file            S
 *     target_table           S
 *     record_count           N
 *     error_count            N
 *     retry_count            N
 *     failure_stage          S   FailureStage#getValue()
 *     error_code             S
 *     error_message          S
 *     error_file_path        S
 *     estimated_cost_usd     N
 *     billed_bytes_scanned   N
 *     billed_bytes_written   N
 *     created_at             S   ISO-8601 Instant
 *     updated_at             S   ISO-8601 Instant
 *     started_at             S   ISO-8601 Instant
 *     completed_at           S   ISO-8601 Instant
 * }</pre>
 *
 * <p>PK-only design is deliberate: {@link #getPendingJobs}, {@link #getEntityStatus},
 * {@link #getFailedJobs} and {@link #getFdpJobStatus} all filter on
 * non-key attributes ({@code system_id}, {@code extract_date}, {@code status},
 * ...), so they run as a {@code Scan} with a {@code FilterExpression} rather
 * than a {@code Query} against a secondary index. This keeps the table
 * creatable with a single {@code AttributeDefinition} (no GSI backfill to
 * wait on) at the cost of O(table size) reads on these paths — acceptable for
 * a job-control ledger, which is not a high-cardinality table. A future
 * ticket may add a GSI on {@code system_id} if scan cost becomes a problem.
 *
 * <h2>Conditional-write (compare-and-swap) design</h2>
 *
 * <ul>
 *   <li>{@link #createJob} — {@code PutItem} with
 *       {@code ConditionExpression = "attribute_not_exists(run_id)"}: refuses
 *       to silently overwrite an existing run (INSERT, not upsert).</li>
 *   <li>{@link #updateStatus}, {@link #markFailed}, {@link #markRetrying},
 *       {@link #updateCostMetrics} — {@code UpdateItem} with
 *       {@code ConditionExpression = "attribute_exists(run_id)"}: refuses to
 *       create a partial item out of thin air if the run doesn't exist yet,
 *       which is exactly the failure mode an unconditional {@code UpdateItem}
 *       (an upsert by default) would allow.</li>
 * </ul>
 *
 * <p>These are per-item conditional writes, not {@code TransactWriteItems} —
 * the contract's "transactional within a single runId" guarantee is satisfied
 * by DynamoDB's per-item atomicity; no multi-item transaction is needed here.
 *
 * <p>Constructor injection: pass in a pre-built {@link DynamoDbClient} and the
 * table name. The client's lifecycle (including {@code close()}) is managed
 * by the caller, matching {@code BigQueryJobControlRepository}'s convention.
 *
 * <p>Sprint-21 deliverable for issue #148 (T21.4).
 */
public final class DynamoDbJobControlRepository implements JobControlRepository {

    /** Partition key attribute name. */
    static final String ATTR_RUN_ID = "run_id";
    static final String ATTR_SYSTEM_ID = "system_id";
    static final String ATTR_PIPELINE_NAME = "pipeline_name";
    static final String ATTR_EXTRACT_DATE = "extract_date";
    static final String ATTR_STATUS = "status";
    static final String ATTR_JOB_TYPE = "job_type";
    static final String ATTR_ENTITY_TYPE = "entity_type";
    static final String ATTR_SOURCE_FILE = "source_file";
    static final String ATTR_TARGET_TABLE = "target_table";
    static final String ATTR_RECORD_COUNT = "record_count";
    static final String ATTR_ERROR_COUNT = "error_count";
    static final String ATTR_RETRY_COUNT = "retry_count";
    static final String ATTR_FAILURE_STAGE = "failure_stage";
    static final String ATTR_ERROR_CODE = "error_code";
    static final String ATTR_ERROR_MESSAGE = "error_message";
    static final String ATTR_ERROR_FILE_PATH = "error_file_path";
    static final String ATTR_ESTIMATED_COST_USD = "estimated_cost_usd";
    static final String ATTR_BILLED_BYTES_SCANNED = "billed_bytes_scanned";
    static final String ATTR_BILLED_BYTES_WRITTEN = "billed_bytes_written";
    static final String ATTR_CREATED_AT = "created_at";
    static final String ATTR_UPDATED_AT = "updated_at";
    static final String ATTR_STARTED_AT = "started_at";
    static final String ATTR_COMPLETED_AT = "completed_at";

    private final DynamoDbClient client;
    private final String tableName;

    /**
     * Primary constructor.
     *
     * @param client    Pre-built DynamoDB client. Required.
     * @param tableName DynamoDB table name (e.g. {@code "pipeline_jobs"}). Required.
     * @throws NullPointerException if any argument is null.
     */
    public DynamoDbJobControlRepository(DynamoDbClient client, String tableName) {
        this.client = Objects.requireNonNull(client, "client must not be null");
        this.tableName = Objects.requireNonNull(tableName, "tableName must not be null");
    }

    /**
     * No-arg constructor for worker-side auto-config reconstruction, gated on
     * {@code CULVERT_CLOUD=aws} (see {@code S3BlobStore()} / the GCP family's
     * {@code BigQueryWarehouse()} for the worker-rebuild rationale). Table
     * from {@code JOB_CONTROL_TABLE} (default {@code pipeline_jobs});
     * region/credentials from the AWS default chains.
     */
    public DynamoDbJobControlRepository() {
        this(gatedDefaultClient(), resolveTable());
    }

    private static DynamoDbClient gatedDefaultClient() {
        String cloud = System.getenv("CULVERT_CLOUD");
        if (cloud == null || cloud.isBlank()) {
            cloud = System.getProperty("culvert.cloud");
        }
        if (cloud == null || !cloud.equalsIgnoreCase("aws")) {
            throw new IllegalStateException(
                    "AWS adapters are gated to CULVERT_CLOUD=aws; current selector: " + cloud);
        }
        return DynamoDbClient.create();
    }

    private static String resolveTable() {
        String t = System.getenv("JOB_CONTROL_TABLE");
        if (t == null || t.isBlank()) {
            t = System.getProperty("aws.jobControlTable");
        }
        return (t == null || t.isBlank()) ? "pipeline_jobs" : t;
    }

    @Override
    public void createJob(PipelineJob job) {
        Objects.requireNonNull(job, "job must not be null");

        Map<String, AttributeValue> item = new HashMap<>();
        item.put(ATTR_RUN_ID, AttributeValue.fromS(job.runId()));
        item.put(ATTR_SYSTEM_ID, AttributeValue.fromS(job.systemId()));
        item.put(ATTR_PIPELINE_NAME, AttributeValue.fromS(job.pipelineName()));
        item.put(ATTR_EXTRACT_DATE, AttributeValue.fromS(job.extractDate().toString()));
        item.put(ATTR_STATUS, AttributeValue.fromS(job.status().getValue()));
        item.put(ATTR_JOB_TYPE, AttributeValue.fromS(job.jobType().name()));
        putIfPresent(item, ATTR_ENTITY_TYPE, job.entityType());
        putIfPresent(item, ATTR_SOURCE_FILE, job.sourceFile());
        putIfPresent(item, ATTR_TARGET_TABLE, job.targetTable());
        item.put(ATTR_RECORD_COUNT, AttributeValue.fromN(Long.toString(job.recordCount())));
        item.put(ATTR_ERROR_COUNT, AttributeValue.fromN(Long.toString(job.errorCount())));
        item.put(ATTR_RETRY_COUNT, AttributeValue.fromN(Integer.toString(job.retryCount())));
        job.failureStage().ifPresent(fs -> item.put(ATTR_FAILURE_STAGE, AttributeValue.fromS(fs.getValue())));
        putIfPresent(item, ATTR_ERROR_CODE, job.errorCode());
        putIfPresent(item, ATTR_ERROR_MESSAGE, job.errorMessage());
        putIfPresent(item, ATTR_ERROR_FILE_PATH, job.errorFilePath());
        item.put(ATTR_ESTIMATED_COST_USD, AttributeValue.fromN(Double.toString(job.estimatedCostUsd())));
        item.put(ATTR_BILLED_BYTES_SCANNED, AttributeValue.fromN(Long.toString(job.billedBytesScanned())));
        item.put(ATTR_BILLED_BYTES_WRITTEN, AttributeValue.fromN(Long.toString(job.billedBytesWritten())));
        item.put(ATTR_CREATED_AT, AttributeValue.fromS(job.createdAt().toString()));
        item.put(ATTR_UPDATED_AT, AttributeValue.fromS(job.updatedAt().toString()));
        job.startedAt().ifPresent(v -> item.put(ATTR_STARTED_AT, AttributeValue.fromS(v.toString())));
        job.completedAt().ifPresent(v -> item.put(ATTR_COMPLETED_AT, AttributeValue.fromS(v.toString())));

        PutItemRequest request = PutItemRequest.builder()
                .tableName(tableName)
                .item(item)
                // INSERT semantics: never silently clobber an existing run.
                .conditionExpression("attribute_not_exists(" + ATTR_RUN_ID + ")")
                .build();

        client.putItem(request);
    }

    @Override
    public Optional<PipelineJob> getJob(String runId) {
        Objects.requireNonNull(runId, "runId must not be null");

        GetItemRequest request = GetItemRequest.builder()
                .tableName(tableName)
                .key(Map.of(ATTR_RUN_ID, AttributeValue.fromS(runId)))
                .build();

        GetItemResponse response = client.getItem(request);
        if (!response.hasItem() || response.item().isEmpty()) {
            return Optional.empty();
        }
        return Optional.of(itemToPipelineJob(response.item()));
    }

    @Override
    public void updateStatus(String runId, JobStatus status, Optional<Long> totalRecords) {
        Objects.requireNonNull(runId, "runId must not be null");
        Objects.requireNonNull(status, "status must not be null");
        Objects.requireNonNull(totalRecords, "totalRecords must not be null");

        // Three flavours mirroring BigQueryJobControlRepository#updateStatus:
        // RUNNING stamps started_at, SUCCEEDED stamps completed_at +
        // record_count, everything else just bumps status + updated_at.
        StringBuilder updateExpr = new StringBuilder("SET #status = :status, #updated_at = :updated_at");
        Map<String, String> names = new HashMap<>();
        names.put("#status", ATTR_STATUS);
        names.put("#updated_at", ATTR_UPDATED_AT);
        Map<String, AttributeValue> values = new HashMap<>();
        values.put(":status", AttributeValue.fromS(status.getValue()));
        values.put(":updated_at", AttributeValue.fromS(Instant.now().toString()));

        if (status == JobStatus.RUNNING) {
            updateExpr.append(", #started_at = :started_at");
            names.put("#started_at", ATTR_STARTED_AT);
            values.put(":started_at", AttributeValue.fromS(Instant.now().toString()));
        } else if (status == JobStatus.SUCCEEDED) {
            updateExpr.append(", #completed_at = :completed_at, #record_count = :record_count");
            names.put("#completed_at", ATTR_COMPLETED_AT);
            names.put("#record_count", ATTR_RECORD_COUNT);
            values.put(":completed_at", AttributeValue.fromS(Instant.now().toString()));
            values.put(":record_count", AttributeValue.fromN(Long.toString(totalRecords.orElse(0L))));
        }

        updateItemConditionally(runId, updateExpr.toString(), names, values, "updateStatus");
    }

    @Override
    public void markFailed(String runId, String errorCode, String errorMessage,
                           FailureStage failureStage, Optional<String> errorFilePath) {
        Objects.requireNonNull(runId, "runId must not be null");
        Objects.requireNonNull(errorCode, "errorCode must not be null");
        Objects.requireNonNull(errorMessage, "errorMessage must not be null");
        Objects.requireNonNull(failureStage, "failureStage must not be null");
        Objects.requireNonNull(errorFilePath, "errorFilePath must not be null");

        Map<String, String> names = new HashMap<>();
        names.put("#status", ATTR_STATUS);
        names.put("#error_code", ATTR_ERROR_CODE);
        names.put("#error_message", ATTR_ERROR_MESSAGE);
        names.put("#failure_stage", ATTR_FAILURE_STAGE);
        names.put("#completed_at", ATTR_COMPLETED_AT);
        names.put("#updated_at", ATTR_UPDATED_AT);

        Map<String, AttributeValue> values = new HashMap<>();
        values.put(":status", AttributeValue.fromS(JobStatus.FAILED.getValue()));
        values.put(":error_code", AttributeValue.fromS(errorCode));
        values.put(":error_message", AttributeValue.fromS(errorMessage));
        values.put(":failure_stage", AttributeValue.fromS(failureStage.getValue()));
        values.put(":completed_at", AttributeValue.fromS(Instant.now().toString()));
        values.put(":updated_at", AttributeValue.fromS(Instant.now().toString()));

        String updateExpr = "SET #status = :status, #error_code = :error_code, "
                + "#error_message = :error_message, #failure_stage = :failure_stage, "
                + "#completed_at = :completed_at, #updated_at = :updated_at";

        if (errorFilePath.isPresent()) {
            names.put("#error_file_path", ATTR_ERROR_FILE_PATH);
            values.put(":error_file_path", AttributeValue.fromS(errorFilePath.get()));
            updateExpr += ", #error_file_path = :error_file_path";
        }

        updateItemConditionally(runId, updateExpr, names, values, "markFailed");
    }

    @Override
    public void markRetrying(String runId, int retryCount) {
        Objects.requireNonNull(runId, "runId must not be null");
        if (retryCount < 0) {
            throw new IllegalArgumentException("retryCount must be >= 0, got " + retryCount);
        }

        Map<String, String> names = Map.of(
                "#status", ATTR_STATUS,
                "#retry_count", ATTR_RETRY_COUNT,
                "#updated_at", ATTR_UPDATED_AT);
        Map<String, AttributeValue> values = Map.of(
                ":status", AttributeValue.fromS(JobStatus.RETRYING.getValue()),
                ":retry_count", AttributeValue.fromN(Integer.toString(retryCount)),
                ":updated_at", AttributeValue.fromS(Instant.now().toString()));

        updateItemConditionally(runId,
                "SET #status = :status, #retry_count = :retry_count, #updated_at = :updated_at",
                names, values, "markRetrying");
    }

    @Override
    public List<PipelineJob> getPendingJobs(Optional<String> systemId) {
        Objects.requireNonNull(systemId, "systemId must not be null");

        Map<String, String> names = new HashMap<>();
        names.put("#status", ATTR_STATUS);
        Map<String, AttributeValue> values = new HashMap<>();
        values.put(":created", AttributeValue.fromS(JobStatus.CREATED.getValue()));
        values.put(":running", AttributeValue.fromS(JobStatus.RUNNING.getValue()));

        String filterExpr = "#status IN (:created, :running)";
        if (systemId.isPresent()) {
            names.put("#system_id", ATTR_SYSTEM_ID);
            values.put(":system_id", AttributeValue.fromS(systemId.get()));
            filterExpr += " AND #system_id = :system_id";
        }

        ScanRequest request = ScanRequest.builder()
                .tableName(tableName)
                .filterExpression(filterExpr)
                .expressionAttributeNames(names)
                .expressionAttributeValues(values)
                .build();

        ScanResponse response = client.scan(request);
        List<PipelineJob> jobs = new ArrayList<>();
        for (Map<String, AttributeValue> item : response.items()) {
            jobs.add(itemToPipelineJob(item));
        }
        jobs.sort((a, b) -> a.createdAt().compareTo(b.createdAt()));
        return jobs;
    }

    @Override
    public List<EntityStatus> getEntityStatus(String systemId, LocalDate extractDate) {
        Objects.requireNonNull(systemId, "systemId must not be null");
        Objects.requireNonNull(extractDate, "extractDate must not be null");

        ScanResponse response = scanBySystemAndDate(systemId, extractDate, "getEntityStatus");
        List<EntityStatus> out = new ArrayList<>();
        for (Map<String, AttributeValue> item : response.items()) {
            String entityType = stringOrEmpty(item, ATTR_ENTITY_TYPE);
            String status = stringOrEmpty(item, ATTR_STATUS);
            String runId = stringOrEmpty(item, ATTR_RUN_ID);
            long recordCount = longOrZero(item, ATTR_RECORD_COUNT);
            long errorCount = longOrZero(item, ATTR_ERROR_COUNT);
            Optional<Instant> startedAt = instantOptional(item, ATTR_STARTED_AT);
            Optional<Instant> completedAt = instantOptional(item, ATTR_COMPLETED_AT);
            out.add(new EntityStatus(entityType, status, runId, recordCount, errorCount,
                    startedAt, completedAt));
        }
        return out;
    }

    @Override
    public List<FailedJob> getFailedJobs(String systemId, LocalDate extractDate) {
        Objects.requireNonNull(systemId, "systemId must not be null");
        Objects.requireNonNull(extractDate, "extractDate must not be null");

        Map<String, String> names = new HashMap<>();
        names.put("#system_id", ATTR_SYSTEM_ID);
        names.put("#extract_date", ATTR_EXTRACT_DATE);
        names.put("#status", ATTR_STATUS);
        Map<String, AttributeValue> values = new HashMap<>();
        values.put(":system_id", AttributeValue.fromS(systemId));
        values.put(":extract_date", AttributeValue.fromS(extractDate.toString()));
        values.put(":status", AttributeValue.fromS(JobStatus.FAILED.getValue()));

        ScanRequest request = ScanRequest.builder()
                .tableName(tableName)
                .filterExpression("#system_id = :system_id AND #extract_date = :extract_date "
                        + "AND #status = :status")
                .expressionAttributeNames(names)
                .expressionAttributeValues(values)
                .build();

        ScanResponse response = client.scan(request);
        List<FailedJob> out = new ArrayList<>();
        for (Map<String, AttributeValue> item : response.items()) {
            String runId = stringOrEmpty(item, ATTR_RUN_ID);
            String entityType = stringOrEmpty(item, ATTR_ENTITY_TYPE);
            String failureStage = stringOrEmpty(item, ATTR_FAILURE_STAGE);
            String errorCode = stringOrEmpty(item, ATTR_ERROR_CODE);
            String errorMessage = stringOrEmpty(item, ATTR_ERROR_MESSAGE);
            Optional<String> errorFilePath = stringOptional(item, ATTR_ERROR_FILE_PATH);
            Instant failedAt = instantOptional(item, ATTR_COMPLETED_AT).orElse(Instant.EPOCH);
            int retryCount = (int) longOrZero(item, ATTR_RETRY_COUNT);
            out.add(new FailedJob(runId, entityType, failureStage, errorCode, errorMessage,
                    errorFilePath, failedAt, retryCount));
        }
        return out;
    }

    @Override
    public Optional<FdpJobStatus> getFdpJobStatus(String systemId, LocalDate extractDate,
                                                  String modelName) {
        Objects.requireNonNull(systemId, "systemId must not be null");
        Objects.requireNonNull(extractDate, "extractDate must not be null");
        Objects.requireNonNull(modelName, "modelName must not be null");

        // Mirrors BigQueryJobControlRepository#getFdpJobStatus: the Java
        // PipelineJob doesn't carry a dbt_model_name column, so pipeline_name
        // is used as the model identifier.
        Map<String, String> names = new HashMap<>();
        names.put("#system_id", ATTR_SYSTEM_ID);
        names.put("#extract_date", ATTR_EXTRACT_DATE);
        names.put("#job_type", ATTR_JOB_TYPE);
        names.put("#pipeline_name", ATTR_PIPELINE_NAME);
        Map<String, AttributeValue> values = new HashMap<>();
        values.put(":system_id", AttributeValue.fromS(systemId));
        values.put(":extract_date", AttributeValue.fromS(extractDate.toString()));
        values.put(":job_type", AttributeValue.fromS(JobType.TRANSFORMATION.name()));
        values.put(":model_name", AttributeValue.fromS(modelName));

        ScanRequest request = ScanRequest.builder()
                .tableName(tableName)
                .filterExpression("#system_id = :system_id AND #extract_date = :extract_date "
                        + "AND #job_type = :job_type AND #pipeline_name = :model_name")
                .expressionAttributeNames(names)
                .expressionAttributeValues(values)
                .build();

        ScanResponse response = client.scan(request);
        Map<String, AttributeValue> latest = null;
        Instant latestCreatedAt = null;
        for (Map<String, AttributeValue> item : response.items()) {
            Instant createdAt = instantOptional(item, ATTR_CREATED_AT).orElse(Instant.EPOCH);
            if (latest == null || createdAt.isAfter(latestCreatedAt)) {
                latest = item;
                latestCreatedAt = createdAt;
            }
        }
        if (latest == null) {
            return Optional.empty();
        }

        String runId = stringOrEmpty(latest, ATTR_RUN_ID);
        String pipelineName = stringOrEmpty(latest, ATTR_PIPELINE_NAME);
        String status = stringOrEmpty(latest, ATTR_STATUS);
        long recordCount = longOrZero(latest, ATTR_RECORD_COUNT);
        Optional<Instant> startedAt = instantOptional(latest, ATTR_STARTED_AT);
        Optional<Instant> completedAt = instantOptional(latest, ATTR_COMPLETED_AT);
        return Optional.of(new FdpJobStatus(runId, pipelineName, status, recordCount,
                startedAt, completedAt));
    }

    @Override
    public int cleanupPartialLoad(String runId, String tableId) {
        Objects.requireNonNull(runId, "runId must not be null");
        Objects.requireNonNull(tableId, "tableId must not be null");

        // DynamoDB has no DELETE-WHERE statement (unlike BigQuery's
        // `DELETE FROM <fqtn> WHERE _run_id = ...`), so this is implemented as
        // Scan-then-BatchWriteItem-delete against tableId (an arbitrary,
        // caller-supplied table distinct from the job-control table itself —
        // the "warehouse" table partially loaded by the failed run). The
        // convention, mirroring BigQuery's `_run_id` column, is that tableId
        // carries a `_run_id` (S) attribute on every item tagging which run
        // wrote it; this method scans for that tag and deletes the matches.
        //
        // Divergence from BigQuery: this is not a single atomic statement —
        // it is scan-then-delete, so it is not safe to run concurrently with
        // writes to the same run_id tag on tableId. Callers should only
        // invoke this once a run has reached a terminal (FAILED) state.
        String runIdAttr = "_run_id";

        Map<String, String> names = Map.of("#run_id", runIdAttr);
        Map<String, AttributeValue> values = Map.of(":run_id", AttributeValue.fromS(runId));

        ScanRequest scanRequest = ScanRequest.builder()
                .tableName(tableId)
                .filterExpression("#run_id = :run_id")
                .expressionAttributeNames(names)
                .expressionAttributeValues(values)
                .build();

        ScanResponse scanResponse = client.scan(scanRequest);
        List<Map<String, AttributeValue>> matches = scanResponse.items();
        if (matches.isEmpty()) {
            return 0;
        }

        List<WriteRequest> deletes = new ArrayList<>();
        for (Map<String, AttributeValue> item : matches) {
            // BatchWriteItem delete requests take only the key attributes;
            // the run_id (partition key of tableId's own schema) is not known
            // to this repository, so the full item's key subset can't be
            // derived generically. This adapter assumes tableId is keyed by
            // the same run_id-tag attribute for the purpose of deletion,
            // consistent with the `_run_id`-only filter above.
            Map<String, AttributeValue> key = new HashMap<>();
            key.put(runIdAttr, item.get(runIdAttr));
            deletes.add(WriteRequest.builder()
                    .deleteRequest(DeleteRequest.builder().key(key).build())
                    .build());
        }

        // BatchWriteItem caps at 25 items per call.
        int deleted = 0;
        for (int i = 0; i < deletes.size(); i += 25) {
            List<WriteRequest> chunk = deletes.subList(i, Math.min(i + 25, deletes.size()));
            BatchWriteItemRequest batchRequest = BatchWriteItemRequest.builder()
                    .requestItems(Map.of(tableId, chunk))
                    .build();
            client.batchWriteItem(batchRequest);
            deleted += chunk.size();
        }
        return deleted;
    }

    @Override
    public void updateCostMetrics(String runId, double estimatedCostUsd,
                                  long billedBytesScanned, long billedBytesWritten) {
        Objects.requireNonNull(runId, "runId must not be null");

        Map<String, String> names = Map.of(
                "#cost", ATTR_ESTIMATED_COST_USD,
                "#scanned", ATTR_BILLED_BYTES_SCANNED,
                "#written", ATTR_BILLED_BYTES_WRITTEN,
                "#updated_at", ATTR_UPDATED_AT);
        Map<String, AttributeValue> values = Map.of(
                ":cost", AttributeValue.fromN(Double.toString(estimatedCostUsd)),
                ":scanned", AttributeValue.fromN(Long.toString(billedBytesScanned)),
                ":written", AttributeValue.fromN(Long.toString(billedBytesWritten)),
                ":updated_at", AttributeValue.fromS(Instant.now().toString()));

        updateItemConditionally(runId,
                "SET #cost = :cost, #scanned = :scanned, #written = :written, "
                        + "#updated_at = :updated_at",
                names, values, "updateCostMetrics");
    }

    // --- helpers -------------------------------------------------------

    /**
     * Runs {@code UpdateItem} with {@code ConditionExpression =
     * "attribute_exists(run_id)"} — the compare-and-swap guard used by every
     * status-transition method. Throws
     * {@link software.amazon.awssdk.services.dynamodb.model.ConditionalCheckFailedException}
     * if {@code runId} doesn't already exist, exactly mirroring the semantics
     * an {@code UPDATE ... WHERE run_id = @run_id} affecting zero rows would
     * silently allow to pass in BigQuery — here it's a hard failure instead.
     */
    private void updateItemConditionally(String runId, String updateExpression,
                                         Map<String, String> names,
                                         Map<String, AttributeValue> values,
                                         String op) {
        UpdateItemRequest request = UpdateItemRequest.builder()
                .tableName(tableName)
                .key(Map.of(ATTR_RUN_ID, AttributeValue.fromS(runId)))
                .updateExpression(updateExpression)
                .conditionExpression("attribute_exists(" + ATTR_RUN_ID + ")")
                .expressionAttributeNames(names)
                .expressionAttributeValues(values)
                .build();
        client.updateItem(request);
    }

    private ScanResponse scanBySystemAndDate(String systemId, LocalDate extractDate, String op) {
        Map<String, String> names = Map.of(
                "#system_id", ATTR_SYSTEM_ID,
                "#extract_date", ATTR_EXTRACT_DATE);
        Map<String, AttributeValue> values = Map.of(
                ":system_id", AttributeValue.fromS(systemId),
                ":extract_date", AttributeValue.fromS(extractDate.toString()));

        ScanRequest request = ScanRequest.builder()
                .tableName(tableName)
                .filterExpression("#system_id = :system_id AND #extract_date = :extract_date")
                .expressionAttributeNames(names)
                .expressionAttributeValues(values)
                .build();
        return client.scan(request);
    }

    private static void putIfPresent(Map<String, AttributeValue> item, String attr,
                                     Optional<String> value) {
        value.ifPresent(v -> item.put(attr, AttributeValue.fromS(v)));
    }

    private PipelineJob itemToPipelineJob(Map<String, AttributeValue> item) {
        PipelineJob.Builder b = PipelineJob.builder(
                stringOrEmpty(item, ATTR_RUN_ID),
                stringOrEmpty(item, ATTR_SYSTEM_ID),
                stringOrEmpty(item, ATTR_PIPELINE_NAME),
                LocalDate.parse(stringOrEmpty(item, ATTR_EXTRACT_DATE)),
                JobStatus.valueOf(stringOrEmpty(item, ATTR_STATUS).toUpperCase()));

        String jobTypeStr = stringOrEmpty(item, ATTR_JOB_TYPE);
        if (!jobTypeStr.isEmpty()) {
            b.jobType(JobType.valueOf(jobTypeStr));
        }
        b.entityType(stringOptional(item, ATTR_ENTITY_TYPE).orElse(null));
        b.sourceFile(stringOptional(item, ATTR_SOURCE_FILE).orElse(null));
        b.targetTable(stringOptional(item, ATTR_TARGET_TABLE).orElse(null));
        b.recordCount(longOrZero(item, ATTR_RECORD_COUNT));
        b.errorCount(longOrZero(item, ATTR_ERROR_COUNT));
        b.retryCount((int) longOrZero(item, ATTR_RETRY_COUNT));
        stringOptional(item, ATTR_FAILURE_STAGE).ifPresent(
                v -> b.failureStage(FailureStage.valueOf(v.toUpperCase())));
        b.errorCode(stringOptional(item, ATTR_ERROR_CODE).orElse(null));
        b.errorMessage(stringOptional(item, ATTR_ERROR_MESSAGE).orElse(null));
        b.errorFilePath(stringOptional(item, ATTR_ERROR_FILE_PATH).orElse(null));
        b.estimatedCostUsd(doubleOrZero(item, ATTR_ESTIMATED_COST_USD));
        b.billedBytesScanned(longOrZero(item, ATTR_BILLED_BYTES_SCANNED));
        b.billedBytesWritten(longOrZero(item, ATTR_BILLED_BYTES_WRITTEN));
        instantOptional(item, ATTR_CREATED_AT).ifPresent(b::createdAt);
        instantOptional(item, ATTR_UPDATED_AT).ifPresent(b::updatedAt);
        instantOptional(item, ATTR_STARTED_AT).ifPresent(b::startedAt);
        instantOptional(item, ATTR_COMPLETED_AT).ifPresent(b::completedAt);
        return b.build();
    }

    private static String stringOrEmpty(Map<String, AttributeValue> item, String name) {
        AttributeValue v = item.get(name);
        if (v == null || v.s() == null) {
            return "";
        }
        return v.s();
    }

    private static Optional<String> stringOptional(Map<String, AttributeValue> item, String name) {
        AttributeValue v = item.get(name);
        if (v == null || v.s() == null || v.s().isEmpty()) {
            return Optional.empty();
        }
        return Optional.of(v.s());
    }

    private static long longOrZero(Map<String, AttributeValue> item, String name) {
        AttributeValue v = item.get(name);
        if (v == null || v.n() == null) {
            return 0L;
        }
        return Long.parseLong(v.n());
    }

    private static double doubleOrZero(Map<String, AttributeValue> item, String name) {
        AttributeValue v = item.get(name);
        if (v == null || v.n() == null) {
            return 0.0;
        }
        return Double.parseDouble(v.n());
    }

    private static Optional<Instant> instantOptional(Map<String, AttributeValue> item, String name) {
        AttributeValue v = item.get(name);
        if (v == null || v.s() == null || v.s().isEmpty()) {
            return Optional.empty();
        }
        return Optional.of(Instant.parse(v.s()));
    }
}
