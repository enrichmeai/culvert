package com.enrichmeai.culvert.deployments.ingestion;

/**
 * Outcome of one {@link IngestionRunner#run} call.
 *
 * @param runId            The run identifier processed.
 * @param entity           The entity processed.
 * @param candidateRowCount CSV data rows successfully split into field maps
 *                         (excludes blank lines and the duplicate CSV header
 *                         row, includes both schema-valid and schema-invalid rows).
 * @param validRowCount    Rows that passed schema validation and were staged for load.
 * @param invalidRowCount  Rows quarantined — CSV parse errors plus schema violations.
 * @param loadedRowCount   Rows {@link com.enrichmeai.culvert.contracts.Warehouse#loadFromUri}
 *                         reported as loaded.
 * @param reconciliation   Declared-vs-loaded count comparison.
 */
public record IngestionResult(
        String runId,
        String entity,
        int candidateRowCount,
        int validRowCount,
        int invalidRowCount,
        long loadedRowCount,
        ReconciliationResult reconciliation) {
}
