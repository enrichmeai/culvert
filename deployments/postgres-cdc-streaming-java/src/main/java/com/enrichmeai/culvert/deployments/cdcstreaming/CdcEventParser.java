package com.enrichmeai.culvert.deployments.cdcstreaming;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.Serializable;
import java.time.Instant;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Optional;

/**
 * Parses Debezium-format CDC change events (JSON), mirroring
 * {@code ParseCDCEventDoFn} from the Python reference implementation
 * (gcp-pipeline-reference deployments/postgres-cdc-streaming/src/streaming_pipeline/pipeline/cdc_parser.py:20-131).
 *
 * <h2>Debezium event structure (see Python docstring, cdc_parser.py:24-39)</h2>
 * <pre>{@code
 * {
 *   "before": {...},      // record state before change (null for INSERT)
 *   "after": {...},       // record state after change (null for DELETE)
 *   "source": {
 *     "version": "2.4.0", "connector": "postgresql", "name": "pg-cdc",
 *     "ts_ms": 1709807400000, "db": "customers_db", "schema": "public",
 *     "table": "customers"
 *   },
 *   "op": "c",            // c=create, u=update, d=delete, r=read (snapshot)
 *   "ts_ms": 1709807400123
 * }
 * }</pre>
 *
 * <h2>Operation mapping (cdc_parser.py:73-91)</h2>
 * <ul>
 *   <li>{@code op="c"} → INSERT, payload = {@code after}</li>
 *   <li>{@code op="u"} → UPDATE, payload = {@code after}</li>
 *   <li>{@code op="d"} → DELETE, payload = {@code before}</li>
 *   <li>{@code op="r"} → SNAPSHOT, payload = {@code after}</li>
 *   <li>anything else (schema-change events, missing {@code op}) → not a
 *       data event, {@link #parse(String)} returns {@link Optional#empty()}
 *       (cdc_parser.py:88-91, "Skipping non-data event").</li>
 * </ul>
 *
 * <h2>Error handling (parity with cdc_parser.py:124-131 and
 * tests/unit/test_cdc_parser.py: test_malformed_json_does_not_raise,
 * test_missing_op_field_does_not_raise)</h2>
 *
 * <p>Malformed JSON and any other parsing exception are caught and logged;
 * {@link #parse(String)} returns {@link Optional#empty()} rather than
 * throwing. Callers route empty results to the dead-letter sink (see
 * {@link CdcParseStage}) — this class never raises for bad input.
 *
 * <p>Empty record (both {@code after} and {@code before} absent/null for the
 * given operation) is also treated as invalid (cdc_parser.py:93-95,
 * "Empty record for operation ...").
 *
 * <p>Implements {@link Serializable} so it can be captured by a Beam
 * {@code DoFn} if a future sprint adds element-level Beam translation (see
 * README.md "Streaming semantics caveats").
 */
public final class CdcEventParser implements Serializable {

    private static final long serialVersionUID = 1L;

    private static final Logger LOG = LoggerFactory.getLogger(CdcEventParser.class);

    /** CDC metadata keys injected into the returned record — mirrors cdc_parser.py:98-119. */
    public static final String FIELD_CDC_OPERATION = "_cdc_operation";
    public static final String FIELD_CDC_SOURCE_TABLE = "_cdc_source_table";
    public static final String FIELD_CDC_SOURCE_DB = "_cdc_source_db";
    public static final String FIELD_CDC_SOURCE_SCHEMA = "_cdc_source_schema";
    public static final String FIELD_CDC_CONNECTOR = "_cdc_connector";
    public static final String FIELD_CDC_CONNECTOR_VERSION = "_cdc_connector_version";
    public static final String FIELD_CDC_EVENT_TIME = "_cdc_event_time";
    public static final String FIELD_CDC_SOURCE_TIME = "_cdc_source_time";

    private static final DateTimeFormatter ISO_INSTANT = DateTimeFormatter.ISO_INSTANT;

    // Transient: Jackson's ObjectMapper is not guaranteed Serializable across
    // versions; rebuild lazily rather than ship it. Mirrors the
    // "transient + lazy rebuild" pattern used by DefaultRuntimeContext's
    // registry (data-pipeline-core-java/src/main/java/com/enrichmeai/culvert/runtime/DefaultRuntimeContext.java:113).
    private transient volatile ObjectMapper mapper;

    private ObjectMapper mapper() {
        ObjectMapper local = mapper;
        if (local == null) {
            local = new ObjectMapper();
            mapper = local;
        }
        return local;
    }

    /**
     * Parse one Debezium CDC event.
     *
     * @param json JSON string containing the Debezium envelope.
     * @return The parsed event, or {@link Optional#empty()} if the input is
     *         malformed JSON, not a data event (schema change / unknown
     *         {@code op}), or the resolved record payload is empty.
     */
    public Optional<ParsedCdcEvent> parse(String json) {
        JsonNode event;
        try {
            event = mapper().readTree(json);
        } catch (Exception e) {
            LOG.error("JSON parse error: {}", e.getMessage());
            return Optional.empty();
        }

        try {
            return parseEvent(event);
        } catch (Exception e) {
            LOG.error("Unexpected error parsing CDC event: {}", e.getMessage());
            return Optional.empty();
        }
    }

    private Optional<ParsedCdcEvent> parseEvent(JsonNode event) {
        String operationCode = textOrNull(event, "op");
        JsonNode source = event.path("source");

        CdcOperation operation;
        JsonNode payload;
        switch (operationCode == null ? "" : operationCode) {
            case "c" -> {
                operation = CdcOperation.INSERT;
                payload = event.path("after");
            }
            case "u" -> {
                operation = CdcOperation.UPDATE;
                payload = event.path("after");
            }
            case "d" -> {
                operation = CdcOperation.DELETE;
                payload = event.path("before");
            }
            case "r" -> {
                operation = CdcOperation.SNAPSHOT;
                payload = event.path("after");
            }
            default -> {
                LOG.debug("Skipping non-data event: op={}", operationCode);
                return Optional.empty();
            }
        }

        if (payload == null || payload.isMissingNode() || payload.isNull() || payload.isEmpty()) {
            LOG.warn("Empty record for operation {}", operationCode);
            return Optional.empty();
        }

        Map<String, Object> record = toMap(payload);

        long eventTsMs = longOrZero(event, "ts_ms");
        String eventTimeIso = eventTsMs != 0
                ? ISO_INSTANT.format(Instant.ofEpochMilli(eventTsMs))
                : ISO_INSTANT.format(Instant.now());

        long sourceTsMs = longOrZero(source, "ts_ms");
        String sourceTimeIso = sourceTsMs != 0
                ? ISO_INSTANT.format(Instant.ofEpochMilli(sourceTsMs).atZone(ZoneOffset.UTC).toInstant())
                : null;

        return Optional.of(new ParsedCdcEvent(
                record,
                operation,
                textOrNull(source, "table"),
                textOrNull(source, "db"),
                textOrNull(source, "schema"),
                textOrNull(source, "connector"),
                textOrNull(source, "version"),
                eventTimeIso,
                sourceTimeIso));
    }

    private static Map<String, Object> toMap(JsonNode node) {
        Map<String, Object> map = new LinkedHashMap<>();
        node.fields().forEachRemaining(entry -> map.put(entry.getKey(), toJavaValue(entry.getValue())));
        return map;
    }

    private static Object toJavaValue(JsonNode value) {
        if (value == null || value.isNull() || value.isMissingNode()) {
            return null;
        }
        if (value.isTextual()) {
            return value.asText();
        }
        if (value.isBoolean()) {
            return value.asBoolean();
        }
        if (value.isIntegralNumber()) {
            return value.asLong();
        }
        if (value.isFloatingPointNumber()) {
            return value.asDouble();
        }
        // Objects/arrays: keep as text representation — the ODP/FDP transforms
        // in this deployment only read scalar fields (mirrors the Python
        // implementation, which never nests structured values into BigQuery
        // rows for this reference pipeline).
        return value.toString();
    }

    private static String textOrNull(JsonNode node, String field) {
        JsonNode v = node.path(field);
        return v.isMissingNode() || v.isNull() ? null : v.asText();
    }

    private static long longOrZero(JsonNode node, String field) {
        JsonNode v = node.path(field);
        return v.isMissingNode() || v.isNull() ? 0L : v.asLong();
    }
}
