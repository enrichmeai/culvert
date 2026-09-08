package com.enrichmeai.culvert.audit;

import java.util.Collections;
import java.util.LinkedHashSet;
import java.util.Set;

/**
 * The kinds of event an audit log carries — {@code docs/CONTRACT.md} §4's
 * {@code event_kind} enum, verbatim.
 *
 * <p>These are not just labels. Reading §4 against {@code JobControlRepository}
 * shows that {@link #RUN_START}, {@link #RUN_END}, {@link #ERROR_RAISED},
 * {@link #RETRY_ATTEMPTED} and {@link #RECONCILIATION} <em>are</em> the
 * job-control lifecycle under different names. Job control and the audit trail
 * were never two things; they were one thing modelled twice, which is how four
 * incompatible shapes for one table name came to exist.
 *
 * <h2>Two things each kind decides</h2>
 * <ol>
 *   <li><strong>What happens when its append fails</strong> — see
 *       {@link #isRunLevel()}. A run-level event <em>is</em> the run's state, so
 *       losing one silently is how a pipeline reports success it never had.</li>
 *   <li><strong>What its payload must contain</strong> — see
 *       {@link #requiredPayloadKeys()}. {@code docs/CONTRACT.md} §10.3 forbids
 *       extra columns in a well-known table, so everything beyond §4's ten
 *       columns lives in {@code payload}. Unbound, two adapters diverge on
 *       {@code markFailed} alone, and a key typo returns {@code NULL} silently
 *       where a typed column would have failed loudly.</li>
 * </ol>
 */
public enum EventKind {

    /** A run began. Carries the source file it will process. */
    RUN_START(true, "source_file"),

    /** A run finished successfully. Carries the count it loaded. */
    RUN_END(true, "record_count"),

    /**
     * Records that passed validation, aggregated for the run and entity.
     *
     * <p>Emitted <strong>once per {@code (run_id, entity)}</strong>, not once
     * per record. Read literally, §4 would have a 5-million-row extract emit
     * five million audit rows — duplicating what quarantine already stores, at
     * real cost per run. The count lives in the payload instead.
     */
    RECORD_VALIDATED(false, "count"),

    /**
     * Records that failed validation, aggregated for the run and entity.
     *
     * <p>Also once per {@code (run_id, entity)}. {@code quarantine_uri} points
     * at the per-row detail, so the audit row stays small and the evidence
     * stays reachable.
     */
    RECORD_REJECTED(false, "count", "quarantine_uri"),

    /**
     * The declared-versus-accounted comparison for a run.
     *
     * <p>{@code reconciled} is the field the projection reads to decide whether
     * a run failed, so it is required rather than inferred from the counts.
     */
    RECONCILIATION(true, "expected_count", "accounted_count", "reconciled"),

    /**
     * A run failed.
     *
     * <p>{@code error_category} is required because §9 mandates classifying
     * every error into {@code validation}/{@code integration}/{@code resource}
     * before deciding whether to retry — a classification that is useless if it
     * is not recorded.
     */
    ERROR_RAISED(true, "error_code", "error_category"),

    /**
     * A retry is about to be attempted.
     *
     * <p>§9 requires emitting this <em>before each</em> retry, capped at three,
     * so up to three legitimately share one {@code run_id}. §7 additionally
     * requires a retried pipeline to take a <strong>new</strong> {@code run_id},
     * recording the previous one here — which is why
     * {@code previous_run_id} is required.
     */
    RETRY_ATTEMPTED(true, "attempt", "previous_run_id");

    private final boolean runLevel;
    private final Set<String> requiredPayloadKeys;

    EventKind(boolean runLevel, String... requiredPayloadKeys) {
        this.runLevel = runLevel;
        this.requiredPayloadKeys =
                Collections.unmodifiableSet(new LinkedHashSet<>(Set.of(requiredPayloadKeys)));
    }

    /**
     * True if this event carries the run's state rather than a counter.
     *
     * <p>Drives the failure rule: a failed append of a run-level event
     * <strong>throws</strong> and fails the pipeline, because proceeding
     * without it is exactly how a run reports success it never had. A failed
     * aggregate append logs at ERROR and dead-letters, so an audit hiccup over
     * a counter cannot halt ingestion.
     *
     * <p>Either way <strong>nothing is swallowed</strong> — the pattern that
     * kept this defect class invisible for months.
     */
    public boolean isRunLevel() {
        return runLevel;
    }

    /**
     * Payload keys this kind must carry.
     *
     * <p>Fixture-pinned and asserted by the conformance suite, so two adapters
     * in two languages cannot drift on key names.
     */
    public Set<String> requiredPayloadKeys() {
        return requiredPayloadKeys;
    }

    /** The wire value written to {@code event_kind}. Uppercase, per §4. */
    public String wireValue() {
        return name();
    }

    /**
     * Parse a wire value, rejecting anything §4 does not define.
     *
     * @throws IllegalArgumentException naming the valid values — this reads
     *                                  rows written by other producers, and a
     *                                  bare enum failure would not say what was
     *                                  expected.
     */
    public static EventKind fromWire(String value) {
        if (value != null) {
            for (EventKind kind : values()) {
                if (kind.name().equals(value)) {
                    return kind;
                }
            }
        }
        StringBuilder valid = new StringBuilder();
        for (EventKind kind : values()) {
            valid.append(valid.length() == 0 ? "" : ", ").append(kind.name());
        }
        throw new IllegalArgumentException(
                "Unknown event_kind '" + value + "'; docs/CONTRACT.md §4 defines: " + valid);
    }
}
