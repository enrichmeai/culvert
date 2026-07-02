package com.enrichmeai.culvert.deployments.ingestion.testsupport;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * Builds well-formed HDR/TRL-enveloped test files with a correct MD5
 * checksum, so tests don't hand-compute hashes.
 */
public final class EnvelopeFixtures {

    private EnvelopeFixtures() {
    }

    /**
     * @param systemId   HDR system id.
     * @param entity     HDR entity type.
     * @param extractDate HDR extract date, yyyyMMdd.
     * @param csvHeader  The CSV header row (included in the data span, excluded from
     *                   the record count / checksum, per the wire format).
     * @param dataRows   The CSV data rows (checksummed and counted).
     * @return Full file lines: HDR, csvHeader, dataRows..., TRL.
     */
    public static List<String> buildFile(
            String systemId, String entity, String extractDate,
            String csvHeader, List<String> dataRows) {
        String checksum = md5(dataRows);
        List<String> lines = new ArrayList<>();
        lines.add("HDR|" + systemId + "|" + entity + "|" + extractDate);
        lines.add(csvHeader);
        lines.addAll(dataRows);
        lines.add("TRL|RecordCount=" + dataRows.size() + "|Checksum=" + checksum);
        return lines;
    }

    public static byte[] buildFileBytes(
            String systemId, String entity, String extractDate,
            String csvHeader, List<String> dataRows) {
        return String.join("\n", buildFile(systemId, entity, extractDate, csvHeader, dataRows))
                .getBytes(StandardCharsets.UTF_8);
    }

    public static String md5(List<String> lines) {
        MessageDigest digest;
        try {
            digest = MessageDigest.getInstance("MD5");
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
        for (String line : lines) {
            digest.update(line.getBytes(StandardCharsets.UTF_8));
        }
        StringBuilder hex = new StringBuilder();
        for (byte b : digest.digest()) {
            hex.append(String.format(Locale.ROOT, "%02x", b));
        }
        return hex.toString();
    }
}
