package com.enrichmeai.culvert.deployments.ingestion;

import com.enrichmeai.culvert.dataquality.FieldViolation;
import com.enrichmeai.culvert.dataquality.ValidationResult;
import com.enrichmeai.culvert.gcp.gcs.FailedRowRecord;

import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.function.Function;
import java.util.stream.Collectors;

/**
 * Bridges {@link ValidationResult.InvalidRow} (core dataquality) to
 * {@link FailedRowRecord} (gcp-gcs) so invalid rows can flow into
 * {@link com.enrichmeai.culvert.gcp.gcs.QuarantineHandler#writeFailures}.
 *
 * <p>Mirrors {@code deployments/reference-e2e-gcp}'s
 * {@code com.enrichmeai.culvert.e2e.dq.InvalidRowAdapter} (T14.5, issue #82) —
 * that class lives under {@code reference-e2e-gcp}'s own package and is not a
 * published artifact, so this deployment carries its own copy rather than
 * introducing a cross-deployment dependency (deployments are standalone Maven
 * projects, not part of the reactor; see the pom.xml header).
 */
final class InvalidRowAdapter {

    private InvalidRowAdapter() {
        // utility class
    }

    static <R> FailedRowRecord adapt(
            ValidationResult.InvalidRow<R> invalidRow,
            Function<R, Map<String, Object>> rowToMap) {

        Objects.requireNonNull(invalidRow, "invalidRow must not be null");
        Objects.requireNonNull(rowToMap, "rowToMap must not be null");

        Map<String, Object> content = rowToMap.apply(invalidRow.row());
        List<ViolationDescriptorImpl> vds = invalidRow.violations().stream()
                .map(fv -> new ViolationDescriptorImpl(fv.fieldName(), fv.detail()))
                .collect(Collectors.toUnmodifiableList());

        return new AdaptedFailedRowRecord(content, vds);
    }

    static <R> List<FailedRowRecord> adaptAll(
            List<ValidationResult.InvalidRow<R>> invalidRows,
            Function<R, Map<String, Object>> rowToMap) {

        Objects.requireNonNull(invalidRows, "invalidRows must not be null");
        Objects.requireNonNull(rowToMap, "rowToMap must not be null");

        return invalidRows.stream()
                .map(inv -> adapt(inv, rowToMap))
                .collect(Collectors.toUnmodifiableList());
    }

    private static final class AdaptedFailedRowRecord implements FailedRowRecord {

        private final Map<String, Object> content;
        private final List<ViolationDescriptorImpl> vds;

        AdaptedFailedRowRecord(Map<String, Object> content, List<ViolationDescriptorImpl> vds) {
            this.content = content;
            this.vds = vds;
        }

        @Override
        public Map<String, Object> rowContent() {
            return content;
        }

        @Override
        public List<? extends FailedRowRecord.ViolationDescriptor> violations() {
            return vds;
        }
    }

    private record ViolationDescriptorImpl(String field, String rule)
            implements FailedRowRecord.ViolationDescriptor {
    }
}
