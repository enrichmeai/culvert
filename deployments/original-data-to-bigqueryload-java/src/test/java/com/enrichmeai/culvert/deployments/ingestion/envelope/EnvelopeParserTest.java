package com.enrichmeai.culvert.deployments.ingestion.envelope;

import com.enrichmeai.culvert.deployments.ingestion.testsupport.EnvelopeFixtures;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * Unit tests for {@link EnvelopeParser}, grounded in the wire format from the
 * Python reference (see {@link EnvelopeParser} class Javadoc for exact
 * source citations).
 */
class EnvelopeParserTest {

    private static final List<String> ROWS = List.of(
            "cust-1,Ada,Lovelace,123-45-6789,1990-01-01,A,2020-01-01",
            "cust-2,Alan,Turing,987-65-4321,1985-06-23,A,2019-05-05");

    @Test
    void parsesWellFormedEnvelope() {
        List<String> file = EnvelopeFixtures.buildFile(
                "Generic", "customers", "20260601",
                "customer_id,first_name,last_name,ssn,dob,status,created_date", ROWS);

        ParsedEnvelope envelope = EnvelopeParser.withCsvHeaderRow().parse(file, "Generic", "customers");

        assertThat(envelope.header().systemId()).isEqualTo("Generic");
        assertThat(envelope.header().entityType()).isEqualTo("customers");
        assertThat(envelope.header().extractDate()).isEqualTo("20260601");
        assertThat(envelope.trailer().recordCount()).isEqualTo(2);
        // dataLines includes the CSV header row (index 0) plus the 2 data rows.
        assertThat(envelope.dataLines()).hasSize(3);
        assertThat(envelope.dataLines().get(0))
                .isEqualTo("customer_id,first_name,last_name,ssn,dob,status,created_date");
    }

    @Test
    void systemIdMismatchThrows() {
        List<String> file = EnvelopeFixtures.buildFile(
                "OtherSystem", "customers", "20260601", "h", ROWS);

        assertThatThrownBy(() -> EnvelopeParser.withCsvHeaderRow().parse(file, "Generic", "customers"))
                .isInstanceOf(EnvelopeParseException.class)
                .hasMessageContaining("System ID mismatch");
    }

    @Test
    void entityMismatchThrows() {
        List<String> file = EnvelopeFixtures.buildFile(
                "Generic", "accounts", "20260601", "h", ROWS);

        assertThatThrownBy(() -> EnvelopeParser.withCsvHeaderRow().parse(file, "Generic", "customers"))
                .isInstanceOf(EnvelopeParseException.class)
                .hasMessageContaining("Entity mismatch");
    }

    @Test
    void recordCountMismatchThrows() {
        List<String> file = new java.util.ArrayList<>(EnvelopeFixtures.buildFile(
                "Generic", "customers", "20260601", "h", ROWS));
        // Corrupt the TRL's declared count without touching the actual rows.
        file.set(file.size() - 1, "TRL|RecordCount=99|Checksum=" + EnvelopeFixtures.md5(ROWS));

        assertThatThrownBy(() -> EnvelopeParser.withCsvHeaderRow().parse(file, "Generic", "customers"))
                .isInstanceOf(EnvelopeParseException.class)
                .hasMessageContaining("Record count mismatch");
    }

    @Test
    void checksumMismatchThrows() {
        List<String> file = new java.util.ArrayList<>(EnvelopeFixtures.buildFile(
                "Generic", "customers", "20260601", "h", ROWS));
        file.set(file.size() - 1, "TRL|RecordCount=" + ROWS.size() + "|Checksum=deadbeef");

        assertThatThrownBy(() -> EnvelopeParser.withCsvHeaderRow().parse(file, "Generic", "customers"))
                .isInstanceOf(EnvelopeParseException.class)
                .hasMessageContaining("Checksum mismatch");
    }

    @Test
    void malformedHeaderThrows() {
        List<String> file = List.of(
                "NOT_A_HEADER",
                "h",
                "TRL|RecordCount=0|Checksum=" + EnvelopeFixtures.md5(List.of()));

        assertThatThrownBy(() -> EnvelopeParser.withCsvHeaderRow().parse(file, "Generic", "customers"))
                .isInstanceOf(EnvelopeParseException.class)
                .hasMessageContaining("Invalid header record");
    }

    @Test
    void malformedTrailerThrows() {
        List<String> file = List.of(
                "HDR|Generic|customers|20260601",
                "h",
                "NOT_A_TRAILER");

        assertThatThrownBy(() -> EnvelopeParser.withCsvHeaderRow().parse(file, "Generic", "customers"))
                .isInstanceOf(EnvelopeParseException.class)
                .hasMessageContaining("Invalid trailer record");
    }

    @Test
    void emptyFileThrows() {
        assertThatThrownBy(() -> EnvelopeParser.withCsvHeaderRow().parse(List.of(), "Generic", "customers"))
                .isInstanceOf(EnvelopeParseException.class)
                .hasMessageContaining("Empty file");
    }

    @Test
    void checksumIsCaseInsensitive() {
        List<String> file = new java.util.ArrayList<>(EnvelopeFixtures.buildFile(
                "Generic", "customers", "20260601", "h", ROWS));
        String upperChecksum = EnvelopeFixtures.md5(ROWS).toUpperCase(java.util.Locale.ROOT);
        file.set(file.size() - 1, "TRL|RecordCount=" + ROWS.size() + "|Checksum=" + upperChecksum);

        ParsedEnvelope envelope = EnvelopeParser.withCsvHeaderRow().parse(file, "Generic", "customers");
        assertThat(envelope.trailer().checksum()).isEqualTo(upperChecksum);
    }
}
