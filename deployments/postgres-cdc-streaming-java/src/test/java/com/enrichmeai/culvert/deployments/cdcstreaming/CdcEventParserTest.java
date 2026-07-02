package com.enrichmeai.culvert.deployments.cdcstreaming;

import org.junit.jupiter.api.Test;

import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Unit tests for {@link CdcEventParser}, mirroring
 * tests/unit/test_cdc_parser.py from the Python reference implementation
 * (gcp-pipeline-reference deployments/postgres-cdc-streaming/tests/unit/test_cdc_parser.py)
 * case-for-case: insert/update/delete classification, CDC metadata presence,
 * and graceful handling of malformed JSON / missing {@code op}.
 */
class CdcEventParserTest {

    private final CdcEventParser parser = new CdcEventParser();

    private static final String INSERT_EVENT = """
            {
              "before": null,
              "after": {
                "customer_id": "C001",
                "full_name": "Jane Smith",
                "email": "jane@example.com",
                "ssn": "123456789"
              },
              "source": {
                "version": "2.4.0",
                "connector": "postgresql",
                "name": "pg-cdc",
                "ts_ms": 1709807400000,
                "db": "customers_db",
                "schema": "public",
                "table": "customers"
              },
              "op": "c",
              "ts_ms": 1709807400123
            }
            """;

    private static final String UPDATE_EVENT = """
            {
              "before": {"customer_id": "C001", "full_name": "Jane Smith"},
              "after": {"customer_id": "C001", "full_name": "Jane Smith-Jones"},
              "source": {
                "connector": "postgresql",
                "table": "customers",
                "db": "customers_db",
                "schema": "public",
                "ts_ms": 1709807500000
              },
              "op": "u",
              "ts_ms": 1709807500123
            }
            """;

    private static final String DELETE_EVENT = """
            {
              "before": {"customer_id": "C001", "full_name": "Jane Smith"},
              "after": null,
              "source": {
                "connector": "postgresql",
                "table": "customers",
                "db": "customers_db",
                "schema": "public",
                "ts_ms": 1709807600000
              },
              "op": "d",
              "ts_ms": 1709807600123
            }
            """;

    // test_insert_event_parses_after_record
    @Test
    void insertEventParsesAfterRecord() {
        Optional<ParsedCdcEvent> result = parser.parse(INSERT_EVENT);

        assertThat(result).isPresent();
        assertThat(result.get().record().get("customer_id")).isEqualTo("C001");
        assertThat(result.get().record().get("full_name")).isEqualTo("Jane Smith");
    }

    // test_insert_event_has_cdc_metadata
    @Test
    void insertEventHasCdcMetadata() {
        Optional<ParsedCdcEvent> result = parser.parse(INSERT_EVENT);

        assertThat(result).isPresent();
        ParsedCdcEvent event = result.get();
        assertThat(event.operation()).isEqualTo(CdcOperation.INSERT);
        assertThat(event.sourceTable()).isEqualTo("customers");
    }

    // test_update_event_parses_after_record
    @Test
    void updateEventParsesAfterRecordAndOperation() {
        Optional<ParsedCdcEvent> result = parser.parse(UPDATE_EVENT);

        assertThat(result).isPresent();
        assertThat(result.get().record().get("full_name")).isEqualTo("Jane Smith-Jones");
        assertThat(result.get().operation()).isEqualTo(CdcOperation.UPDATE);
    }

    // test_delete_event_has_delete_operation
    @Test
    void deleteEventHasDeleteOperation() {
        Optional<ParsedCdcEvent> result = parser.parse(DELETE_EVENT);

        assertThat(result).isPresent();
        assertThat(result.get().operation()).isEqualTo(CdcOperation.DELETE);
        // DELETE payload comes from "before", per cdc_parser.py:81-84.
        assertThat(result.get().record().get("full_name")).isEqualTo("Jane Smith");
    }

    // test_malformed_json_does_not_raise
    @Test
    void malformedJsonDoesNotRaiseAndYieldsEmpty() {
        Optional<ParsedCdcEvent> result = parser.parse("not valid json {{{");

        assertThat(result).isEmpty();
    }

    // test_missing_op_field_does_not_raise
    @Test
    void missingOpFieldDoesNotRaiseAndYieldsEmpty() {
        String event = "{\"after\": {\"id\": \"1\"}, \"source\": {\"table\": \"test\"}}";

        Optional<ParsedCdcEvent> result = parser.parse(event);

        assertThat(result).isEmpty();
    }

    @Test
    void snapshotOperationParsesAfterRecord() {
        String snapshotEvent = """
                {
                  "before": null,
                  "after": {"customer_id": "C002", "full_name": "Bob Lee"},
                  "source": {"connector": "postgresql", "table": "customers", "db": "customers_db", "schema": "public"},
                  "op": "r",
                  "ts_ms": 1709807700000
                }
                """;

        Optional<ParsedCdcEvent> result = parser.parse(snapshotEvent);

        assertThat(result).isPresent();
        assertThat(result.get().operation()).isEqualTo(CdcOperation.SNAPSHOT);
    }

    @Test
    void schemaChangeEventIsSkipped() {
        // Neither c/u/d/r — mirrors cdc_parser.py:88-91 "Skipping non-data event".
        String schemaChangeEvent = "{\"op\": \"m\", \"source\": {\"table\": \"customers\"}}";

        Optional<ParsedCdcEvent> result = parser.parse(schemaChangeEvent);

        assertThat(result).isEmpty();
    }

    @Test
    void emptyRecordIsRejected() {
        // op=c but "after" is an empty object — cdc_parser.py:93-95 "Empty record".
        String emptyAfterEvent = "{\"op\": \"c\", \"after\": {}, \"source\": {\"table\": \"customers\"}, \"ts_ms\": 1709807400123}";

        Optional<ParsedCdcEvent> result = parser.parse(emptyAfterEvent);

        assertThat(result).isEmpty();
    }

    @Test
    void deleteWithNullBeforeIsRejected() {
        // op=d but "before" is null — no payload to route to dead-letter.
        String noBeforeEvent = "{\"op\": \"d\", \"before\": null, \"source\": {\"table\": \"customers\"}}";

        Optional<ParsedCdcEvent> result = parser.parse(noBeforeEvent);

        assertThat(result).isEmpty();
    }

    @Test
    void missingTsMsFallsBackToNowRatherThanThrowing() {
        String noTsEvent = "{\"op\": \"c\", \"after\": {\"id\": \"1\"}, \"source\": {\"table\": \"t\"}}";

        Optional<ParsedCdcEvent> result = parser.parse(noTsEvent);

        assertThat(result).isPresent();
        assertThat(result.get().eventTimeIso()).isNotBlank();
        // source.ts_ms absent -> sourceTimeIso stays null (cdc_parser.py:115-119).
        assertThat(result.get().sourceTimeIso()).isNull();
    }
}
