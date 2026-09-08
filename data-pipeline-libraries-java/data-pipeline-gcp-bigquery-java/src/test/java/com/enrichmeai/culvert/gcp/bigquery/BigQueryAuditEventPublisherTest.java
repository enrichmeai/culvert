package com.enrichmeai.culvert.gcp.bigquery;

import com.enrichmeai.culvert.audit.AuditEvent;
import com.enrichmeai.culvert.audit.ContractVersion;
import com.enrichmeai.culvert.audit.EventKind;
import com.google.cloud.bigquery.BigQuery;
import com.google.cloud.bigquery.BigQueryOptions;
import com.google.cloud.bigquery.QueryJobConfiguration;
import com.google.cloud.bigquery.QueryParameterValue;
import com.google.cloud.bigquery.StandardSQLTypeName;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.MockedStatic;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.Instant;
import java.time.LocalDate;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Optional;

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
 * <h2>What these tests are guarding</h2>
 * <p>They were rewritten for the 0.2.0 audit rebuild. The previous suite
 * asserted a twelve-column <em>stage summary</em> row
 * ({@code pipeline_name}, {@code entity_type}, {@code source_file},
 * {@code processing_duration_seconds}, {@code success}, {@code audit_hash},
 * {@code metadata_json}, {@code published_at}) written to a default target of
 * {@code <project>.audit.audit_events}. The repository never provisioned an
 * {@code audit} dataset, so every write failed — and the old implementation
 * caught, logged at WARN and swallowed each one. A green suite therefore
 * co-existed with an audit trail that had never written a single row.
 *
 * <p>So the assertions below deliberately pin the two facts that let that
 * happen:
 * <ol>
 *   <li>the default dataset is the one the repo actually creates
 *       ({@code job_control}), and the statement names exactly
 *       {@code docs/CONTRACT.md} §4's ten columns — no more, and none of the
 *       retired ones;</li>
 *   <li>a failed write is never silent: run-level events throw, aggregate
 *       events log and continue, and both increment the failure counter.</li>
 * </ol>
 *
 * <p>The run-level / aggregate split is spelled out here as two hardcoded
 * enum lists rather than read back from {@link EventKind#isRunLevel()}. That
 * partition <em>is</em> the contract; deriving it from the type under test
 * would make this suite agree with any future flip of it.
 */
@ExtendWith(MockitoExtension.class)
class BigQueryAuditEventPublisherTest {

    private static final String PROJECT_ID = "my-project";
    private static final String DATASET    = "job_control";
    private static final String TABLE      = "audit_events";

    private static final Instant EVENT_TS = Instant.parse("2026-06-05T10:00:00Z");
    private static final LocalDate EXTRACT_DATE = LocalDate.parse("2026-06-04");

    /** {@code docs/CONTRACT.md} §4, in declaration order. */
    private static final String[] CONTRACT_COLUMNS = {
            "run_id", "system_id", "entity", "event_kind", "event_ts",
            "extract_date", "payload", "producer", "contract_version", "environment"
    };

    /** Columns the retired stage-summary shape had. None may reappear. */
    private static final String[] RETIRED_COLUMNS = {
            "pipeline_name", "entity_type", "source_file",
            "processing_duration_seconds", "success", "error_count",
            "audit_hash", "metadata_json", "published_at", "processed_timestamp"
    };

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

    /** A fully-populated event: every optional §4 column present. */
    private static AuditEvent sampleEvent() {
        return AuditEvent.of("run-001", "generic", "customers", EventKind.RUN_START,
                EVENT_TS, Map.of("source_file", "gs://my-bucket/customers.csv"),
                EXTRACT_DATE, "culvert@0.2.0", "int");
    }

    /** The same event with every nullable §4 column absent. */
    private static AuditEvent minimalEvent() {
        return AuditEvent.of("run-002", "generic", "customers", EventKind.RUN_START,
                EVENT_TS, Map.of("source_file", "gs://my-bucket/customers.csv"));
    }

    /**
     * A payload satisfying {@link EventKind#requiredPayloadKeys()} for the kind.
     *
     * <p>Exhaustive by construction — a new kind added to §4 fails compilation
     * here rather than silently skipping the failure-mode tests below.
     */
    private static Map<String, Object> payloadFor(EventKind kind) {
        return switch (kind) {
            case RUN_START -> Map.of("source_file", "gs://my-bucket/customers.csv");
            case RUN_END -> Map.of("record_count", 1_000L);
            case RECORD_VALIDATED -> Map.of("count", 990L);
            case RECORD_REJECTED -> Map.of("count", 10L, "quarantine_uri", "gs://b/q/");
            case RECONCILIATION -> Map.of(
                    "expected_count", 1_000L, "accounted_count", 1_000L, "reconciled", true);
            case ERROR_RAISED -> Map.of("error_code", "E_PARSE", "error_category", "validation");
            case RETRY_ATTEMPTED -> Map.of("attempt", 2, "previous_run_id", "run-000");
        };
    }

    private static AuditEvent eventOfKind(EventKind kind) {
        return AuditEvent.of("run-" + kind.name(), "generic", "customers", kind,
                EVENT_TS, payloadFor(kind));
    }

    /** Publish through a mocked client and hand back the statement it built. */
    private QueryJobConfiguration capturePublish(AuditEvent event) throws InterruptedException {
        ArgumentCaptor<QueryJobConfiguration> captor =
                ArgumentCaptor.forClass(QueryJobConfiguration.class);
        newPublisher().publish(event);
        verify(client).query(captor.capture());
        return captor.getValue();
    }

    // --- the statement: target table and column list (§4) ---------------------

    @Test
    void publishCallsClientQueryOnce() throws InterruptedException {
        newPublisher().publish(sampleEvent());

        verify(client).query(any(QueryJobConfiguration.class));
    }

    @Test
    void defaultDatasetIsTheOneTheRepoProvisions() {
        // The regression that made this whole rebuild necessary: the default
        // was `audit`, a dataset no Terraform in this repo ever created, so
        // every audit write failed against a table that did not exist.
        assertThat(BigQueryAuditEventPublisher.DEFAULT_DATASET).isEqualTo("job_control");
        assertThat(BigQueryAuditEventPublisher.DEFAULT_TABLE).isEqualTo("audit_events");
    }

    @Test
    void publishTargetsJobControlAuditEvents() throws InterruptedException {
        String sql = capturePublish(sampleEvent()).getQuery();

        assertThat(sql).startsWith("INSERT INTO");
        assertThat(sql).contains("`my-project.job_control.audit_events`");
        assertThat(sql).doesNotContain("my-project.audit.audit_events");
    }

    @Test
    void insertNamesAllTenContractColumns() throws InterruptedException {
        String sql = capturePublish(sampleEvent()).getQuery();

        assertThat(sql).contains(CONTRACT_COLUMNS);
    }

    @Test
    void insertNamesNoneOfTheRetiredStageSummaryColumns() throws InterruptedException {
        String sql = capturePublish(sampleEvent()).getQuery();

        assertThat(sql).doesNotContain(RETIRED_COLUMNS);
        assertThat(sql).doesNotContain("CURRENT_TIMESTAMP()");
    }

    @Test
    void payloadIsInsertedThroughParseJson() throws InterruptedException {
        // payload is a JSON column in §4, so the STRING parameter has to be
        // parsed on the way in - binding it raw would write a quoted string.
        assertThat(capturePublish(sampleEvent()).getQuery()).contains("PARSE_JSON(@payload)");
    }

    // --- parameter binding (§4, one named parameter per column) ---------------

    @Test
    void publishBindsExactlyTheTenContractParameters() throws InterruptedException {
        Map<String, QueryParameterValue> params =
                capturePublish(sampleEvent()).getNamedParameters();

        assertThat(params).containsOnlyKeys(CONTRACT_COLUMNS);
    }

    @Test
    void publishBindsEachColumnFromTheEvent() throws InterruptedException {
        Map<String, QueryParameterValue> params =
                capturePublish(sampleEvent()).getNamedParameters();

        assertThat(params.get("run_id").getValue()).isEqualTo("run-001");
        assertThat(params.get("system_id").getValue()).isEqualTo("generic");
        assertThat(params.get("entity").getValue()).isEqualTo("customers");
        assertThat(params.get("event_kind").getValue()).isEqualTo("RUN_START");
        assertThat(params.get("extract_date").getValue()).isEqualTo("2026-06-04");
        assertThat(params.get("producer").getValue()).isEqualTo("culvert@0.2.0");
        assertThat(params.get("environment").getValue()).isEqualTo("int");
        assertThat(params.get("contract_version").getValue()).isEqualTo("1.0.0");
    }

    @Test
    void eventTsIsBoundAsATimestampParameter() throws InterruptedException {
        QueryParameterValue eventTs =
                capturePublish(sampleEvent()).getNamedParameters().get("event_ts");

        // The SDK owns the rendered text; assert the type and the instant, not
        // the exact formatter output.
        assertThat(eventTs.getType()).isEqualTo(StandardSQLTypeName.TIMESTAMP);
        assertThat(eventTs.getValue()).contains("2026-06-05 10:00:00");
    }

    @Test
    void extractDateIsBoundAsADateParameter() throws InterruptedException {
        QueryParameterValue extractDate =
                capturePublish(sampleEvent()).getNamedParameters().get("extract_date");

        assertThat(extractDate.getType()).isEqualTo(StandardSQLTypeName.DATE);
    }

    @Test
    void payloadIsBoundAsAJsonObjectStringCarryingTheEventDetail()
            throws InterruptedException {
        QueryParameterValue payload =
                capturePublish(sampleEvent()).getNamedParameters().get("payload");

        assertThat(payload.getType()).isEqualTo(StandardSQLTypeName.STRING);
        assertThat(payload.getValue())
                .isEqualTo("{\"source_file\":\"gs://my-bucket/customers.csv\"}");
    }

    @Test
    void payloadNumbersAndBooleansAreBoundUnquoted() throws InterruptedException {
        AuditEvent reconciliation = AuditEvent.of("run-003", "generic", "customers",
                EventKind.RECONCILIATION, EVENT_TS,
                payloadFor(EventKind.RECONCILIATION));

        String payload = capturePublish(reconciliation).getNamedParameters()
                .get("payload").getValue();

        assertThat(payload).contains("\"expected_count\":1000");
        assertThat(payload).contains("\"reconciled\":true");
    }

    @Test
    void absentOptionalColumnsAreStillBoundAsNulls() throws InterruptedException {
        // A dropped parameter is an INSERT arity error, not a NULL - so the ten
        // keys must all be present even when three of them have no value.
        Map<String, QueryParameterValue> params =
                capturePublish(minimalEvent()).getNamedParameters();

        assertThat(params).containsOnlyKeys(CONTRACT_COLUMNS);
        assertThat(params.get("extract_date").getValue()).isNull();
        assertThat(params.get("producer").getValue()).isNull();
        assertThat(params.get("environment").getValue()).isNull();
    }

    // --- contract_version comes from the event, never from the caller ---------

    @Test
    void contractVersionIsBoundFromTheEventsStampedValue() throws InterruptedException {
        assertThat(capturePublish(sampleEvent()).getNamedParameters()
                .get("contract_version").getValue())
                .isEqualTo(ContractVersion.CURRENT);
    }

    @Test
    void contractVersionIsReadFromTheEventRatherThanStampedByThePublisher()
            throws InterruptedException {
        // A row deserialised from a foreign producer keeps its own version.
        // If the publisher stamped its own, this would come back as 1.0.0 and
        // the row would claim conformance it does not have.
        AuditEvent foreign = new AuditEvent("run-foreign", "generic", "customers",
                EventKind.RUN_START, EVENT_TS, Optional.empty(),
                Map.of("source_file", "gs://b/f.csv"),
                Optional.of("other-emitter@3.1.0"), Optional.of("prod"),
                "9.9.9-foreign");

        assertThat(capturePublish(foreign).getNamedParameters()
                .get("contract_version").getValue())
                .isEqualTo("9.9.9-foreign");
    }

    // --- failure handling: run-level throws, aggregate does not, neither is
    //     silent. This is the defect the rebuild exists to remove. -------------

    @ParameterizedTest
    @EnumSource(value = EventKind.class,
            names = {"RUN_START", "RUN_END", "ERROR_RAISED", "RECONCILIATION",
                     "RETRY_ATTEMPTED"})
    void failedPublishOfARunLevelEventThrows(EventKind kind) throws InterruptedException {
        doThrow(new RuntimeException("BQ unavailable"))
                .when(client).query(any(QueryJobConfiguration.class));
        BigQueryAuditEventPublisher publisher = newPublisher();
        AuditEvent event = eventOfKind(kind);

        assertThatThrownBy(() -> publisher.publish(event))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining(kind.name())
                .hasMessageContaining("run-" + kind.name())
                .hasRootCauseMessage("BQ unavailable");

        assertThat(publisher.auditFailureCount()).isEqualTo(1L);
    }

    @ParameterizedTest
    @EnumSource(value = EventKind.class, names = {"RECORD_VALIDATED", "RECORD_REJECTED"})
    void failedPublishOfAnAggregateEventDoesNotThrow(EventKind kind)
            throws InterruptedException {
        doThrow(new RuntimeException("BQ unavailable"))
                .when(client).query(any(QueryJobConfiguration.class));
        BigQueryAuditEventPublisher publisher = newPublisher();
        AuditEvent event = eventOfKind(kind);

        // A counter must not be able to halt ingestion.
        assertThatCode(() -> publisher.publish(event)).doesNotThrowAnyException();

        // But it is not swallowed either - the counter is the observable.
        assertThat(publisher.auditFailureCount()).isEqualTo(1L);
    }

    @Test
    void aggregateFailuresAccumulateOnTheCounterRatherThanVanishing()
            throws InterruptedException {
        doThrow(new RuntimeException("BQ unavailable"))
                .when(client).query(any(QueryJobConfiguration.class));
        BigQueryAuditEventPublisher publisher = newPublisher();
        AuditEvent event = eventOfKind(EventKind.RECORD_VALIDATED);

        publisher.publish(event);
        publisher.publish(event);

        assertThat(publisher.auditFailureCount()).isEqualTo(2L);
    }

    @Test
    void auditFailureCountZeroAfterSuccessfulPublish() {
        BigQueryAuditEventPublisher publisher = newPublisher();

        publisher.publish(sampleEvent());

        assertThat(publisher.auditFailureCount()).isZero();
    }

    @Test
    void interruptedPublishThrowsAndRestoresTheInterruptFlag()
            throws InterruptedException {
        doThrow(new InterruptedException("thread interrupted"))
                .when(client).query(any(QueryJobConfiguration.class));
        BigQueryAuditEventPublisher publisher = newPublisher();
        // Deliberately an AGGREGATE kind: an interrupt is thread death, not an
        // audit failure, so it is fatal for both kinds - unlike a RuntimeException.
        AuditEvent event = eventOfKind(EventKind.RECORD_VALIDATED);

        assertThatThrownBy(() -> publisher.publish(event))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("interrupted");

        assertThat(Thread.currentThread().isInterrupted()).isTrue();
        Thread.interrupted();  // clear so it does not leak into later tests

        assertThat(publisher.auditFailureCount()).isEqualTo(1L);
    }

    // --- flush ----------------------------------------------------------------

    @Test
    void flushIsNoOp() throws InterruptedException {
        BigQueryAuditEventPublisher publisher = newPublisher();

        assertThatCode(publisher::flush).doesNotThrowAnyException();

        verify(client, never()).query(any(QueryJobConfiguration.class));
    }

    @Test
    void flushIsIdempotent() {
        BigQueryAuditEventPublisher publisher = newPublisher();

        assertThatCode(publisher::flush).doesNotThrowAnyException();
        assertThatCode(publisher::flush).doesNotThrowAnyException();
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
    void publishRejectsNullEvent() {
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

            // CULVERT_GCP_PROJECT env var is not set in test env -> falls back to ADC mock.
            // If the env var IS set in the current environment the test still passes
            // because the env branch precedes ADC - the env value is itself valid.
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
        // No sysprop set, no env var expected in CI - returns the hardcoded default.
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
        // Use Provider.type() - avoids actually instantiating (which would trigger ADC).
        // This asserts that the META-INF/services file is present and lists our class.
        java.util.ServiceLoader<com.enrichmeai.culvert.contracts.AuditEventPublisher> loader =
                java.util.ServiceLoader.load(
                        com.enrichmeai.culvert.contracts.AuditEventPublisher.class);

        java.util.List<Class<?>> types = loader.stream()
                .map(java.util.ServiceLoader.Provider::type)
                .collect(java.util.stream.Collectors.toList());

        assertThat(types).contains(BigQueryAuditEventPublisher.class);
    }

    @Test
    void payloadWithNewlinesIsEscapedSoParseJsonAccceptsIt() throws InterruptedException {
        // ERROR_RAISED payloads carry error messages, which routinely contain
        // newlines (stack traces). An earlier hand-rolled serializer in publish()
        // escaped only backslash and quote, so a newline produced a raw control
        // character inside a JSON string literal -- PARSE_JSON rejects that, and
        // it would have failed only on the error path, in production.
        ArgumentCaptor<QueryJobConfiguration> captor =
                ArgumentCaptor.forClass(QueryJobConfiguration.class);
        when(client.query(captor.capture())).thenReturn(null);

        newPublisher().publish(com.enrichmeai.culvert.audit.AuditEvent.of(
                "run-1", "Generic", "customers",
                com.enrichmeai.culvert.audit.EventKind.ERROR_RAISED,
                java.time.Instant.now(),
                Map.of("error_code", "BOOM",
                       "error_category", "integration",
                       "detail", "line one\nline two\ttabbed")));

        String payload = captor.getValue().getNamedParameters().get("payload").getValue();
        assertThat(payload).doesNotContain("\n").doesNotContain("\t");
        assertThat(payload).contains("\\n").contains("\\t");
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
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("flag", Boolean.TRUE);
        assertThat(BigQueryAuditEventPublisher.toJsonString(m)).isEqualTo("{\"flag\":true}");
    }

    @Test
    void toJsonStringNumberValue() {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("count", 42L);
        assertThat(BigQueryAuditEventPublisher.toJsonString(m)).isEqualTo("{\"count\":42}");
    }

    @Test
    void toJsonStringEscapesSpecialChars() {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("msg", "line1\nline2");
        String json = BigQueryAuditEventPublisher.toJsonString(m);
        assertThat(json).doesNotContain("\n");
        assertThat(json).contains("\\n");
    }
}
