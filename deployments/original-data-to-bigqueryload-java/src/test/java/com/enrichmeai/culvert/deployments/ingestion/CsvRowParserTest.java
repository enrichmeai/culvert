package com.enrichmeai.culvert.deployments.ingestion;

import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;

class CsvRowParserTest {

    private final CsvRowParser parser = new CsvRowParser(
            List.of("customer_id", "first_name", "last_name", "ssn", "dob", "status", "created_date"));

    @Test
    void parsesWellFormedLine() {
        Optional<CsvRowParser.ParsedRow> result =
                parser.parseLine("cust-1,Ada,Lovelace,123-45-6789,1990-01-01,A,2020-01-01");

        assertThat(result).isPresent();
        assertThat(result.get().isError()).isFalse();
        assertThat(result.get().fields())
                .containsEntry("customer_id", "cust-1")
                .containsEntry("first_name", "Ada")
                .containsEntry("status", "A");
    }

    @Test
    void blankLineIsSkipped() {
        assertThat(parser.parseLine("   ")).isEmpty();
        assertThat(parser.parseLine("")).isEmpty();
    }

    @Test
    void duplicateHeaderRowIsSkipped() {
        assertThat(parser.parseLine("customer_id,first_name,last_name,ssn,dob,status,created_date")).isEmpty();
    }

    @Test
    void fieldCountMismatchYieldsError() {
        Optional<CsvRowParser.ParsedRow> result = parser.parseLine("cust-1,Ada,Lovelace");

        assertThat(result).isPresent();
        assertThat(result.get().isError()).isTrue();
        assertThat(result.get().error()).contains("Field count mismatch: expected 7, got 3");
        assertThat(result.get().rawLine()).isEqualTo("cust-1,Ada,Lovelace");
    }

    @Test
    void trailingEmptyFieldsArePreserved() {
        // split(",", -1) must NOT drop trailing empty fields (default String.split would).
        Optional<CsvRowParser.ParsedRow> result =
                parser.parseLine("cust-1,Ada,Lovelace,123-45-6789,1990-01-01,,");

        assertThat(result).isPresent();
        assertThat(result.get().isError()).isFalse();
        assertThat(result.get().fields()).containsEntry("status", "").containsEntry("created_date", "");
    }
}
