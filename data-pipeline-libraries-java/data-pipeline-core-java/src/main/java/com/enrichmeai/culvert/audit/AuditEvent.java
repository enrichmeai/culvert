package com.enrichmeai.culvert.audit;

import java.time.Instant;
import java.time.LocalDate;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;

/**
 * One row of {@code job_control.audit_events} — {@code docs/CONTRACT.md} §4.
 *
 * <p>Replaces {@code AuditRecord}, which modelled a <em>stage summary</em>
 * (eleven fields: durations, success flags, hashes) while the contract
 * specifies an <em>event</em>. The two shared exactly one column, {@code run_id},
 * so this is a different unit of emission rather than a field rename — which is
 * why there is no adapter between them.
 *
 * <h2>What this type guarantees</h2>
 * <ul>
 *   <li>{@code contract_version} is stamped here, from {@link ContractVersion},
 *       so no emitter can forget it or drift.</li>
 *   <li>Required payload keys for the {@link EventKind} are present at
 *       construction. §10.3 forbids extra columns on a well-known table, so
 *       everything past §4's ten columns lives in {@code payload} — and an
 *       unbound payload is the largest divergence surface in this design. A
 *       missing key fails <strong>here</strong>, loudly, rather than reading
 *       back as {@code NULL} at query time.</li>
 *   <li>{@code payload} is copied and unmodifiable, so an event cannot be
 *       mutated after the decision to emit it.</li>
 * </ul>
 *
 * <p>Java mirror of the Python {@code AuditEvent} dataclass.
 *
 * @param runId           Pipeline execution id (§7 format). Never reused across runs.
 * @param systemId        Source system, e.g. {@code Generic}.
 * @param entity          Entity name, e.g. {@code customers}. Required on every
 *                        event: {@code getEntityStatus} reports per system+date
 *                        and cannot be derived from per-run aggregates.
 * @param eventKind       Which event this is.
 * @param eventTs         UTC instant the event occurred; the partition column.
 * @param extractDate     Business date the source covers, from the HDR record.
 * @param payload         Event-specific detail. Must carry
 *                        {@link EventKind#requiredPayloadKeys()}.
 * @param producer        Emitter name and version, e.g. {@code culvert@0.2.0}.
 * @param environment     Deployment environment, e.g. {@code int}.
 * @param contractVersion Always {@link ContractVersion#CURRENT}; not caller-supplied.
 */
public record AuditEvent(
        String runId,
        String systemId,
        String entity,
        EventKind eventKind,
        Instant eventTs,
        Optional<LocalDate> extractDate,
        Map<String, Object> payload,
        Optional<String> producer,
        Optional<String> environment,
        String contractVersion) {

    public AuditEvent {
        Objects.requireNonNull(runId, "runId must not be null");
        Objects.requireNonNull(systemId, "systemId must not be null");
        Objects.requireNonNull(entity, "entity must not be null");
        Objects.requireNonNull(eventKind, "eventKind must not be null");
        Objects.requireNonNull(eventTs, "eventTs must not be null");
        Objects.requireNonNull(extractDate, "extractDate must not be null (use Optional.empty())");
        Objects.requireNonNull(payload, "payload must not be null (use Map.of())");
        Objects.requireNonNull(producer, "producer must not be null (use Optional.empty())");
        Objects.requireNonNull(environment, "environment must not be null (use Optional.empty())");
        Objects.requireNonNull(contractVersion, "contractVersion must not be null");

        if (runId.isBlank()) {
            throw new IllegalArgumentException("runId must not be blank");
        }
        if (entity.isBlank()) {
            throw new IllegalArgumentException("entity must not be blank");
        }

        payload = Collections.unmodifiableMap(new LinkedHashMap<>(payload));

        // Fail at construction, not at read time. A missing key would otherwise
        // surface as a NULL from a JSON path months later, in a query nobody
        // thinks to distrust.
        for (String required : eventKind.requiredPayloadKeys()) {
            if (!payload.containsKey(required)) {
                throw new IllegalArgumentException(
                        eventKind + " requires payload key '" + required + "'; got "
                                + payload.keySet() + ". See docs/CONTRACT.md §4.");
            }
        }
    }

    /**
     * Build an event, stamping {@code contract_version} from the one constant.
     *
     * <p>The only supported way to create one — the canonical constructor takes
     * the version so deserialisation can round-trip a foreign producer's row,
     * but emitters must not choose it.
     */
    public static AuditEvent of(String runId,
                                String systemId,
                                String entity,
                                EventKind eventKind,
                                Instant eventTs,
                                Map<String, Object> payload) {
        return new AuditEvent(runId, systemId, entity, eventKind, eventTs,
                Optional.empty(), payload, Optional.empty(), Optional.empty(),
                ContractVersion.CURRENT);
    }

    /** Same, with the business date, producer and environment supplied. */
    public static AuditEvent of(String runId,
                                String systemId,
                                String entity,
                                EventKind eventKind,
                                Instant eventTs,
                                Map<String, Object> payload,
                                LocalDate extractDate,
                                String producer,
                                String environment) {
        return new AuditEvent(runId, systemId, entity, eventKind, eventTs,
                Optional.ofNullable(extractDate), payload,
                Optional.ofNullable(producer), Optional.ofNullable(environment),
                ContractVersion.CURRENT);
    }

    /**
     * True if a failed append of this event must fail the pipeline.
     *
     * <p>Delegates to {@link EventKind#isRunLevel()} so the rule lives with the
     * kind rather than being restated in every emitter — restating it is how
     * two emitters end up disagreeing about which failures matter.
     */
    public boolean failureIsFatal() {
        return eventKind.isRunLevel();
    }
}
