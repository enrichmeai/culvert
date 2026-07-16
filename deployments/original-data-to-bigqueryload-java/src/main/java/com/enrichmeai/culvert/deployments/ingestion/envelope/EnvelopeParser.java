package com.enrichmeai.culvert.deployments.ingestion.envelope;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.List;
import java.util.Locale;
import java.util.Objects;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Parses and validates HDR/TRL-enveloped CSV extracts.
 *
 * <p>Culvert Java has no HDR/TRL library today (verified — searched
 * {@code data-pipeline-libraries-java} for {@code file_management}, {@code HDRTRLParser};
 * none exist as of T20.5). This class ports the wire format and validation rules
 * from the retired predecessor's {@code gcp_pipeline_core.file_management.hdr_trl}
 * package (removed 2026-07), grounded in these source files (paths refer to git history):
 *
 * <ul>
 *   <li>Wire patterns —
 *       {@code gcp-pipeline-libraries/gcp-pipeline-core/src/gcp_pipeline_core/file_management/hdr_trl/constants.py:8-9}:
 *       <pre>
 *         DEFAULT_HDR_PATTERN = r'^HDR\|([^|]+)\|([^|]+)\|(\d{8})$'
 *         DEFAULT_TRL_PATTERN = r'^TRL\|RecordCount=(\d+)\|Checksum=([^|]+)$'
 *       </pre>
 *   <li>Header/trailer/data-line split —
 *       {@code .../hdr_trl/parser.py:121-154} ({@code HDRTRLParser.parse_file_lines}):
 *       header is line 0, trailer is the last line, data spans everything in
 *       between (data may itself start with a CSV column-header row).
 *   <li>Record-count validation —
 *       {@code gcp-pipeline-libraries/gcp-pipeline-beam/src/gcp_pipeline_beam/file_management/validator.py:193-231}
 *       ({@code validate_record_count}): excludes HDR, TRL, and (when present) one
 *       leading CSV header row from the count.
 *   <li>Checksum algorithm —
 *       {@code gcp-pipeline-libraries/gcp-pipeline-beam/src/gcp_pipeline_beam/file_management/integrity.py:97-159}
 *       ({@code compute_checksum} / {@code validate_checksum}): MD5 over the UTF-8
 *       bytes of each data line, fed to the digest in sequence (no separators, no
 *       final newline), hex-encoded, compared case-insensitively. The "data lines"
 *       fed to the checksum are the same span used for the record count (i.e. the
 *       CSV header row, if present, is excluded — mirrors
 *       {@code GenericFileValidator.validate} at
 *       {@code deployments/original-data-to-bigqueryload/src/data_ingestion/validation/file_validator.py:104-112}
 *       which slices {@code file_lines[metadata.data_start_line:metadata.data_end_line + 1]}
 *       and separately treats the first of those lines as the CSV header for the
 *       record-count arithmetic).
 * </ul>
 */
public final class EnvelopeParser {

    private static final Pattern HDR_PATTERN = Pattern.compile("^HDR\\|([^|]+)\\|([^|]+)\\|(\\d{8})$");
    private static final Pattern TRL_PATTERN = Pattern.compile("^TRL\\|RecordCount=(\\d+)\\|Checksum=([^|]+)$");

    private final boolean hasCsvHeaderRow;

    /**
     * @param hasCsvHeaderRow Whether the data span (between HDR and TRL) starts
     *                        with a CSV column-header row that must be excluded
     *                        from the record count and checksum. The Python
     *                        reference always sets this true for the Generic
     *                        entities (customers/accounts/decision/applications).
     */
    public EnvelopeParser(boolean hasCsvHeaderRow) {
        this.hasCsvHeaderRow = hasCsvHeaderRow;
    }

    /** Convenience: HDR/TRL with a leading CSV header row (the Python reference's only mode). */
    public static EnvelopeParser withCsvHeaderRow() {
        return new EnvelopeParser(true);
    }

    /**
     * Parse and validate {@code lines} (a full file, HDR through TRL inclusive).
     *
     * @param lines           All lines of the file, in order.
     * @param expectedSystemId The system id expected in the HDR (case-insensitive
     *                         compare, mirrors
     *                         {@code file_validator.py:74-75}).
     * @param expectedEntity   The entity name expected in the HDR (case-insensitive,
     *                         mirrors {@code file_validator.py:81-84}).
     * @return The parsed, fully-validated envelope.
     * @throws EnvelopeParseException on any structural or integrity failure.
     */
    public ParsedEnvelope parse(List<String> lines, String expectedSystemId, String expectedEntity) {
        Objects.requireNonNull(lines, "lines must not be null");
        if (lines.isEmpty()) {
            throw new EnvelopeParseException("Empty file - no lines to parse");
        }

        HeaderRecord header = parseHeader(lines.get(0));
        TrailerRecord trailer = parseTrailer(lines.get(lines.size() - 1));

        if (!header.systemId().equalsIgnoreCase(expectedSystemId)) {
            throw new EnvelopeParseException(
                    "System ID mismatch: expected " + expectedSystemId + ", got " + header.systemId());
        }
        if (!header.entityType().equalsIgnoreCase(expectedEntity)) {
            throw new EnvelopeParseException(
                    "Entity mismatch: expected " + expectedEntity + ", got " + header.entityType());
        }

        List<String> dataLines = lines.subList(1, lines.size() - 1);

        List<String> countedLines = hasCsvHeaderRow && !dataLines.isEmpty()
                ? dataLines.subList(1, dataLines.size())
                : dataLines;

        int actualCount = countedLines.size();
        if (actualCount != trailer.recordCount()) {
            throw new EnvelopeParseException(
                    "Record count mismatch: expected " + trailer.recordCount() + ", got " + actualCount);
        }

        String computed = computeChecksum(countedLines);
        if (!computed.equalsIgnoreCase(trailer.checksum())) {
            throw new EnvelopeParseException(
                    "Checksum mismatch: expected " + trailer.checksum() + ", got " + computed);
        }

        return new ParsedEnvelope(header, trailer, dataLines);
    }

    private HeaderRecord parseHeader(String line) {
        String trimmed = line.strip();
        Matcher m = HDR_PATTERN.matcher(trimmed);
        if (!m.matches()) {
            throw new EnvelopeParseException("Invalid header record: " + truncate(trimmed));
        }
        return new HeaderRecord(m.group(1), m.group(2), m.group(3), trimmed);
    }

    private TrailerRecord parseTrailer(String line) {
        String trimmed = line.strip();
        Matcher m = TRL_PATTERN.matcher(trimmed);
        if (!m.matches()) {
            throw new EnvelopeParseException("Invalid trailer record: " + truncate(trimmed));
        }
        return new TrailerRecord(Integer.parseInt(m.group(1)), m.group(2), trimmed);
    }

    /** MD5 over the UTF-8 bytes of each line, fed to the digest in sequence (no separators). */
    static String computeChecksum(List<String> dataLines) {
        MessageDigest digest;
        try {
            digest = MessageDigest.getInstance("MD5");
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("MD5 not available on this JVM", e);
        }
        for (String line : dataLines) {
            digest.update(line.getBytes(StandardCharsets.UTF_8));
        }
        byte[] hash = digest.digest();
        StringBuilder hex = new StringBuilder(hash.length * 2);
        for (byte b : hash) {
            hex.append(String.format(Locale.ROOT, "%02x", b));
        }
        return hex.toString();
    }

    private static String truncate(String s) {
        return s.length() > 100 ? s.substring(0, 100) : s;
    }
}
