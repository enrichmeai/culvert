package com.enrichmeai.culvert.deployments.cdcstreaming;

import java.util.Map;
import java.util.Objects;

/**
 * A successfully parsed Debezium CDC event: the record payload (either
 * {@code after} or {@code before}, depending on operation) plus CDC
 * metadata, mirroring the fields {@code ParseCDCEventDoFn.process} injects
 * into the record dict in the Python source (see
 * deployments/postgres-cdc-streaming/src/streaming_pipeline/pipeline/cdc_parser.py:97-119).
 *
 * @param record         The row payload ({@code after} for INSERT/UPDATE/SNAPSHOT,
 *                        {@code before} for DELETE). Never null or empty —
 *                        {@link CdcEventParser} rejects empty records.
 * @param operation      The classified CDC operation.
 * @param sourceTable    Debezium {@code source.table}, or null if absent.
 * @param sourceDb       Debezium {@code source.db}, or null if absent.
 * @param sourceSchema   Debezium {@code source.schema}, or null if absent.
 * @param connector      Debezium {@code source.connector}, or null if absent.
 * @param connectorVersion Debezium {@code source.version}, or null if absent.
 * @param eventTimeIso   ISO-8601 UTC timestamp derived from the envelope's
 *                        top-level {@code ts_ms} (falls back to "now" if
 *                        {@code ts_ms} is absent/zero — mirrors cdc_parser.py:106-112).
 * @param sourceTimeIso  ISO-8601 UTC timestamp derived from {@code source.ts_ms},
 *                        or null if absent/zero (cdc_parser.py:115-119).
 */
public record ParsedCdcEvent(
        Map<String, Object> record,
        CdcOperation operation,
        String sourceTable,
        String sourceDb,
        String sourceSchema,
        String connector,
        String connectorVersion,
        String eventTimeIso,
        String sourceTimeIso) {

    public ParsedCdcEvent {
        Objects.requireNonNull(record, "record must not be null");
        Objects.requireNonNull(operation, "operation must not be null");
        Objects.requireNonNull(eventTimeIso, "eventTimeIso must not be null");
    }
}
