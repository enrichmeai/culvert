package com.enrichmeai.culvert.aws.dynamodb;

import com.enrichmeai.culvert.jobcontrol.FailureStage;
import com.enrichmeai.culvert.jobcontrol.JobStatus;
import com.enrichmeai.culvert.jobcontrol.PipelineJob;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import software.amazon.awssdk.services.dynamodb.DynamoDbClient;
import software.amazon.awssdk.services.dynamodb.model.AttributeValue;
import software.amazon.awssdk.services.dynamodb.model.BatchWriteItemRequest;
import software.amazon.awssdk.services.dynamodb.model.BatchWriteItemResponse;
import software.amazon.awssdk.services.dynamodb.model.ConditionalCheckFailedException;
import software.amazon.awssdk.services.dynamodb.model.PutItemRequest;
import software.amazon.awssdk.services.dynamodb.model.PutItemResponse;
import software.amazon.awssdk.services.dynamodb.model.QueryRequest;
import software.amazon.awssdk.services.dynamodb.model.QueryResponse;
import software.amazon.awssdk.services.dynamodb.model.ScanRequest;
import software.amazon.awssdk.services.dynamodb.model.ScanResponse;
import software.amazon.awssdk.services.dynamodb.model.UpdateItemRequest;

import java.time.LocalDate;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatNullPointerException;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Mocked-client unit tests for {@link DynamoDbJobControlRepository}: the
 * <em>shape</em> of the requests it sends.
 *
 * <p>What a mock can prove, it proves here — that every write is a
 * {@code PutItem} and never an {@code UpdateItem} (AD-2), that
 * {@code createJob} carries the {@code attribute_not_exists} condition at the
 * sentinel sort key, that reads paginate, and that no scan filters on
 * {@code status} (AD-3: the status test belongs after the fold, never inside
 * the scan). What a mock cannot prove — that the projection resolves a run's
 * items correctly — belongs to {@link DynamoDbJobControlProjectionTest} and
 * {@link DynamoDbJobControlContractTest}, which run against a real ledger in
 * {@link InMemoryDynamoDb}. Round-trips against DynamoDB itself run in
 * {@code DynamoDbJobControlLocalStackIT} under {@code mvn -P it verify}.
 */
@ExtendWith(MockitoExtension.class)
@org.mockito.junit.jupiter.MockitoSettings(strictness = org.mockito.quality.Strictness.LENIENT)
class DynamoDbJobControlRepositoryTest {

    private static final String TABLE = "job_control";

    @Mock
    private DynamoDbClient client;

    private DynamoDbJobControlRepository repo;

    @BeforeEach
    void setUp() {
        repo = new DynamoDbJobControlRepository(client, TABLE);
    }

    private static PipelineJob job(String runId) {
        return PipelineJob.builder(
                runId, "GENERIC", "ingest_customers",
                LocalDate.of(2026, 1, 15), JobStatus.CREATED).build();
    }

    /** One ledger item, as the repository would have written it. */
    private static Map<String, AttributeValue> item(String runId, String eventSeq, String status) {
        Map<String, AttributeValue> item = new HashMap<>();
        item.put(DynamoDbJobControlRepository.ATTR_RUN_ID, AttributeValue.fromS(runId));
        item.put(DynamoDbJobControlRepository.ATTR_EVENT_SEQ, AttributeValue.fromS(eventSeq));
        item.put(DynamoDbJobControlRepository.ATTR_SYSTEM_ID, AttributeValue.fromS("GENERIC"));
        item.put(DynamoDbJobControlRepository.ATTR_PIPELINE_NAME,
                AttributeValue.fromS("ingest_customers"));
        item.put(DynamoDbJobControlRepository.ATTR_EXTRACT_DATE, AttributeValue.fromS("2026-01-15"));
        item.put(DynamoDbJobControlRepository.ATTR_STATUS, AttributeValue.fromS(status));
        return item;
    }

    /** The repository's read of one run returns exactly this item. */
    private void ledgerHolds(Map<String, AttributeValue> item) {
        when(client.query(any(QueryRequest.class)))
                .thenReturn(QueryResponse.builder().items(List.of(item)).build());
    }

    private PutItemRequest capturePut() {
        ArgumentCaptor<PutItemRequest> captor = ArgumentCaptor.forClass(PutItemRequest.class);
        verify(client).putItem(captor.capture());
        return captor.getValue();
    }

    private static String valueOf(PutItemRequest request, String attribute) {
        AttributeValue value = request.item().get(attribute);
        return value == null ? null : (value.s() != null ? value.s() : value.n());
    }

    // ------------------------------------------------------------------ //
    // createJob — attribute_not_exists at the sentinel sort key
    // ------------------------------------------------------------------ //

    @Test
    void createJobPutsTheCreatedItemAtTheSentinelSortKeyWithTheNotExistsGuard() {
        when(client.putItem(any(PutItemRequest.class))).thenReturn(PutItemResponse.builder().build());

        repo.createJob(job("run-1"));

        PutItemRequest req = capturePut();
        assertThat(req.tableName()).isEqualTo(TABLE);
        assertThat(req.conditionExpression()).isEqualTo("attribute_not_exists(run_id)");
        assertThat(valueOf(req, DynamoDbJobControlRepository.ATTR_RUN_ID)).isEqualTo("run-1");
        assertThat(valueOf(req, DynamoDbJobControlRepository.ATTR_STATUS)).isEqualTo("created");
        assertThat(valueOf(req, DynamoDbJobControlRepository.ATTR_EVENT_SEQ))
                .as("the fixed sentinel is what keeps createJob an atomic INSERT")
                .isEqualTo(DynamoDbJobControlRepository.CREATE_EVENT_SEQ);
    }

    @Test
    void createJobRejectsNull() {
        assertThatNullPointerException().isThrownBy(() -> repo.createJob(null));
    }

    @Test
    void createJobDuplicatePropagatesConditionalCheckFailure() {
        when(client.putItem(any(PutItemRequest.class)))
                .thenThrow(ConditionalCheckFailedException.builder().message("exists").build());

        assertThatThrownBy(() -> repo.createJob(job("run-1")))
                .isInstanceOf(ConditionalCheckFailedException.class);
    }

    // ------------------------------------------------------------------ //
    // getJob — a single-partition, ascending, paginated Query
    // ------------------------------------------------------------------ //

    @Test
    void getJobQueriesOnePartitionAscendingAndParsesTheItem() {
        ledgerHolds(item("run-1", "00000000000000000001-aaaaaaaa", "running"));

        Optional<PipelineJob> found = repo.getJob("run-1");

        ArgumentCaptor<QueryRequest> captor = ArgumentCaptor.forClass(QueryRequest.class);
        verify(client).query(captor.capture());
        QueryRequest req = captor.getValue();
        assertThat(req.tableName()).isEqualTo(TABLE);
        assertThat(req.keyConditionExpression()).isEqualTo("#run_id = :run_id");
        assertThat(req.scanIndexForward()).isTrue();
        assertThat(req.expressionAttributeValues().get(":run_id").s()).isEqualTo("run-1");

        assertThat(found).isPresent();
        assertThat(found.get().runId()).isEqualTo("run-1");
        assertThat(found.get().status()).isEqualTo(JobStatus.RUNNING);
        assertThat(found.get().extractDate()).isEqualTo(LocalDate.of(2026, 1, 15));
    }

    @Test
    void getJobFollowsTheLastEvaluatedKeyUntilItIsEmpty() {
        // The AWS SDK auto-constructs response maps, so the final page's
        // lastEvaluatedKey is an EMPTY MAP, not null. A null check alone would
        // spin forever; this pins the terminating condition.
        Map<String, AttributeValue> page1Key = Map.of(
                DynamoDbJobControlRepository.ATTR_RUN_ID, AttributeValue.fromS("run-1"),
                DynamoDbJobControlRepository.ATTR_EVENT_SEQ,
                AttributeValue.fromS("00000000000000000001-aaaaaaaa"));
        when(client.query(any(QueryRequest.class)))
                .thenReturn(QueryResponse.builder()
                        .items(List.of(item("run-1", "00000000000000000001-aaaaaaaa", "created")))
                        .lastEvaluatedKey(page1Key)
                        .build())
                .thenReturn(QueryResponse.builder()
                        .items(List.of(item("run-1", "00000000000000000002-bbbbbbbb", "running")))
                        .build());

        assertThat(repo.getJob("run-1")).get()
                .extracting(PipelineJob::status)
                .as("both pages are folded, so the second page's item wins")
                .isEqualTo(JobStatus.RUNNING);
        verify(client, org.mockito.Mockito.times(2)).query(any(QueryRequest.class));
    }

    @Test
    void getJobMissingReturnsEmpty() {
        when(client.query(any(QueryRequest.class)))
                .thenReturn(QueryResponse.builder().items(List.of()).build());

        assertThat(repo.getJob("nope")).isEmpty();
    }

    @Test
    void getJobRejectsNull() {
        assertThatNullPointerException().isThrownBy(() -> repo.getJob(null));
    }

    // ------------------------------------------------------------------ //
    // State changes — appends, never UpdateItem (AD-2)
    // ------------------------------------------------------------------ //

    @Test
    void updateStatusAppendsANewItemAndNeverUpdatesInPlace() {
        ledgerHolds(item("run-1", "00000000000000000001-aaaaaaaa", "running"));
        when(client.putItem(any(PutItemRequest.class))).thenReturn(PutItemResponse.builder().build());

        repo.updateStatus("run-1", JobStatus.SUCCEEDED, Optional.of(5_000L));

        PutItemRequest req = capturePut();
        assertThat(req.conditionExpression())
                .as("an append needs no condition: it collides with nothing")
                .isNull();
        assertThat(valueOf(req, DynamoDbJobControlRepository.ATTR_STATUS)).isEqualTo("succeeded");
        assertThat(valueOf(req, DynamoDbJobControlRepository.ATTR_RECORD_COUNT)).isEqualTo("5000");
        assertThat(valueOf(req, DynamoDbJobControlRepository.ATTR_EVENT_SEQ))
                .as("a fresh sort key — overwriting the previous item is the one thing AD-2 forbids")
                .isNotEqualTo(DynamoDbJobControlRepository.CREATE_EVENT_SEQ);
        assertThat(valueOf(req, DynamoDbJobControlRepository.ATTR_COMPLETED_AT)).isNotNull();
        verify(client, never()).updateItem(any(UpdateItemRequest.class));
    }

    @Test
    void updateStatusOnAMissingRunIsRejectedBeforeAnythingIsWritten() {
        when(client.query(any(QueryRequest.class)))
                .thenReturn(QueryResponse.builder().items(List.of()).build());

        assertThatThrownBy(() -> repo.updateStatus("nope", JobStatus.RUNNING, Optional.empty()))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("no job with runId=nope");
        verify(client, never()).putItem(any(PutItemRequest.class));
    }

    @Test
    void updateStatusOutOfAnIllegalPriorStateIsRejectedBeforeAnythingIsWritten() {
        ledgerHolds(item("run-1", "00000000000000000001-aaaaaaaa", "succeeded"));

        assertThatThrownBy(() -> repo.updateStatus("run-1", JobStatus.RUNNING, Optional.empty()))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("expected one of");
        verify(client, never()).putItem(any(PutItemRequest.class));
    }

    @Test
    void updateStatusRejectsCreatedAsATransitionTarget() {
        assertThatThrownBy(() -> repo.updateStatus("run-1", JobStatus.CREATED, Optional.empty()))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("CREATED is not a transition target");
    }

    @Test
    void markFailedAppendsTheErrorFields() {
        ledgerHolds(item("run-1", "00000000000000000001-aaaaaaaa", "running"));
        when(client.putItem(any(PutItemRequest.class))).thenReturn(PutItemResponse.builder().build());

        repo.markFailed("run-1", "E42", "boom", FailureStage.LOAD,
                Optional.of("s3://errors/run-1.json"));

        PutItemRequest req = capturePut();
        assertThat(valueOf(req, DynamoDbJobControlRepository.ATTR_STATUS)).isEqualTo("failed");
        assertThat(valueOf(req, DynamoDbJobControlRepository.ATTR_ERROR_CODE)).isEqualTo("E42");
        assertThat(valueOf(req, DynamoDbJobControlRepository.ATTR_ERROR_MESSAGE)).isEqualTo("boom");
        assertThat(valueOf(req, DynamoDbJobControlRepository.ATTR_ERROR_FILE_PATH))
                .isEqualTo("s3://errors/run-1.json");
        verify(client, never()).updateItem(any(UpdateItemRequest.class));
    }

    @Test
    void markRetryingAppendsTheRetryCount() {
        ledgerHolds(item("run-1", "00000000000000000001-aaaaaaaa", "failed"));
        when(client.putItem(any(PutItemRequest.class))).thenReturn(PutItemResponse.builder().build());

        repo.markRetrying("run-1", 2);

        PutItemRequest req = capturePut();
        assertThat(valueOf(req, DynamoDbJobControlRepository.ATTR_STATUS)).isEqualTo("retrying");
        assertThat(valueOf(req, DynamoDbJobControlRepository.ATTR_RETRY_COUNT)).isEqualTo("2");
        verify(client, never()).updateItem(any(UpdateItemRequest.class));
    }

    @Test
    void markRetryingRejectsANegativeCount() {
        assertThatThrownBy(() -> repo.markRetrying("run-1", -1))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void updateCostMetricsAppendsAllThreeFiguresAndCarriesTheStatusForward() {
        ledgerHolds(item("run-1", "00000000000000000001-aaaaaaaa", "running"));
        when(client.putItem(any(PutItemRequest.class))).thenReturn(PutItemResponse.builder().build());

        repo.updateCostMetrics("run-1", 1.25, 10L, 20L);

        PutItemRequest req = capturePut();
        assertThat(valueOf(req, DynamoDbJobControlRepository.ATTR_ESTIMATED_COST_USD)).isEqualTo("1.25");
        assertThat(valueOf(req, DynamoDbJobControlRepository.ATTR_BILLED_BYTES_SCANNED)).isEqualTo("10");
        assertThat(valueOf(req, DynamoDbJobControlRepository.ATTR_BILLED_BYTES_WRITTEN)).isEqualTo("20");
        assertThat(valueOf(req, DynamoDbJobControlRepository.ATTR_STATUS))
                .as("not a transition: the projected status rides along unchanged")
                .isEqualTo("running");
        verify(client, never()).updateItem(any(UpdateItemRequest.class));
    }

    // ------------------------------------------------------------------ //
    // Queries (scan-backed) — no status predicate may reach the scan
    // ------------------------------------------------------------------ //

    @Test
    void getPendingJobsScansOnSystemIdOnlyAndFiltersStatusAfterTheFold() {
        when(client.scan(any(ScanRequest.class))).thenReturn(ScanResponse.builder()
                .items(List.of(item("run-9", "00000000000000000001-aaaaaaaa", "created")))
                .build());

        List<PipelineJob> pending = repo.getPendingJobs(Optional.of("GENERIC"));

        ArgumentCaptor<ScanRequest> captor = ArgumentCaptor.forClass(ScanRequest.class);
        verify(client).scan(captor.capture());
        assertThat(captor.getValue().filterExpression())
                .as("a status predicate here would rank a partition stripped of its winning item")
                .isEqualTo("#system_id = :system_id");
        assertThat(captor.getValue().expressionAttributeNames().values())
                .doesNotContain(DynamoDbJobControlRepository.ATTR_STATUS);

        assertThat(pending).hasSize(1);
        assertThat(pending.get(0).runId()).isEqualTo("run-9");
    }

    @Test
    void getPendingJobsWithNoSystemIdScansUnfiltered() {
        when(client.scan(any(ScanRequest.class)))
                .thenReturn(ScanResponse.builder().items(List.of()).build());

        assertThat(repo.getPendingJobs(Optional.empty())).isEmpty();

        ArgumentCaptor<ScanRequest> captor = ArgumentCaptor.forClass(ScanRequest.class);
        verify(client).scan(captor.capture());
        assertThat(captor.getValue().filterExpression()).isNull();
    }

    @Test
    void getFailedJobsScanCarriesNoStatusPredicate() {
        when(client.scan(any(ScanRequest.class)))
                .thenReturn(ScanResponse.builder().items(List.of()).build());

        assertThat(repo.getFailedJobs("GENERIC", LocalDate.of(2026, 1, 15))).isEmpty();

        ArgumentCaptor<ScanRequest> captor = ArgumentCaptor.forClass(ScanRequest.class);
        verify(client).scan(captor.capture());
        assertThat(captor.getValue().filterExpression())
                .isEqualTo("#system_id = :system_id AND #extract_date = :extract_date");
    }

    @Test
    void getEntityStatusEmptyScanYieldsEmptyList() {
        when(client.scan(any(ScanRequest.class)))
                .thenReturn(ScanResponse.builder().items(List.of()).build());

        assertThat(repo.getEntityStatus("GENERIC", LocalDate.of(2026, 1, 15))).isEmpty();
    }

    @Test
    void getFdpJobStatusEmptyScanYieldsEmpty() {
        when(client.scan(any(ScanRequest.class)))
                .thenReturn(ScanResponse.builder().items(List.of()).build());

        assertThat(repo.getFdpJobStatus("GENERIC", LocalDate.of(2026, 1, 15), "fdp_table"))
                .isEmpty();
    }

    // ------------------------------------------------------------------ //
    // cleanupPartialLoad — scan-then-batch-delete, against the caller's table
    // ------------------------------------------------------------------ //

    @Test
    void cleanupPartialLoadBatchDeletesEachMatchAndReturnsTheCount() {
        Map<String, AttributeValue> loaded = Map.of("_run_id", AttributeValue.fromS("run-1"));
        when(client.scan(any(ScanRequest.class)))
                .thenReturn(ScanResponse.builder().items(List.of(loaded, loaded)).build());
        when(client.batchWriteItem(any(BatchWriteItemRequest.class)))
                .thenReturn(BatchWriteItemResponse.builder().build());

        int deleted = repo.cleanupPartialLoad("run-1", "odp.customers");

        assertThat(deleted).isEqualTo(2);
        ArgumentCaptor<BatchWriteItemRequest> captor =
                ArgumentCaptor.forClass(BatchWriteItemRequest.class);
        verify(client).batchWriteItem(captor.capture());
        assertThat(captor.getValue().requestItems())
                .as("the deletes target the caller's warehouse table, never the ledger")
                .containsOnlyKeys("odp.customers");
    }

    @Test
    void cleanupPartialLoadDeletesNothingWhenTheRunLoadedNothing() {
        when(client.scan(any(ScanRequest.class)))
                .thenReturn(ScanResponse.builder().items(List.of()).build());

        assertThat(repo.cleanupPartialLoad("run-1", "odp.customers")).isZero();
        verify(client, never()).batchWriteItem(any(BatchWriteItemRequest.class));
    }

    // ------------------------------------------------------------------ //
    // Constructor guards
    // ------------------------------------------------------------------ //

    @Test
    void constructorRejectsNulls() {
        assertThatNullPointerException()
                .isThrownBy(() -> new DynamoDbJobControlRepository(null, TABLE));
        assertThatNullPointerException()
                .isThrownBy(() -> new DynamoDbJobControlRepository(client, null));
    }
}
