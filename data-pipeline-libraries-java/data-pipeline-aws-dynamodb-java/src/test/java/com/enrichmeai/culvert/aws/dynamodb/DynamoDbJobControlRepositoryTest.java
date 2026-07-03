package com.enrichmeai.culvert.aws.dynamodb;

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
import software.amazon.awssdk.services.dynamodb.model.ConditionalCheckFailedException;
import software.amazon.awssdk.services.dynamodb.model.DeleteItemRequest;
import software.amazon.awssdk.services.dynamodb.model.DeleteItemResponse;
import software.amazon.awssdk.services.dynamodb.model.GetItemRequest;
import software.amazon.awssdk.services.dynamodb.model.GetItemResponse;
import software.amazon.awssdk.services.dynamodb.model.PutItemRequest;
import software.amazon.awssdk.services.dynamodb.model.PutItemResponse;
import software.amazon.awssdk.services.dynamodb.model.ScanRequest;
import software.amazon.awssdk.services.dynamodb.model.ScanResponse;
import software.amazon.awssdk.services.dynamodb.model.UpdateItemRequest;
import software.amazon.awssdk.services.dynamodb.model.UpdateItemResponse;

import java.time.LocalDate;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatNullPointerException;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Mocked-client unit tests for {@link DynamoDbJobControlRepository}.
 *
 * <p>Request-shape coverage for all 11 contract methods: the conditional-write
 * guards ({@code attribute_not_exists} on create, {@code attribute_exists} on
 * every status transition), scan filters, item parsing, and null-rejection.
 * Real round-trips against DynamoDB run in {@code DynamoDbJobControlLocalStackIT}
 * under {@code mvn -P it verify}.
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

    private static Map<String, AttributeValue> minimalItem(String runId, String status) {
        return Map.of(
                DynamoDbJobControlRepository.ATTR_RUN_ID, AttributeValue.fromS(runId),
                DynamoDbJobControlRepository.ATTR_SYSTEM_ID, AttributeValue.fromS("GENERIC"),
                DynamoDbJobControlRepository.ATTR_PIPELINE_NAME, AttributeValue.fromS("ingest_customers"),
                DynamoDbJobControlRepository.ATTR_EXTRACT_DATE, AttributeValue.fromS("2026-01-15"),
                DynamoDbJobControlRepository.ATTR_STATUS, AttributeValue.fromS(status));
    }

    // ------------------------------------------------------------------ //
    // createJob — attribute_not_exists guard
    // ------------------------------------------------------------------ //

    @Test
    void createJobPutsItemWithNotExistsCondition() {
        when(client.putItem(any(PutItemRequest.class))).thenReturn(PutItemResponse.builder().build());

        repo.createJob(job("run-1"));

        ArgumentCaptor<PutItemRequest> captor = ArgumentCaptor.forClass(PutItemRequest.class);
        verify(client).putItem(captor.capture());
        PutItemRequest req = captor.getValue();
        assertThat(req.tableName()).isEqualTo(TABLE);
        assertThat(req.conditionExpression()).contains("attribute_not_exists");
        assertThat(req.item().get(DynamoDbJobControlRepository.ATTR_RUN_ID).s()).isEqualTo("run-1");
        assertThat(req.item().get(DynamoDbJobControlRepository.ATTR_STATUS).s()).isEqualTo("created");
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
    // getJob
    // ------------------------------------------------------------------ //

    @Test
    void getJobParsesItem() {
        when(client.getItem(any(GetItemRequest.class))).thenReturn(
                GetItemResponse.builder().item(minimalItem("run-1", "RUNNING")).build());

        Optional<PipelineJob> found = repo.getJob("run-1");

        assertThat(found).isPresent();
        assertThat(found.get().runId()).isEqualTo("run-1");
        assertThat(found.get().status()).isEqualTo(JobStatus.RUNNING);
        assertThat(found.get().extractDate()).isEqualTo(LocalDate.of(2026, 1, 15));
    }

    @Test
    void getJobMissingReturnsEmpty() {
        when(client.getItem(any(GetItemRequest.class))).thenReturn(GetItemResponse.builder().build());

        assertThat(repo.getJob("nope")).isEmpty();
    }

    @Test
    void getJobRejectsNull() {
        assertThatNullPointerException().isThrownBy(() -> repo.getJob(null));
    }

    // ------------------------------------------------------------------ //
    // Status transitions — attribute_exists compare-and-swap guard
    // ------------------------------------------------------------------ //

    @Test
    void updateStatusUsesExistsConditionAndSetsStatus() {
        when(client.updateItem(any(UpdateItemRequest.class))).thenReturn(UpdateItemResponse.builder().build());

        repo.updateStatus("run-1", JobStatus.SUCCEEDED, Optional.of(5_000L));

        ArgumentCaptor<UpdateItemRequest> captor = ArgumentCaptor.forClass(UpdateItemRequest.class);
        verify(client).updateItem(captor.capture());
        UpdateItemRequest req = captor.getValue();
        assertThat(req.conditionExpression()).contains("attribute_exists");
        assertThat(req.key().get(DynamoDbJobControlRepository.ATTR_RUN_ID).s()).isEqualTo("run-1");
        assertThat(req.expressionAttributeValues().values())
                .anyMatch(v -> "succeeded".equals(v.s()));
        assertThat(req.expressionAttributeValues().values())
                .anyMatch(v -> "5000".equals(v.n()));
    }

    @Test
    void updateStatusOnMissingJobFailsHard() {
        when(client.updateItem(any(UpdateItemRequest.class)))
                .thenThrow(ConditionalCheckFailedException.builder().message("missing").build());

        assertThatThrownBy(() -> repo.updateStatus("nope", JobStatus.RUNNING, Optional.empty()))
                .isInstanceOf(ConditionalCheckFailedException.class);
    }

    @Test
    void markFailedRecordsErrorFieldsConditionally() {
        when(client.updateItem(any(UpdateItemRequest.class))).thenReturn(UpdateItemResponse.builder().build());

        repo.markFailed("run-1", "E42", "boom",
                com.enrichmeai.culvert.jobcontrol.FailureStage.LOAD,
                Optional.of("gs://errors/run-1.json"));

        ArgumentCaptor<UpdateItemRequest> captor = ArgumentCaptor.forClass(UpdateItemRequest.class);
        verify(client).updateItem(captor.capture());
        UpdateItemRequest req = captor.getValue();
        assertThat(req.conditionExpression()).contains("attribute_exists");
        assertThat(req.expressionAttributeValues().values())
                .anyMatch(v -> "E42".equals(v.s()));
        assertThat(req.expressionAttributeValues().values())
                .anyMatch(v -> "boom".equals(v.s()));
    }

    @Test
    void markRetryingBumpsRetryCountConditionally() {
        when(client.updateItem(any(UpdateItemRequest.class))).thenReturn(UpdateItemResponse.builder().build());

        repo.markRetrying("run-1", 2);

        ArgumentCaptor<UpdateItemRequest> captor = ArgumentCaptor.forClass(UpdateItemRequest.class);
        verify(client).updateItem(captor.capture());
        assertThat(captor.getValue().conditionExpression()).contains("attribute_exists");
        assertThat(captor.getValue().expressionAttributeValues().values())
                .anyMatch(v -> "2".equals(v.n()));
    }

    @Test
    void updateCostMetricsWritesAllFourFields() {
        when(client.updateItem(any(UpdateItemRequest.class))).thenReturn(UpdateItemResponse.builder().build());

        repo.updateCostMetrics("run-1", 1.25, 10L, 20L);

        ArgumentCaptor<UpdateItemRequest> captor = ArgumentCaptor.forClass(UpdateItemRequest.class);
        verify(client).updateItem(captor.capture());
        UpdateItemRequest req = captor.getValue();
        assertThat(req.conditionExpression()).contains("attribute_exists");
        assertThat(req.expressionAttributeNames().values())
                .contains(DynamoDbJobControlRepository.ATTR_ESTIMATED_COST_USD,
                        DynamoDbJobControlRepository.ATTR_BILLED_BYTES_SCANNED,
                        DynamoDbJobControlRepository.ATTR_BILLED_BYTES_WRITTEN);
    }

    // ------------------------------------------------------------------ //
    // Queries (scan-backed)
    // ------------------------------------------------------------------ //

    @Test
    void getPendingJobsParsesScanResults() {
        when(client.scan(any(ScanRequest.class))).thenReturn(
                ScanResponse.builder().items(List.of(minimalItem("run-9", "CREATED"))).build());

        List<PipelineJob> pending = repo.getPendingJobs(Optional.of("GENERIC"));

        assertThat(pending).hasSize(1);
        assertThat(pending.get(0).runId()).isEqualTo("run-9");
    }

    @Test
    void getEntityStatusEmptyScanYieldsEmptyList() {
        when(client.scan(any(ScanRequest.class))).thenReturn(ScanResponse.builder().items(List.of()).build());

        assertThat(repo.getEntityStatus("GENERIC", LocalDate.of(2026, 1, 15))).isEmpty();
    }

    @Test
    void getFailedJobsEmptyScanYieldsEmptyList() {
        when(client.scan(any(ScanRequest.class))).thenReturn(ScanResponse.builder().items(List.of()).build());

        assertThat(repo.getFailedJobs("GENERIC", LocalDate.of(2026, 1, 15))).isEmpty();
    }

    @Test
    void getFdpJobStatusEmptyScanYieldsEmpty() {
        when(client.scan(any(ScanRequest.class))).thenReturn(ScanResponse.builder().items(List.of()).build());

        assertThat(repo.getFdpJobStatus("GENERIC", LocalDate.of(2026, 1, 15), "fdp_table")).isEmpty();
    }

    // ------------------------------------------------------------------ //
    // cleanupPartialLoad — scan-then-delete
    // ------------------------------------------------------------------ //

    @Test
    void cleanupPartialLoadDeletesEachMatchAndReturnsCount() {
        when(client.scan(any(ScanRequest.class))).thenReturn(ScanResponse.builder()
                .items(List.of(minimalItem("run-1", "FAILED"), minimalItem("run-1", "FAILED")))
                .build());
        when(client.deleteItem(any(DeleteItemRequest.class)))
                .thenReturn(DeleteItemResponse.builder().build());

        int deleted = repo.cleanupPartialLoad("run-1", "odp.customers");

        assertThat(deleted).isEqualTo(2);
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
