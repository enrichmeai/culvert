package com.enrichmeai.culvert.governance;

/**
 * Sensitivity classification for a field or table.
 *
 * <p>The four-tier model used by Dataplex, AWS Macie, and Azure Purview.
 * Mirrors the Python {@code DataClassification} enum.
 */
public enum DataClassification {
    PUBLIC("public"),
    INTERNAL("internal"),
    CONFIDENTIAL("confidential"),
    /** PII, PHI, financial — strongest controls. */
    RESTRICTED("restricted");

    private final String value;

    DataClassification(String value) {
        this.value = value;
    }

    public String getValue() {
        return value;
    }
}
