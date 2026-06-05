package com.enrichmeai.culvert.gcp.gcs;

import java.util.List;
import java.util.Map;

/**
 * Minimal seam that {@link QuarantineHandler} depends on instead of the
 * concrete {@code InvalidRow} from T14.1 (which does not exist on this
 * branch yet).
 *
 * <p><strong>T14.5 wiring note:</strong> T14.1's {@code InvalidRow} must
 * either implement this interface or be adapted to it by the E2E slice
 * (T14.5) before passing to {@link QuarantineHandler#writeFailures}. No
 * core edits are required — the adapter lives in the calling code.
 *
 * <p>Two accessors are all the handler needs:
 * <ul>
 *   <li>{@link #rowContent()} — the raw field values, serialised as a JSON
 *       object in the quarantine file so the row is fully self-describing.
 *   <li>{@link #violations()} — ordered list of violation descriptors;
 *       each carries a field name and a human-readable rule message.
 * </ul>
 *
 * <p>Sprint-14 / issue #74 (T14.2).
 */
public interface FailedRowRecord {

    /**
     * The raw field values for the failed row.
     *
     * @return a non-null map of column name → value (value may be null for
     *         genuinely missing fields). Must not be modified by callers.
     */
    Map<String, Object> rowContent();

    /**
     * Ordered list of rule violations that caused this row to fail
     * validation.
     *
     * @return non-null, may be empty (if the row failed for a non-field
     *         reason, e.g. a row-level schema mismatch).
     */
    List<? extends ViolationDescriptor> violations();

    // ---- Nested seam interface ----

    /**
     * Minimal view of a single field violation. Maps cleanly to T14.1's
     * {@code FieldViolation} — T14.5 wires them by implementing this
     * interface there (or via a one-line lambda/record adapter).
     */
    interface ViolationDescriptor {

        /**
         * Name of the field that failed validation, or {@code "_row"} for a
         * row-level violation not tied to a specific field.
         */
        String field();

        /**
         * Human-readable description of the violated rule, e.g.
         * {@code "must not be null"} or {@code "value exceeds max length 255"}.
         */
        String rule();
    }
}
