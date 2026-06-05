package com.enrichmeai.culvert.gcp.gcs;

import com.enrichmeai.culvert.contracts.BlobStore;
import com.enrichmeai.culvert.contracts.JobControlRepository;
import com.enrichmeai.culvert.jobcontrol.FailureStage;
import com.google.gson.Gson;
import com.google.gson.reflect.TypeToken;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.lang.reflect.Type;
import java.nio.charset.StandardCharsets;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;

/**
 * Unit tests for {@link QuarantineHandler}. All dependencies are stubs /
 * mocks; no real GCS credentials or network are required.
 *
 * <p>DoD coverage:
 * <ul>
 *   <li>Non-empty list → writes serialised rows ({@link BlobStore#put}) and
 *       calls {@link JobControlRepository#markFailed} with the expected URI.
 *   <li>Empty list → no-op (neither BlobStore nor repository touched).
 *   <li>Quarantine path includes {@code runId} and a timestamp component.
 *   <li>Each quarantined record contains row content and violations
 *       (asserted by parsing the written bytes).
 *   <li>The URI passed to {@code markFailed} equals the URI passed to
 *       {@code BlobStore.put}.
 * </ul>
 *
 * Sprint-14 / issue #74 (T14.2).
 */
@ExtendWith(MockitoExtension.class)
class QuarantineHandlerTest {

    private static final String PREFIX = "gs://my-bucket/errors";
    private static final String RUN_ID = "run-abc-123";

    // Fixed clock: 2025-06-04T14:30:22.456Z → timestamp token "20250604T143022456Z"
    private static final Instant FIXED_INSTANT =
            Instant.parse("2025-06-04T14:30:22.456Z");
    private static final String EXPECTED_TIMESTAMP = "20250604T143022456Z";
    private static final String EXPECTED_URI =
            PREFIX + "/quarantine/" + RUN_ID + "/" + EXPECTED_TIMESTAMP + ".jsonl";

    private static final Clock FIXED_CLOCK =
            Clock.fixed(FIXED_INSTANT, ZoneOffset.UTC);

    @Mock
    private BlobStore blobStore;

    @Mock
    private JobControlRepository jobControlRepository;

    private QuarantineHandler handler;

    private static final Gson GSON = new Gson();

    @BeforeEach
    void setUp() {
        handler = new QuarantineHandler(blobStore, jobControlRepository, PREFIX, FIXED_CLOCK);
    }

    // ---- helpers ----

    /** Build a minimal {@link FailedRowRecord} inline without importing T14.1 types. */
    private static FailedRowRecord makeRecord(Map<String, Object> row,
                                              List<FailedRowRecord.ViolationDescriptor> violations) {
        return new FailedRowRecord() {
            @Override
            public Map<String, Object> rowContent() {
                return row;
            }

            @Override
            public List<? extends ViolationDescriptor> violations() {
                return violations;
            }
        };
    }

    private static FailedRowRecord.ViolationDescriptor violation(String field, String rule) {
        return new FailedRowRecord.ViolationDescriptor() {
            @Override
            public String field() {
                return field;
            }

            @Override
            public String rule() {
                return rule;
            }
        };
    }

    // ---- tests ----

    @Test
    void nonEmptyList_writesNdjsonAndCallsMarkFailed() {
        List<FailedRowRecord> failures = List.of(
                makeRecord(
                        Map.of("id", 1, "name", "Alice"),
                        List.of(violation("name", "must not be null"))));

        handler.writeFailures(RUN_ID, failures);

        // Verify BlobStore.put called with the expected URI
        ArgumentCaptor<String> uriCaptor = ArgumentCaptor.forClass(String.class);
        ArgumentCaptor<byte[]> bytesCaptor = ArgumentCaptor.forClass(byte[].class);
        verify(blobStore).put(uriCaptor.capture(), bytesCaptor.capture());

        assertThat(uriCaptor.getValue()).isEqualTo(EXPECTED_URI);

        // Verify markFailed called with the SAME uri in errorFilePath
        @SuppressWarnings({"unchecked", "rawtypes"})
        ArgumentCaptor<Optional<String>> errorFileCaptor =
                (ArgumentCaptor<Optional<String>>) (ArgumentCaptor) ArgumentCaptor.forClass(Optional.class);
        verify(jobControlRepository).markFailed(
                eq(RUN_ID),
                eq(QuarantineHandler.ERROR_CODE),
                any(String.class),
                eq(FailureStage.VALIDATION),
                errorFileCaptor.capture());

        assertThat(errorFileCaptor.getValue())
                .isPresent()
                .hasValue(EXPECTED_URI);

        // The URI in put == URI in markFailed
        assertThat(uriCaptor.getValue()).isEqualTo(errorFileCaptor.getValue().get());
    }

    @Test
    void emptyList_isNoOp() {
        handler.writeFailures(RUN_ID, List.of());

        verify(blobStore, never()).put(any(), any());
        verify(jobControlRepository, never()).markFailed(
                any(), any(), any(), any(), any());
    }

    @Test
    void quarantinePathContainsRunIdAndTimestamp() {
        List<FailedRowRecord> failures = List.of(
                makeRecord(Map.of("k", "v"), List.of()));

        handler.writeFailures(RUN_ID, failures);

        ArgumentCaptor<String> uriCaptor = ArgumentCaptor.forClass(String.class);
        verify(blobStore).put(uriCaptor.capture(), any());

        String uri = uriCaptor.getValue();
        assertThat(uri).contains(RUN_ID);
        assertThat(uri).contains(EXPECTED_TIMESTAMP);
        // Path structure: <prefix>/quarantine/<runId>/<ts>.jsonl
        assertThat(uri).matches(".*quarantine/" + RUN_ID + "/[^/]+\\.jsonl$");
    }

    @Test
    void twoRunsWithDifferentRunIds_produceDifferentUris() {
        // Different runIds => different path segments (no collision)
        String runId1 = "run-1";
        String runId2 = "run-2";

        QuarantineHandler h1 = new QuarantineHandler(
                blobStore, jobControlRepository, PREFIX, FIXED_CLOCK);
        QuarantineHandler h2 = new QuarantineHandler(
                blobStore, jobControlRepository, PREFIX, FIXED_CLOCK);

        List<FailedRowRecord> failures = List.of(
                makeRecord(Map.of("x", "y"), List.of()));

        h1.writeFailures(runId1, failures);
        h2.writeFailures(runId2, failures);

        ArgumentCaptor<String> uriCaptor = ArgumentCaptor.forClass(String.class);
        verify(blobStore, org.mockito.Mockito.times(2)).put(uriCaptor.capture(), any());

        List<String> uris = uriCaptor.getAllValues();
        assertThat(uris.get(0)).isNotEqualTo(uris.get(1));
        assertThat(uris.get(0)).contains(runId1);
        assertThat(uris.get(1)).contains(runId2);
    }

    @Test
    void writtenBytesContainRowContentAndViolations() {
        Map<String, Object> row = Map.of("orderId", "O-42", "amount", 999.99);
        List<FailedRowRecord.ViolationDescriptor> violations = List.of(
                violation("amount", "must be <= 500"),
                violation("orderId", "unrecognised prefix"));

        List<FailedRowRecord> failures = List.of(makeRecord(row, violations));

        handler.writeFailures(RUN_ID, failures);

        ArgumentCaptor<byte[]> bytesCaptor = ArgumentCaptor.forClass(byte[].class);
        verify(blobStore).put(any(), bytesCaptor.capture());

        String ndjson = new String(bytesCaptor.getValue(), StandardCharsets.UTF_8);

        // Should be exactly one line (plus trailing newline)
        String[] lines = ndjson.split("\n");
        assertThat(lines).hasSize(1);

        Type mapType = new TypeToken<Map<String, Object>>() {}.getType();
        Map<String, Object> parsed = GSON.fromJson(lines[0], mapType);

        // "row" key present with the field values
        assertThat(parsed).containsKey("row");
        @SuppressWarnings("unchecked")
        Map<String, Object> parsedRow = (Map<String, Object>) parsed.get("row");
        assertThat(parsedRow).containsKey("orderId");
        assertThat(parsedRow).containsKey("amount");

        // "violations" key present with both violation entries
        assertThat(parsed).containsKey("violations");
        @SuppressWarnings("unchecked")
        List<Map<String, String>> parsedViolations =
                (List<Map<String, String>>) parsed.get("violations");
        assertThat(parsedViolations).hasSize(2);

        assertThat(parsedViolations.get(0)).containsEntry("field", "amount");
        assertThat(parsedViolations.get(0)).containsEntry("rule", "must be <= 500");
        assertThat(parsedViolations.get(1)).containsEntry("field", "orderId");
        assertThat(parsedViolations.get(1)).containsEntry("rule", "unrecognised prefix");
    }

    @Test
    void multipleFailures_eachRecordOnSeparateLine() {
        List<FailedRowRecord> failures = List.of(
                makeRecord(Map.of("id", 1), List.of(violation("id", "out of range"))),
                makeRecord(Map.of("id", 2), List.of(violation("id", "duplicate"))),
                makeRecord(Map.of("id", 3), List.of()));

        handler.writeFailures(RUN_ID, failures);

        ArgumentCaptor<byte[]> bytesCaptor = ArgumentCaptor.forClass(byte[].class);
        verify(blobStore).put(any(), bytesCaptor.capture());

        String ndjson = new String(bytesCaptor.getValue(), StandardCharsets.UTF_8);
        // NDJSON: N records → N lines (trailing newline means split gives N elements)
        String[] lines = ndjson.split("\n");
        assertThat(lines).hasSize(3);

        // Each line is valid JSON
        Type mapType = new TypeToken<Map<String, Object>>() {}.getType();
        for (String line : lines) {
            Map<String, Object> obj = GSON.fromJson(line, mapType);
            assertThat(obj).containsKeys("row", "violations");
        }
    }

    @Test
    void prefixWithTrailingSlash_normalisedToSingleSlash() {
        // Prefix ending in "/" should not produce double-slash in path
        QuarantineHandler h = new QuarantineHandler(
                blobStore, jobControlRepository,
                "gs://my-bucket/errors/", FIXED_CLOCK);

        h.writeFailures(RUN_ID, List.of(makeRecord(Map.of("k", "v"), List.of())));

        ArgumentCaptor<String> uriCaptor = ArgumentCaptor.forClass(String.class);
        verify(blobStore).put(uriCaptor.capture(), any());

        assertThat(uriCaptor.getValue()).doesNotContain("//quarantine");
        assertThat(uriCaptor.getValue())
                .startsWith("gs://my-bucket/errors/quarantine/");
    }
}
