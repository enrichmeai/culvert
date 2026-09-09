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
import software.amazon.awssdk.services.dynamodb.model.PutItemRequest;
import software.amazon.awssdk.services.dynamodb.model.QueryRequest;
import software.amazon.awssdk.services.dynamodb.model.QueryResponse;
import software.amazon.awssdk.services.dynamodb.model.ScanRequest;
import software.amazon.awssdk.services.dynamodb.model.ScanResponse;
import software.amazon.awssdk.services.dynamodb.model.WriteRequest;

import java.time.Instant;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.EnumSet;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;
import java.util.concurrent.ThreadLocalRandom;
import java.util.concurrent.atomic.AtomicLong;

/**
 * {@link JobControlRepository} implementation backed by Amazon DynamoDB.
 *
 * <p>The AWS sibling of {@code BigQueryJobControlRepository}, and — since this
 * change — append-only on the same terms (AD-2/AD-3/AD-13). Where the BigQuery
 * adapter expresses the projection as SQL, this one expresses the same
 * semantics with a sort key and a fold; the guarantees are identical, the
 * mechanism is not.
 *
 * <h2>Table schema</h2>
 *
 * <p>Single table, <strong>composite key</strong>, no secondary indexes:
 *
 * <pre>{@code
 * Table: <configured table name>
 *   Partition key: run_id    (S)   -- one partition per pipeline-job run
 *   Sort key:      event_seq (S)   -- one item per state change, ascending in time
 *
 *   Attributes (all optional except run_id, event_seq, system_id,
 *   pipeline_name, extract_date, status):
 *     run_id                 S   pipeline-job run identifier (PK)
 *     event_seq              S   append order (SK) -- see "Ordering" below
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
 * <p><strong>The sort key is a breaking schema change.</strong> A table
 * created for the previous PK-only version cannot serve this class; it must be
 * recreated with the {@code event_seq} range key above.
 *
 * <h2>Append-only writes (AD-2)</h2>
 *
 * <p>Nothing in this class calls {@code UpdateItem} any more, and no
 * {@code DeleteItem}/{@code BatchWriteItem} ever targets the job-control table.
 * Every state change — {@link #updateStatus}, {@link #markFailed},
 * {@link #markRetrying}, {@link #updateCostMetrics} — reads the run's projected
 * state, carries the whole of it forward, applies its own change and
 * {@code PutItem}s the result as a <em>new item</em> under a new
 * {@code event_seq}. Earlier items are never touched.
 *
 * <p>{@link #createJob} keeps its atomic INSERT semantics despite the new sort
 * key: the {@code created} item is always written at the fixed sentinel
 * {@code event_seq} {@value #CREATE_EVENT_SEQ}, so
 * {@code attribute_not_exists(run_id)} is evaluated against precisely the item
 * a second create would collide with, and a duplicate still raises
 * {@link software.amazon.awssdk.services.dynamodb.model.ConditionalCheckFailedException}
 * server-side with no read-then-write window. The sentinel is all-zero and
 * therefore sorts below every generated key, so a run's history always begins
 * with its {@code created} item. (This is the one guarantee this adapter has
 * that BigQuery's {@code MERGE ... WHEN NOT MATCHED} equivalent expresses as an
 * {@code IllegalStateException} instead.)
 *
 * <p>{@link #cleanupPartialLoad} holds the only deletes in the class, and they
 * target the <em>caller-supplied warehouse table</em>, never the ledger.
 *
 * <h2>Reads are a projection; the first terminal state is final (AD-3)</h2>
 *
 * <p>A run has many items, so every read folds a run's items — in
 * {@code event_seq} order — down to one, in {@link #project}:
 *
 * <ul>
 *   <li>before any terminal state, the latest item wins;
 *   <li>the first terminal item ({@code succeeded}, {@code failed},
 *       {@code cancelled}) <strong>freezes</strong> the projection: later
 *       contradicting items are recorded but do not change what the run reads
 *       as. There is no exception, {@code retrying} included -- see the retry
 *       model below.
 * </ul>
 *
 * <p>Earliest-terminal rather than latest-item is the point, not an
 * optimisation. Under plain recency a late {@code failed} append would flip a
 * finished {@code succeeded} run to {@code failed}; {@code failed} is
 * retryable, so {@code RetryOrchestrator.prepareRetry} would then call
 * {@link #cleanupPartialLoad} and delete the rows the successful run had just
 * loaded. Making the first terminal state final closes that data-loss path,
 * which is why {@code DynamoDbJobControlProjectionTest} pins it against a
 * contradicting item injected straight into the ledger, behind this class's
 * back.
 *
 * <h3>The retry model: a failed run is never revived in place</h3>
 *
 * <p>{@code failed} is terminal like the other two, so a {@code retrying} item
 * appended afterwards is recorded and then loses the projection -- the run
 * still reads {@code FAILED}. That is the contract, not a limitation:
 * {@code docs/CONTRACT.md} section 7 requires a retried pipeline to take a
 * <strong>new {@code run_id}</strong>, carrying the old one in the retry
 * event's {@code previous_run_id}. Reviving a failed run in place would mean a
 * later item overturning a terminal state, which is the one thing AD-3 exists
 * to forbid. {@link #markRetrying} therefore still accepts the append (it
 * records the intent, and {@code RetryOrchestrator} calls it) but callers read
 * the retry's status from the new run.
 *
 * <h3>Why a fold rather than a cleverer query</h3>
 *
 * <p>DynamoDB has no window functions, so the projection had to be designed
 * rather than translated. The tempting server-side shape -- a {@code Query}
 * filtered to the terminal statuses, ascending, {@code Limit 1}, with a second
 * descending query as the fallback -- does not actually save the read:
 * DynamoDB applies {@code Limit} to the items <em>examined</em>, before the
 * {@code FilterExpression}, so that query returns an empty page plus a
 * continuation token and has to be looped until the partition is exhausted. It
 * would also cost two round trips per read and put status precedence into the
 * key's ordering, where a new {@link JobStatus} would silently re-rank history.
 * Folding a single-partition {@code Query} here reads the same items once,
 * keeps the precedence rule in one readable place next to the guard that
 * mirrors it, and is linear in a run's state changes.
 *
 * <h2>Scans filter on immutable attributes only</h2>
 *
 * <p>{@link #getPendingJobs}, {@link #getEntityStatus}, {@link #getFailedJobs}
 * and {@link #getFdpJobStatus} run as a {@code Scan} with a
 * {@code FilterExpression}, group the matched items by {@code run_id}, project
 * each run, and only then filter on status. The filter expression may name
 * <strong>only</strong> attributes every append carries forward unchanged —
 * {@code run_id}, {@code system_id}, {@code extract_date}, {@code job_type},
 * {@code pipeline_name}. A {@code status} predicate in the scan would hand the
 * fold a partition stripped of its winning item, resurrecting the superseded
 * state the projection exists to hide: a run that has since succeeded still has
 * its old {@code running} item, and would come back pending.
 *
 * <p>PK-only-scan cost is unchanged in kind by the rewrite (O(table size) on
 * these paths) but the table now grows per state change rather than per run.
 * A GSI on {@code system_id} remains the escape hatch if that becomes a
 * problem. Every read paginates: with one item per state change, a run's
 * history and a system's scan both outgrow DynamoDB's 1&nbsp;MB page far sooner
 * than the old one-item-per-run table did, and an unpaginated read would
 * silently project half a history.
 *
 * <h2>Illegal transitions</h2>
 *
 * <p>An append cannot fail on a guard the way the conditional {@code UpdateItem}
 * it replaced did, so the guard moves ahead of the write: each transition reads
 * the projected current state and rejects a prior state
 * {@link #allowedPriorStates} does not permit, raising
 * {@link IllegalStateException} with the same wording as the BigQuery adapter.
 * Consequently a transition on a run that does not exist now raises
 * {@code IllegalStateException} rather than
 * {@code ConditionalCheckFailedException}.
 *
 * <p><strong>Read-then-append is not atomic.</strong> Two writers racing the
 * same transition can both read the same prior state and both append. Nothing
 * is overwritten, both items survive, and the projection still resolves the
 * read deterministically — the trade AD-2 asks for, and the reason the
 * projection, not the guard, is the load-bearing half of AD-3.
 *
 * <p><strong>{@link #updateCostMetrics} on a run that has already reached a
 * terminal state is write-only</strong>, exactly as in BigQuery: the appended
 * item carries the run's terminal status, so the frozen projection keeps
 * winning and the new figures never read back through this class. Call it
 * before the run finishes if the figure has to be visible.
 *
 * <p>Constructor injection: pass in a pre-built {@link DynamoDbClient} and the
 * table name. The client's lifecycle (including {@code close()}) is managed by
 * the caller, matching {@code BigQueryJobControlRepository}'s convention.
 *
 * <p>Sprint-21 deliverable for issue #148 (T21.4); made append-only in
 * Sprint 23 (AD-2/AD-3/AD-12/AD-13).
 */
public final class DynamoDbJobControlRepository implements JobControlRepository {

    /** Partition key attribute name. */
    static final String ATTR_RUN_ID = "run_id";
    /** Sort key attribute name: the append order of a run's state changes. */
    static final String ATTR_EVENT_SEQ = "event_seq";
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

    /**
     * The {@code event_seq} every {@code created} item is written under. Fixed
     * (so {@code attribute_not_exists} still makes {@link #createJob} an atomic
     * INSERT) and all-zero (so it sorts below every generated key).
     */
    static final String CREATE_EVENT_SEQ = "00000000000000000000-create";

    /**
     * The statuses a run cannot leave (AD-3). The first of these a run reaches
     * freezes its projection: nothing appended afterwards changes what the run
     * reads as. Identical to {@code BigQueryJobControlRepository.TERMINAL_STATES}
     * (BigQueryJobControlRepository.java:162-163).
     */
    private static final Set<JobStatus> TERMINAL_STATES =
            EnumSet.of(JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED);

    /**
     * Guards {@code event_seq} uniqueness and monotonicity within this JVM.
     * {@code Instant.now()} is only microsecond-resolution on common platforms,
     * so two appends in quick succession can share a timestamp; a collision on
     * a composite key would <em>overwrite</em> an item, which is precisely what
     * append-only forbids. Each generated value is therefore forced strictly
     * above the previous one, and carries a random suffix so that two processes
     * landing on the same nanosecond produce two items rather than one.
     */
    private static final AtomicLong LAST_EVENT_NANOS = new AtomicLong(Long.MIN_VALUE);

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

    /**
     * {@inheritDoc}
     *
     * <p>Insert-if-absent, and the one write that is not a state change: a
     * {@code PutItem} at the {@link #CREATE_EVENT_SEQ} sentinel guarded by
     * {@code attribute_not_exists(run_id)}, so a second create for the same
     * {@code runId} is rejected atomically rather than starting a second
     * history for it.
     *
     * @throws software.amazon.awssdk.services.dynamodb.model.ConditionalCheckFailedException
     *         if a job with this {@code runId} already exists.
     */
    @Override
    public void createJob(PipelineJob job) {
        Objects.requireNonNull(job, "job must not be null");

        Map<String, AttributeValue> item = ledgerItem(job, CREATE_EVENT_SEQ,
                job.createdAt(), job.updatedAt(),
                job.startedAt().orElse(null), job.completedAt().orElse(null));

        client.putItem(PutItemRequest.builder()
                .tableName(tableName)
                .item(item)
                // INSERT semantics: never silently start a second history.
                .conditionExpression("attribute_not_exists(" + ATTR_RUN_ID + ")")
                .build());
    }

    /**
     * {@inheritDoc}
     *
     * <p>The projected current state of the run: one item out of however many
     * the run has appended, chosen by {@link #project}. A run whose first
     * terminal item is {@code succeeded} reads {@code SUCCEEDED} however many
     * later items say otherwise.
     */
    @Override
    public Optional<PipelineJob> getJob(String runId) {
        Objects.requireNonNull(runId, "runId must not be null");
        return project(queryRun(runId));
    }

    /**
     * {@inheritDoc}
     *
     * <p>Appends the run's next state. The projected current state is read
     * first and a prior state this transition may not leave is rejected before
     * anything is written, so a transition that would change nothing still does
     * not report success.
     *
     * <p>{@code RUNNING} stamps {@code started_at} and {@code SUCCEEDED} stamps
     * {@code completed_at} + {@code record_count} on the appended item; every
     * other attribute is carried forward from the projected state.
     *
     * @throws IllegalArgumentException if {@code status} is
     *                                  {@link JobStatus#CREATED} — a job enters
     *                                  that state only via {@link #createJob}.
     * @throws IllegalStateException    if the run has no item at all, or its
     *                                  projected status is not one of the
     *                                  allowed prior states for {@code status}.
     */
    @Override
    public void updateStatus(String runId, JobStatus status, Optional<Long> totalRecords) {
        Objects.requireNonNull(runId, "runId must not be null");
        Objects.requireNonNull(status, "status must not be null");
        Objects.requireNonNull(totalRecords, "totalRecords must not be null");

        // Ahead of the read: CREATED is not a transition target whatever the
        // ledger says, and the caller should not pay for a query to hear it.
        Set<JobStatus> allowed = allowedPriorStates(status);
        PipelineJob current = requireTransitionFrom("updateStatus", runId, allowed);

        PipelineJob.Builder next = carryForward(current, status);
        if (status == JobStatus.SUCCEEDED) {
            next.recordCount(totalRecords.orElse(0L));
        }
        append(next.build(), status == JobStatus.RUNNING, status == JobStatus.SUCCEEDED);
    }

    /**
     * {@inheritDoc}
     *
     * <p>Appends a {@code failed} item. The projected prior state must be one of
     * {@code CREATED}, {@code RUNNING}, {@code RETRYING} or {@code FAILED} — a
     * run that already {@code SUCCEEDED} cannot be re-marked failed, and under
     * AD-3 could not read as failed even if an item were appended behind this
     * method's back.
     *
     * @throws IllegalStateException if the run has no item at all, or its
     *                               projected status is not an allowed prior
     *                               state.
     */
    @Override
    public void markFailed(String runId, String errorCode, String errorMessage,
                           FailureStage failureStage, Optional<String> errorFilePath) {
        Objects.requireNonNull(runId, "runId must not be null");
        Objects.requireNonNull(errorCode, "errorCode must not be null");
        Objects.requireNonNull(errorMessage, "errorMessage must not be null");
        Objects.requireNonNull(failureStage, "failureStage must not be null");
        Objects.requireNonNull(errorFilePath, "errorFilePath must not be null");

        Set<JobStatus> allowed = allowedPriorStates(JobStatus.FAILED);
        PipelineJob current = requireTransitionFrom("markFailed", runId, allowed);

        PipelineJob next = carryForward(current, JobStatus.FAILED)
                .errorCode(errorCode)
                .errorMessage(errorMessage)
                .failureStage(failureStage)
                .errorFilePath(errorFilePath.orElse(null))
                .build();
        append(next, false, true);
    }

    /**
     * {@inheritDoc}
     *
     * <p>Appends a {@code retrying} item. The projected prior state must be one
     * of {@code CREATED}, {@code RUNNING} or {@code FAILED}. Retrying a run that
     * already {@code SUCCEEDED} is exactly how a re-run duplicates data, so it
     * is rejected.
     *
     * <p><strong>Recorded, not resurrecting.</strong> Appending this against a
     * {@code failed} run writes the item but does not change what the run reads
     * as: {@code failed} is terminal, and the contract's retry takes a new
     * {@code run_id} rather than reviving the old one. See "The retry model" in
     * the class javadoc.
     *
     * @throws IllegalStateException if the run has no item at all, or its
     *                               projected status is not an allowed prior
     *                               state.
     */
    @Override
    public void markRetrying(String runId, int retryCount) {
        Objects.requireNonNull(runId, "runId must not be null");
        if (retryCount < 0) {
            throw new IllegalArgumentException("retryCount must be >= 0, got " + retryCount);
        }

        Set<JobStatus> allowed = allowedPriorStates(JobStatus.RETRYING);
        PipelineJob current = requireTransitionFrom("markRetrying", runId, allowed);

        PipelineJob next = carryForward(current, JobStatus.RETRYING)
                .retryCount(retryCount)
                .build();
        append(next, false, false);
    }

    /**
     * {@inheritDoc}
     *
     * <p>The status filter sits on the projection, never inside the scan: a run
     * that has since succeeded still has its old {@code running} item in the
     * ledger, and filtering the scan on status would hand that item back as
     * pending.
     */
    @Override
    public List<PipelineJob> getPendingJobs(Optional<String> systemId) {
        Objects.requireNonNull(systemId, "systemId must not be null");

        List<Map<String, AttributeValue>> items;
        if (systemId.isPresent()) {
            items = scanAll("#system_id = :system_id",
                    Map.of("#system_id", ATTR_SYSTEM_ID),
                    Map.of(":system_id", AttributeValue.fromS(systemId.get())));
        } else {
            items = scanAll(null, Map.of(), Map.of());
        }

        List<PipelineJob> jobs = new ArrayList<>();
        for (PipelineJob job : projectEach(items)) {
            if (job.status() == JobStatus.CREATED || job.status() == JobStatus.RUNNING) {
                jobs.add(job);
            }
        }
        jobs.sort(Comparator.comparing(PipelineJob::createdAt));
        return jobs;
    }

    @Override
    public List<EntityStatus> getEntityStatus(String systemId, LocalDate extractDate) {
        Objects.requireNonNull(systemId, "systemId must not be null");
        Objects.requireNonNull(extractDate, "extractDate must not be null");

        List<EntityStatus> out = new ArrayList<>();
        for (PipelineJob job : projectEach(scanBySystemAndDate(systemId, extractDate))) {
            out.add(new EntityStatus(job.entityType().orElse(""), job.status().getValue(),
                    job.runId(), job.recordCount(), job.errorCount(),
                    job.startedAt(), job.completedAt()));
        }
        return out;
    }

    @Override
    public List<FailedJob> getFailedJobs(String systemId, LocalDate extractDate) {
        Objects.requireNonNull(systemId, "systemId must not be null");
        Objects.requireNonNull(extractDate, "extractDate must not be null");

        // The status test is applied to the PROJECTED job, never in the scan
        // filter. Inside the filter it would fold a partition stripped of its
        // winning item, so a run whose first terminal state was `succeeded`
        // would come back failed — and a failed job is a retryable job
        // (RetryOrchestrator), which deletes data.
        List<FailedJob> out = new ArrayList<>();
        for (PipelineJob job : projectEach(scanBySystemAndDate(systemId, extractDate))) {
            if (job.status() != JobStatus.FAILED) {
                continue;
            }
            out.add(new FailedJob(job.runId(), job.entityType().orElse(""),
                    job.failureStage().map(FailureStage::getValue).orElse(""),
                    job.errorCode().orElse(""), job.errorMessage().orElse(""),
                    job.errorFilePath(), job.completedAt().orElse(Instant.EPOCH),
                    job.retryCount()));
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
        // is used as the model identifier. Every attribute filtered on here is
        // one an append carries forward unchanged.
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

        List<Map<String, AttributeValue>> items = scanAll(
                "#system_id = :system_id AND #extract_date = :extract_date "
                        + "AND #job_type = :job_type AND #pipeline_name = :model_name",
                names, values);

        // Most recent run wins, as BigQuery's ORDER BY created_at DESC LIMIT 1
        // does — over the projected jobs, not over the raw items.
        PipelineJob latest = null;
        for (PipelineJob job : projectEach(items)) {
            if (latest == null || job.createdAt().isAfter(latest.createdAt())) {
                latest = job;
            }
        }
        if (latest == null) {
            return Optional.empty();
        }
        return Optional.of(new FdpJobStatus(latest.runId(), latest.pipelineName(),
                latest.status().getValue(), latest.recordCount(),
                latest.startedAt(), latest.completedAt()));
    }

    /**
     * {@inheritDoc}
     *
     * <h2>Exactly what this deletes</h2>
     *
     * <p>DynamoDB has no DELETE-WHERE statement (unlike BigQuery's
     * {@code DELETE FROM <fqtn> WHERE _run_id = ...}), so this is a
     * Scan-then-{@code BatchWriteItem}-delete against {@code tableId} — an
     * arbitrary, caller-supplied table, <strong>never the job-control
     * table</strong>. The convention, mirroring BigQuery's {@code _run_id}
     * column, is that {@code tableId} carries a {@code _run_id} (S) attribute
     * on every item tagging which run wrote it.
     *
     * <p>What it does <strong>not</strong> do:
     * <ul>
     *   <li>It does not touch the job-control ledger, which AD-2 makes
     *       append-only; clearing a run's state is {@link #markRetrying}'s job.
     *   <li>It is not atomic. Scan-then-delete does not fence concurrent
     *       writers; call it only once the run has reached a terminal state.
     * </ul>
     *
     * @return the number of items deleted.
     */
    @Override
    public int cleanupPartialLoad(String runId, String tableId) {
        Objects.requireNonNull(runId, "runId must not be null");
        Objects.requireNonNull(tableId, "tableId must not be null");

        String runIdAttr = "_run_id";

        List<Map<String, AttributeValue>> matches = new ArrayList<>();
        Map<String, AttributeValue> startKey = null;
        do {
            ScanRequest.Builder builder = ScanRequest.builder()
                    .tableName(tableId)
                    .filterExpression("#run_id = :run_id")
                    .expressionAttributeNames(Map.of("#run_id", runIdAttr))
                    .expressionAttributeValues(Map.of(":run_id", AttributeValue.fromS(runId)));
            if (startKey != null) {
                builder.exclusiveStartKey(startKey);
            }
            ScanResponse response = client.scan(builder.build());
            matches.addAll(response.items());
            startKey = nextPage(response.hasLastEvaluatedKey() ? response.lastEvaluatedKey() : null);
        } while (startKey != null);

        if (matches.isEmpty()) {
            return 0;
        }

        List<WriteRequest> deletes = new ArrayList<>();
        for (Map<String, AttributeValue> item : matches) {
            // BatchWriteItem delete requests take only the key attributes; the
            // key schema of tableId is not known to this repository, so this
            // adapter assumes it is keyed by the same run_id-tag attribute the
            // filter above uses.
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
            client.batchWriteItem(BatchWriteItemRequest.builder()
                    .requestItems(Map.of(tableId, chunk))
                    .build());
            deleted += chunk.size();
        }
        return deleted;
    }

    /**
     * {@inheritDoc}
     *
     * <p>Not a status transition — cost metrics are attached to a job in any
     * state — so the only condition is that the run exists. The appended item
     * carries the projected status forward unchanged.
     *
     * <p><strong>Write-only on a finished run.</strong> If the run has already
     * reached a terminal state, the projection is frozen on the earlier item
     * and these figures never read back through this class. See the class
     * javadoc.
     *
     * @throws IllegalStateException if the run has no item at all.
     */
    @Override
    public void updateCostMetrics(String runId, double estimatedCostUsd,
                                  long billedBytesScanned, long billedBytesWritten) {
        Objects.requireNonNull(runId, "runId must not be null");

        PipelineJob current = getJob(runId).orElseThrow(() -> new IllegalStateException(
                "updateCostMetrics rejected: no job with runId=" + runId));

        PipelineJob next = carryForward(current, current.status())
                .estimatedCostUsd(estimatedCostUsd)
                .billedBytesScanned(billedBytesScanned)
                .billedBytesWritten(billedBytesWritten)
                .build();
        append(next, false, false);
    }

    // --- the projection ----------------------------------------------------

    /**
     * Folds one run's items — in {@code event_seq} order — into the run's
     * current state (AD-3).
     *
     * <p>Every read in this class is built on this and none may re-implement
     * it: recency logic of its own is exactly what AD-3 forbids.
     *
     * <p>The fold: the latest item wins until a terminal one arrives, after
     * which the projection is frozen and stays frozen. There is no exit — not
     * even {@code retrying}, because the contract's retry is a new run rather
     * than a revival of this one. That is what stops a late failure making a
     * successful run retryable and its loaded rows deletable.
     */
    private static Optional<PipelineJob> project(List<Map<String, AttributeValue>> runItems) {
        PipelineJob winner = null;
        for (Map<String, AttributeValue> item : runItems) {
            PipelineJob candidate = itemToPipelineJob(item);
            if (winner == null) {
                winner = candidate;
                continue;
            }
            if (TERMINAL_STATES.contains(winner.status())) {
                // Recorded, never projected: the first terminal state is final.
                continue;
            }
            winner = candidate;
        }
        return Optional.ofNullable(winner);
    }

    /**
     * Groups scanned items by {@code run_id}, orders each run's items by
     * {@code event_seq} (a {@code Scan} makes no ordering promise, unlike the
     * single-partition {@code Query} {@link #queryRun} issues) and projects
     * each run. Callers filter on status afterwards, never before.
     */
    private static List<PipelineJob> projectEach(List<Map<String, AttributeValue>> items) {
        Map<String, List<Map<String, AttributeValue>>> byRun = new LinkedHashMap<>();
        for (Map<String, AttributeValue> item : items) {
            byRun.computeIfAbsent(stringOrEmpty(item, ATTR_RUN_ID), k -> new ArrayList<>())
                    .add(item);
        }
        List<PipelineJob> out = new ArrayList<>();
        for (List<Map<String, AttributeValue>> runItems : byRun.values()) {
            runItems.sort(Comparator.comparing(i -> stringOrEmpty(i, ATTR_EVENT_SEQ)));
            project(runItems).ifPresent(out::add);
        }
        return out;
    }

    // --- reads -------------------------------------------------------------

    /**
     * Every item of one run, oldest first: a single-partition {@code Query},
     * paginated. DynamoDB returns a {@code Query} page in sort-key order, so
     * the concatenated pages are already in append order.
     */
    private List<Map<String, AttributeValue>> queryRun(String runId) {
        List<Map<String, AttributeValue>> items = new ArrayList<>();
        Map<String, AttributeValue> startKey = null;
        do {
            QueryRequest.Builder builder = QueryRequest.builder()
                    .tableName(tableName)
                    .keyConditionExpression("#run_id = :run_id")
                    .expressionAttributeNames(Map.of("#run_id", ATTR_RUN_ID))
                    .expressionAttributeValues(Map.of(":run_id", AttributeValue.fromS(runId)))
                    .scanIndexForward(true);
            if (startKey != null) {
                builder.exclusiveStartKey(startKey);
            }
            QueryResponse response = client.query(builder.build());
            items.addAll(response.items());
            startKey = nextPage(response.hasLastEvaluatedKey() ? response.lastEvaluatedKey() : null);
        } while (startKey != null);
        return items;
    }

    /**
     * A paginated {@code Scan} of the ledger.
     *
     * @param filterExpression a conjunction over <strong>immutable</strong>
     *                         attributes only ({@code run_id},
     *                         {@code system_id}, {@code extract_date},
     *                         {@code job_type}, {@code pipeline_name}), or
     *                         {@code null} for none. A {@code status} predicate
     *                         here would strip a run's winning item before the
     *                         fold ever sees it — see the class javadoc.
     */
    private List<Map<String, AttributeValue>> scanAll(String filterExpression,
                                                      Map<String, String> names,
                                                      Map<String, AttributeValue> values) {
        List<Map<String, AttributeValue>> items = new ArrayList<>();
        Map<String, AttributeValue> startKey = null;
        do {
            ScanRequest.Builder builder = ScanRequest.builder().tableName(tableName);
            if (filterExpression != null) {
                builder.filterExpression(filterExpression)
                        .expressionAttributeNames(names)
                        .expressionAttributeValues(values);
            }
            if (startKey != null) {
                builder.exclusiveStartKey(startKey);
            }
            ScanResponse response = client.scan(builder.build());
            items.addAll(response.items());
            startKey = nextPage(response.hasLastEvaluatedKey() ? response.lastEvaluatedKey() : null);
        } while (startKey != null);
        return items;
    }

    private List<Map<String, AttributeValue>> scanBySystemAndDate(String systemId,
                                                                  LocalDate extractDate) {
        return scanAll("#system_id = :system_id AND #extract_date = :extract_date",
                Map.of("#system_id", ATTR_SYSTEM_ID, "#extract_date", ATTR_EXTRACT_DATE),
                Map.of(":system_id", AttributeValue.fromS(systemId),
                        ":extract_date", AttributeValue.fromS(extractDate.toString())));
    }

    /**
     * The next page's start key, or {@code null} when the read is complete.
     *
     * <p>The AWS SDK v2 auto-constructs response collections, so a final page's
     * {@code lastEvaluatedKey()} is an <em>empty map</em>, not {@code null} —
     * testing it for {@code null} alone would loop forever.
     */
    private static Map<String, AttributeValue> nextPage(Map<String, AttributeValue> lastEvaluatedKey) {
        return (lastEvaluatedKey == null || lastEvaluatedKey.isEmpty()) ? null : lastEvaluatedKey;
    }

    // --- writes ------------------------------------------------------------

    /**
     * Appends one full-state item for a run. Never an {@code UpdateItem}: the
     * item carries every ledger attribute plus a fresh {@code event_seq} and
     * {@code updated_at}, and the run's earlier items are left exactly as they
     * are.
     *
     * @param stampStartedNow   stamp {@code started_at} with this append's
     *                          timestamp rather than carrying the projected
     *                          value forward — a {@code RUNNING} transition.
     * @param stampCompletedNow the same for {@code completed_at} — a
     *                          {@code SUCCEEDED} or {@code FAILED} transition.
     */
    private void append(PipelineJob job, boolean stampStartedNow, boolean stampCompletedNow) {
        long nanos = nextEventNanos();
        Instant eventAt = instantOf(nanos);
        Instant startedAt = stampStartedNow ? eventAt : job.startedAt().orElse(null);
        Instant completedAt = stampCompletedNow ? eventAt : job.completedAt().orElse(null);

        Map<String, AttributeValue> item = ledgerItem(job, eventSeq(nanos),
                job.createdAt(), eventAt, startedAt, completedAt);
        client.putItem(PutItemRequest.builder().tableName(tableName).item(item).build());
    }

    /**
     * One ledger item: every attribute of {@code job}, under an explicit
     * {@code event_seq} and explicit timestamps (the caller stamps or carries
     * each one).
     */
    private static Map<String, AttributeValue> ledgerItem(PipelineJob job, String eventSeq,
                                                          Instant createdAt, Instant updatedAt,
                                                          Instant startedAt, Instant completedAt) {
        Map<String, AttributeValue> item = new HashMap<>();
        item.put(ATTR_RUN_ID, AttributeValue.fromS(job.runId()));
        item.put(ATTR_EVENT_SEQ, AttributeValue.fromS(eventSeq));
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
        job.failureStage().ifPresent(
                fs -> item.put(ATTR_FAILURE_STAGE, AttributeValue.fromS(fs.getValue())));
        putIfPresent(item, ATTR_ERROR_CODE, job.errorCode());
        putIfPresent(item, ATTR_ERROR_MESSAGE, job.errorMessage());
        putIfPresent(item, ATTR_ERROR_FILE_PATH, job.errorFilePath());
        item.put(ATTR_ESTIMATED_COST_USD, AttributeValue.fromN(Double.toString(job.estimatedCostUsd())));
        item.put(ATTR_BILLED_BYTES_SCANNED, AttributeValue.fromN(Long.toString(job.billedBytesScanned())));
        item.put(ATTR_BILLED_BYTES_WRITTEN, AttributeValue.fromN(Long.toString(job.billedBytesWritten())));
        item.put(ATTR_CREATED_AT, AttributeValue.fromS(createdAt.toString()));
        item.put(ATTR_UPDATED_AT, AttributeValue.fromS(updatedAt.toString()));
        if (startedAt != null) {
            item.put(ATTR_STARTED_AT, AttributeValue.fromS(startedAt.toString()));
        }
        if (completedAt != null) {
            item.put(ATTR_COMPLETED_AT, AttributeValue.fromS(completedAt.toString()));
        }
        return item;
    }

    /**
     * A strictly increasing nanosecond stamp for this JVM. See
     * {@link #LAST_EVENT_NANOS} for why {@code Instant.now()} alone is not
     * enough.
     */
    private static long nextEventNanos() {
        Instant now = Instant.now();
        long nanos = now.getEpochSecond() * 1_000_000_000L + now.getNano();
        return LAST_EVENT_NANOS.updateAndGet(previous -> Math.max(nanos, previous + 1));
    }

    private static Instant instantOf(long epochNanos) {
        return Instant.ofEpochSecond(Math.floorDiv(epochNanos, 1_000_000_000L),
                Math.floorMod(epochNanos, 1_000_000_000L));
    }

    /**
     * The sort key for an append: a zero-padded, fixed-width epoch-nanosecond
     * stamp, so lexicographic order is chronological order, plus a random
     * suffix so two processes stamping the same nanosecond append two items
     * instead of overwriting one.
     */
    private static String eventSeq(long epochNanos) {
        return String.format("%020d-%08x", epochNanos, ThreadLocalRandom.current().nextInt());
    }

    // --- transition guard --------------------------------------------------

    /**
     * The states a job may legally be in immediately before a transition to
     * {@code target}.
     *
     * <p>Deliberately identical to
     * {@code BigQueryJobControlRepository.allowedPriorStates}
     * (BigQueryJobControlRepository.java:648-671), including
     * {@code FAILED -> FAILED} — a live path, not an oversight: a quarantine
     * handler marks a run FAILED, and a reconciliation check can then mark the
     * same run FAILED again with a more specific error code. Both appends are
     * accepted and both items survive, but under AD-3 the <strong>first</strong>
     * failure is the one that reads back. The table is duplicated across the two
     * adapters rather than shared; hoisting it into the core contracts module is
     * follow-up work, not this change's.
     *
     * @throws IllegalArgumentException if {@code target} is
     *                                  {@link JobStatus#CREATED}, which no
     *                                  transition may produce.
     */
    static Set<JobStatus> allowedPriorStates(JobStatus target) {
        switch (target) {
            case RUNNING:
                return EnumSet.of(JobStatus.CREATED, JobStatus.RETRYING);
            case SUCCEEDED:
                // Only a run that is actually running can succeed. This is the
                // guard that stops a re-run marking an already-finished job
                // succeeded a second time.
                return EnumSet.of(JobStatus.RUNNING);
            case FAILED:
                return EnumSet.of(JobStatus.CREATED, JobStatus.RUNNING,
                        JobStatus.RETRYING, JobStatus.FAILED);
            case RETRYING:
                return EnumSet.of(JobStatus.CREATED, JobStatus.RUNNING, JobStatus.FAILED);
            case CANCELLED:
                return EnumSet.of(JobStatus.CREATED, JobStatus.RUNNING, JobStatus.RETRYING);
            case CREATED:
            default:
                throw new IllegalArgumentException(
                        "CREATED is not a transition target — a job enters it via createJob; got "
                                + target);
        }
    }

    /**
     * Reads the run's projected state and rejects a transition it may not make.
     *
     * <p>This is where the conditional {@code UpdateItem}'s guarantee lives now
     * that the conditional write is gone: a transition out of a state
     * {@code allowed} does not name changes nothing, so it must not report
     * success. Note that the check is not atomic with the append that follows
     * it — the projection, not this guard, is what makes a terminal state
     * immutable.
     */
    private PipelineJob requireTransitionFrom(String op, String runId, Set<JobStatus> allowed) {
        PipelineJob current = getJob(runId).orElseThrow(() -> new IllegalStateException(
                op + " rejected: no job with runId=" + runId));
        if (!allowed.contains(current.status())) {
            throw new IllegalStateException(op + " rejected: job runId=" + runId + " is "
                    + current.status() + ", expected one of " + allowed);
        }
        return current;
    }

    /**
     * Copies every field of the projected state onto a builder, under a new
     * status. {@code updated_at} is deliberately not carried — the appended
     * item gets a fresh one alongside its fresh {@code event_seq}.
     */
    private static PipelineJob.Builder carryForward(PipelineJob current, JobStatus status) {
        return PipelineJob.builder(current.runId(), current.systemId(),
                        current.pipelineName(), current.extractDate(), status)
                .jobType(current.jobType())
                .entityType(current.entityType().orElse(null))
                .sourceFile(current.sourceFile().orElse(null))
                .targetTable(current.targetTable().orElse(null))
                .recordCount(current.recordCount())
                .errorCount(current.errorCount())
                .retryCount(current.retryCount())
                .failureStage(current.failureStage().orElse(null))
                .errorCode(current.errorCode().orElse(null))
                .errorMessage(current.errorMessage().orElse(null))
                .errorFilePath(current.errorFilePath().orElse(null))
                .estimatedCostUsd(current.estimatedCostUsd())
                .billedBytesScanned(current.billedBytesScanned())
                .billedBytesWritten(current.billedBytesWritten())
                .createdAt(current.createdAt())
                .startedAt(current.startedAt().orElse(null))
                .completedAt(current.completedAt().orElse(null));
    }

    // --- item marshalling --------------------------------------------------

    private static void putIfPresent(Map<String, AttributeValue> item, String attr,
                                     Optional<String> value) {
        value.ifPresent(v -> item.put(attr, AttributeValue.fromS(v)));
    }

    private static PipelineJob itemToPipelineJob(Map<String, AttributeValue> item) {
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
