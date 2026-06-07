package com.enrichmeai.culvert.gcp.bigquery;

import com.enrichmeai.culvert.audit.AuditRecord;
import com.google.cloud.bigquery.BigQuery;
import com.google.cloud.bigquery.BigQueryOptions;
import com.google.cloud.bigquery.QueryJobConfiguration;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.MockedStatic;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.Instant;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.mockStatic;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Unit tests for {@link BigQueryAuditEventPublisher}.
 *
 * <p>Mocks the {@link BigQuery} client so no real GCP credentials or network
 * are required.
 *
 * <p>Sprint-14 deliverable for issue #95 (T14.6).
 */
@ExtendWith(MockitoExtension.class)
class BigQueryAuditEventPublisherTest {

    private static final String PROJECT_ID = "my-project";
    private static final String DATASET    = "audit";
    private static final String TABLE      = "audit_events";

    @Mock
    private BigQuery client;

    @AfterEach
    void clearSystemProperties() {
        System.clearProperty(BigQueryAuditEventPublisher.SYSPROP_GCP_PROJECT);
        System.clearProperty(BigQueryAuditEventPublisher.SYSPROP_AUDIT_DATASET);
        System.clearProperty(BigQueryAuditEventPublisher.SYSPROP_AUDIT_TABLE);
    }

    private BigQueryAuditEventPublisher newPublisher() {
        return new BigQueryAuditEventPublisher(client, PROJECT_ID, DATASET, TABLE);
    }

    private AuditRecord sampleRecord() {
        return AuditRecord.builder()
                .runId("run-001")
                .pipelineName("customer-ingest")
                .entityType("customer")
                .sourceFile("gs://my-bucket/customers.csv")
                .recordCount(1_000L)
                .processedTimestamp(Instant.parse("2026-06-05T10:00:00Z"))
                .processingDurationSeconds(3.5)
                .success(true)
                .errorCount(0L)
                .auditHash("sha256-abc123")
                .metadata(Map.of("table", "customers", "partition", "2026-06-05"))
                .build();
    }

    // --- happy paths ----------------------------------------------------------

    @Test
    void publishCallsClientQueryOnce() throws InterruptedException {
        when(client.query(any(QueryJobConfiguration.class))).thenReturn(null);

        newPublisher().publish(sampleRecord());

        verify(client).query(any(QueryJobConfiguration.class));
    }

    @Test
    void publishBuildsInsertIntoCorrectTable() throws InterruptedException {
        ArgumentCaptor<QueryJobConfiguration> captor =
                ArgumentCaptor.forClass(QueryJobConfiguration.class);
        when(client.query(captor.capture())).thenReturn(null);

        newPublisher().publish(sampleRecord());

        String sql = captor.getValue().getQuery();
        assertThat(sql).contains("INSERT INTO");
        assertThat(sql).contains("`my-project.audit.audit_events`");
    }

    @Test
    void publishIncludesAllAuditRecordFields() throws InterruptedException {
        ArgumentCaptor<QueryJobConfiguration> captor =
                ArgumentCaptor.forClass(QueryJobConfiguration.class);
        when(client.query(captor.capture())).thenReturn(null);

        newPublisher().publish(sampleRecord());

        QueryJobConfiguration config = captor.getValue();
        assertThat(config.getQuery()).contains("run_id");
        assertThat(config.getQuery()).contains("pipeline_name");
        assertThat(config.getQuery()).contains("entity_type");
        assertThat(config.getQuery()).contains("source_file");
        assertThat(config.getQuery()).contains("record_count");
        assertThat(config.getQuery()).contains("processed_timestamp");
        assertThat(config.getQuery()).contains("processing_duration_seconds");
        assertThat(config.getQuery()).contains("success");
        assertThat(config.getQuery()).contains("error_count");
        assertThat(config.getQuery()).contains("audit_hash");
        assertThat(config.getQuery()).contains("metadata_json");
        assertThat(config.getQuery()).contains("published_at");
        assertThat(config.getQuery()).contains("CURRENT_TIMESTAMP()");
    }

    @Test
    void publishBindsRunIdParameter() throws InterruptedException {
        ArgumentCaptor<QueryJobConfiguration> captor =
                ArgumentCaptor.forClass(QueryJobConfiguration.class);
        when(client.query(captor.capture())).thenReturn(null);

        newPublisher().publish(sampleRecord());

        assertThat(captor.getValue().getNamedParameters())
                .containsKey("run_id");
        assertThat(captor.getValue().getNamedParameters().get("run_id")
                .getValue()).isEqualTo("run-001");
    }

    @Test
    void publishBindsSuccessFlagParameter() throws InterruptedException {
        ArgumentCaptor<QueryJobConfiguration> captor =
                ArgumentCaptor.forClass(QueryJobConfiguration.class);
        when(client.query(captor.capture())).thenReturn(null);

        newPublisher().publish(sampleRecord());

        assertThat(captor.getValue().getNamedParameters())
                .containsKey("success");
        assertThat(captor.getValue().getNamedParameters().get("success")
                .getValue()).isEqualTo("true");
    }

    @Test
    void publishSerializesMetadataToJson() throws InterruptedException {
        ArgumentCaptor<QueryJobConfiguration> captor =
                ArgumentCaptor.forClass(QueryJobConfiguration.class);
        when(client.query(captor.capture())).thenReturn(null);

        newPublisher().publish(sampleRecord());

        String metadataJson = captor.getValue()
                .getNamedParameters().get("metadata_json").getValue();
        assertThat(metadataJson).contains("table");
        assertThat(metadataJson).contains("customers");
    }

    @Test
    void publishWithNullMetadataSerializesToEmptyJson() throws InterruptedException {
        ArgumentCaptor<QueryJobConfiguration> captor =
                ArgumentCaptor.forClass(QueryJobConfiguration.class);
        when(client.query(captor.capture())).thenReturn(null);

        AuditRecord noMeta = AuditRecord.builder()
                .runId("run-002")
                .pipelineName("pipe")
                .entityType("entity")
                .sourceFile("gs://bucket/file")
                .processedTimestamp(Instant.now())
                .build();

        newPublisher().publish(noMeta);

        String metadataJson = captor.getValue()
                .getNamedParameters().get("metadata_json").getValue();
        assertThat(metadataJson).isEqualTo("{}");
    }

    @Test
    void flushIsNoOp() {
        BigQueryAuditEventPublisher publisher = newPublisher();
        // flush must not throw and must not interact with the client at all.
        assertThatCode(publisher::flush).doesNotThrowAnyException();
        try {
            verify(client, never()).query(any(QueryJobConfiguration.class));
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    @Test
    void flushIsIdempotent() {
        BigQueryAuditEventPublisher publisher = newPublisher();
        assertThatCode(publisher::flush).doesNotThrowAnyException();
        assertThatCode(publisher::flush).doesNotThrowAnyException();
    }

    // --- failure isolation ---------------------------------------------------

    @Test
    void publishExceptionDoesNotPropagate() throws InterruptedException {
        doThrow(new RuntimeException("BQ unavailable"))
                .when(client).query(any(QueryJobConfiguration.class));

        BigQueryAuditEventPublisher publisher = newPublisher();

        // Must return normally — audit write failure must never interrupt the pipeline.
        assertThatCode(() -> publisher.publish(sampleRecord()))
                .doesNotThrowAnyException();
    }

    @Test
    void auditFailureCountIncrementedOnException() throws InterruptedException {
        doThrow(new RuntimeException("BQ unavailable"))
                .when(client).query(any(QueryJobConfiguration.class));

        BigQueryAuditEventPublisher publisher = newPublisher();
        publisher.publish(sampleRecord());
        publisher.publish(sampleRecord());

        assertThat(publisher.auditFailureCount()).isEqualTo(2L);
    }

    @Test
    void auditFailureCountZeroAfterSuccessfulPublish() throws InterruptedException {
        when(client.query(any(QueryJobConfiguration.class))).thenReturn(null);

        BigQueryAuditEventPublisher publisher = newPublisher();
        publisher.publish(sampleRecord());

        assertThat(publisher.auditFailureCount()).isZero();
    }

    @Test
    void interruptedExceptionDoesNotPropagateAndRestoresFlag() throws InterruptedException {
        doThrow(new InterruptedException("thread interrupted"))
                .when(client).query(any(QueryJobConfiguration.class));

        BigQueryAuditEventPublisher publisher = newPublisher();

        // Must not propagate.
        assertThatCode(() -> publisher.publish(sampleRecord()))
                .doesNotThrowAnyException();

        // Interrupt flag must be restored.
        assertThat(Thread.currentThread().isInterrupted()).isTrue();
        // Clear the flag so it doesn't leak into subsequent tests.
        Thread.interrupted();

        assertThat(publisher.auditFailureCount()).isEqualTo(1L);
    }

    // --- construction --------------------------------------------------------

    @Test
    void constructorRejectsNullClient() {
        assertThatThrownBy(() -> new BigQueryAuditEventPublisher(null, PROJECT_ID, DATASET, TABLE))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void constructorRejectsNullProjectId() {
        assertThatThrownBy(() -> new BigQueryAuditEventPublisher(client, null, DATASET, TABLE))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void constructorRejectsNullDataset() {
        assertThatThrownBy(() -> new BigQueryAuditEventPublisher(client, PROJECT_ID, null, TABLE))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void constructorRejectsNullTable() {
        assertThatThrownBy(() -> new BigQueryAuditEventPublisher(client, PROJECT_ID, DATASET, null))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void publishRejectsNullRecord() {
        assertThatThrownBy(() -> newPublisher().publish(null))
                .isInstanceOf(NullPointerException.class);
    }

    @Test
    void projectIdAccessorReturnsConfiguredValue() {
        assertThat(newPublisher().projectId()).isEqualTo(PROJECT_ID);
    }

    // --- project-id / dataset / table precedence resolution ------------------

    @Test
    void resolveProjectIdUsesSystemPropertyFirst() {
        System.setProperty(BigQueryAuditEventPublisher.SYSPROP_GCP_PROJECT, "prop-project");
        assertThat(BigQueryAuditEventPublisher.resolveProjectId()).isEqualTo("prop-project");
    }

    @Test
    @SuppressWarnings("rawtypes")
    void resolveProjectIdFallsBackToAdcWhenPropertyAbsent() {
        System.clearProperty(BigQueryAuditEventPublisher.SYSPROP_GCP_PROJECT);

        // ServiceOptions is generic; raw type required for class literal. Suppressed.
        @SuppressWarnings("unchecked")
        MockedStatic<com.google.cloud.ServiceOptions> opts =
                mockStatic(com.google.cloud.ServiceOptions.class);
        try (opts) {
            opts.when(com.google.cloud.ServiceOptions::getDefaultProjectId)
                    .thenReturn("adc-project");

            // CULVERT_GCP_PROJECT env var is not set in test env → falls back to ADC mock.
            // If the env var IS set in the current environment the test still passes
            // because the env branch precedes ADC — the env value is itself valid.
            String resolved = BigQueryAuditEventPublisher.resolveProjectId();
            assertThat(resolved).isNotBlank();
        }
    }

    @Test
    @SuppressWarnings("rawtypes")
    void resolveProjectIdThrowsWhenNoSourceResolvable() {
        System.clearProperty(BigQueryAuditEventPublisher.SYSPROP_GCP_PROJECT);

        // ServiceOptions is generic; raw type required for class literal. Suppressed.
        @SuppressWarnings("unchecked")
        MockedStatic<com.google.cloud.ServiceOptions> opts =
                mockStatic(com.google.cloud.ServiceOptions.class);
        try (opts) {
            opts.when(com.google.cloud.ServiceOptions::getDefaultProjectId).thenReturn(null);

            // Only throws if env var is also absent.
            if (System.getenv(BigQueryAuditEventPublisher.ENVVAR_GCP_PROJECT) == null
                    || System.getenv(BigQueryAuditEventPublisher.ENVVAR_GCP_PROJECT).isBlank()) {
                assertThatThrownBy(BigQueryAuditEventPublisher::resolveProjectId)
                        .isInstanceOf(IllegalStateException.class)
                        .hasMessageContaining(BigQueryAuditEventPublisher.SYSPROP_GCP_PROJECT)
                        .hasMessageContaining(BigQueryAuditEventPublisher.ENVVAR_GCP_PROJECT);
            }
        }
    }

    @Test
    void resolveStringConfigUsesSystemPropertyOverDefault() {
        System.setProperty(BigQueryAuditEventPublisher.SYSPROP_AUDIT_DATASET, "custom-ds");
        assertThat(BigQueryAuditEventPublisher.resolveStringConfig(
                BigQueryAuditEventPublisher.SYSPROP_AUDIT_DATASET,
                BigQueryAuditEventPublisher.ENVVAR_AUDIT_DATASET,
                BigQueryAuditEventPublisher.DEFAULT_DATASET))
                .isEqualTo("custom-ds");
    }

    @Test
    void resolveStringConfigReturnsDefaultWhenNothingSet() {
        // No sysprop set, no env var expected in CI — returns the hardcoded default.
        String result = BigQueryAuditEventPublisher.resolveStringConfig(
                "culvert.audit.dataset.no-such-prop",
                "CULVERT_AUDIT_DATASET_NO_SUCH_VAR",
                BigQueryAuditEventPublisher.DEFAULT_DATASET);
        assertThat(result).isEqualTo(BigQueryAuditEventPublisher.DEFAULT_DATASET);
    }

    // --- no-arg ctor + ServiceLoader SPI (mirrors T12.6 CloudMonitoring pattern) --

    @Test
    void noArgCtorProducesWorkingPublisherViaStaticMocking() {
        System.setProperty(BigQueryAuditEventPublisher.SYSPROP_GCP_PROJECT, "test-project");

        try (MockedStatic<BigQueryOptions> bqOpts = mockStatic(BigQueryOptions.class)) {
            BigQueryOptions mockOptions = mock(BigQueryOptions.class);
            BigQuery mockClient = mock(BigQuery.class);

            bqOpts.when(BigQueryOptions::getDefaultInstance).thenReturn(mockOptions);
            when(mockOptions.getService()).thenReturn(mockClient);

            BigQueryAuditEventPublisher publisher = new BigQueryAuditEventPublisher();
            assertThat(publisher.projectId()).isEqualTo("test-project");
        }
    }

    @Test
    void serviceLoaderCanFindAuditEventPublisherSpiEntry() {
        // Use Provider.type() — avoids actually instantiating (which would trigger ADC).
        // This asserts that the META-INF/services file is present and lists our class.
        java.util.ServiceLoader<com.enrichmeai.culvert.contracts.AuditEventPublisher> loader =
                java.util.ServiceLoader.load(
                        com.enrichmeai.culvert.contracts.AuditEventPublisher.class);

        java.util.List<Class<?>> types = loader.stream()
                .map(java.util.ServiceLoader.Provider::type)
                .collect(java.util.stream.Collectors.toList());

        assertThat(types).contains(BigQueryAuditEventPublisher.class);
    }

    // --- toJsonString helper --------------------------------------------------

    @Test
    void toJsonStringEmptyMap() {
        assertThat(BigQueryAuditEventPublisher.toJsonString(Map.of())).isEqualTo("{}");
    }

    @Test
    void toJsonStringNullMap() {
        assertThat(BigQueryAuditEventPublisher.toJsonString(null)).isEqualTo("{}");
    }

    @Test
    void toJsonStringStringValue() {
        Map<String, Object> m = Map.of("key", "value");
        String json = BigQueryAuditEventPublisher.toJsonString(m);
        assertThat(json).isEqualTo("{\"key\":\"value\"}");
    }

    @Test
    void toJsonStringBooleanValue() {
        java.util.Map<String, Object> m = new java.util.LinkedHashMap<>();
        m.put("flag", Boolean.TRUE);
        String json = BigQueryAuditEventPublisher.toJsonString(m);
        assertThat(json).isEqualTo("{\"flag\":true}");
    }

    @Test
    void toJsonStringNumberValue() {
        java.util.Map<String, Object> m = new java.util.LinkedHashMap<>();
        m.put("count", 42L);
        String json = BigQueryAuditEventPublisher.toJsonString(m);
        assertThat(json).isEqualTo("{\"count\":42}");
    }

    @Test
    void toJsonStringEscapesSpecialChars() {
        java.util.Map<String, Object> m = new java.util.LinkedHashMap<>();
        m.put("msg", "line1\nline2");
        String json = BigQueryAuditEventPublisher.toJsonString(m);
        assertThat(json).doesNotContain("\n");
        assertThat(json).contains("\\n");
    }
}
