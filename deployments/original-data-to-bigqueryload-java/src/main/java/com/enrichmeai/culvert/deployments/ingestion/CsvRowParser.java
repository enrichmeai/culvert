package com.enrichmeai.culvert.deployments.ingestion;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * Parses one CSV data line into a {@code Map<String,Object>} keyed by the
 * entity's column headers.
 *
 * <p>Ports the CSV-splitting semantics of the Python reference's
 * {@code ParseAndValidateRecordDoFn.process} (main gcp-pipeline-reference
 * checkout,
 * {@code deployments/original-data-to-bigqueryload/src/data_ingestion/pipeline/transforms.py:89-134}):
 * a naive {@code line.split(',')} (no quoted-field handling — the Python source
 * has none either), skip blank lines, skip a line that re-states the header
 * (defence against a stray CSV header row inside the data span), and flag a
 * field-count mismatch as an error rather than throwing.
 */
public final class CsvRowParser {

    private final List<String> headers;

    public CsvRowParser(List<String> headers) {
        this.headers = List.copyOf(headers);
    }

    /**
     * Parse one line.
     *
     * @return {@link Optional#empty()} for a blank line or a line that
     *         duplicates the header row (both are silently skipped, mirroring
     *         the Python source); otherwise a {@link ParsedRow} that is either
     *         a valid field map or a field-count-mismatch error.
     */
    public Optional<ParsedRow> parseLine(String rawLine) {
        String line = rawLine.strip();
        if (line.isEmpty()) {
            return Optional.empty();
        }

        String[] values = line.split(",", -1);
        if (values.length == headers.size() && matchesHeaderRow(values)) {
            return Optional.empty();
        }

        if (values.length != headers.size()) {
            return Optional.of(ParsedRow.error(line,
                    "Field count mismatch: expected " + headers.size() + ", got " + values.length));
        }

        Map<String, Object> record = new LinkedHashMap<>(headers.size() * 2);
        for (int i = 0; i < headers.size(); i++) {
            record.put(headers.get(i), values[i]);
        }
        return Optional.of(ParsedRow.ok(record));
    }

    private boolean matchesHeaderRow(String[] values) {
        for (int i = 0; i < headers.size(); i++) {
            if (!headers.get(i).equals(values[i])) {
                return false;
            }
        }
        return true;
    }

    /** Either a parsed field map or a parse-level error (field-count mismatch). */
    public static final class ParsedRow {
        private final Map<String, Object> fields;
        private final String rawLine;
        private final String error;

        private ParsedRow(Map<String, Object> fields, String rawLine, String error) {
            this.fields = fields;
            this.rawLine = rawLine;
            this.error = error;
        }

        static ParsedRow ok(Map<String, Object> fields) {
            return new ParsedRow(fields, null, null);
        }

        static ParsedRow error(String rawLine, String error) {
            return new ParsedRow(null, rawLine, error);
        }

        public boolean isError() {
            return error != null;
        }

        public Map<String, Object> fields() {
            if (isError()) {
                throw new IllegalStateException("ParsedRow is an error, not a field map: " + error);
            }
            return fields;
        }

        public String rawLine() {
            return rawLine;
        }

        public String error() {
            if (!isError()) {
                throw new IllegalStateException("ParsedRow is not an error");
            }
            return error;
        }
    }
}
