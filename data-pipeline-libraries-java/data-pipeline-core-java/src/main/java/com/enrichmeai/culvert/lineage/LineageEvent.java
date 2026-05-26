package com.enrichmeai.culvert.lineage;

import java.util.Optional;

/**
 * OpenLineage-shaped event emitted at a pipeline-stage boundary.
 *
 * <p>Java equivalent of the Python {@code LineageEvent} TypedDict. The four
 * sub-records mirror what the existing Python {@code DataLineageTracker}
 * produces today; Stage 2 will refactor the static
 * {@code generate_data_lineage(audit_record)} method into an instance method
 * that returns this record.
 *
 * <p>All four sub-records are optional because not every stage produces every
 * section (e.g. a streaming source emits no {@code destination} until the
 * first window closes).
 *
 * @param source      The upstream artefact.
 * @param pipeline    The pipeline run.
 * @param destination The downstream artefact.
 * @param audit       Reconciliation summary.
 */
public record LineageEvent(
        Optional<LineageSource> source,
        Optional<LineagePipeline> pipeline,
        Optional<LineageDestination> destination,
        Optional<LineageAudit> audit) {

    public LineageEvent {
        if (source == null) source = Optional.empty();
        if (pipeline == null) pipeline = Optional.empty();
        if (destination == null) destination = Optional.empty();
        if (audit == null) audit = Optional.empty();
    }

    public static Builder builder() {
        return new Builder();
    }

    public static final class Builder {
        private Optional<LineageSource> source = Optional.empty();
        private Optional<LineagePipeline> pipeline = Optional.empty();
        private Optional<LineageDestination> destination = Optional.empty();
        private Optional<LineageAudit> audit = Optional.empty();

        public Builder source(LineageSource v) { this.source = Optional.ofNullable(v); return this; }
        public Builder pipeline(LineagePipeline v) { this.pipeline = Optional.ofNullable(v); return this; }
        public Builder destination(LineageDestination v) { this.destination = Optional.ofNullable(v); return this; }
        public Builder audit(LineageAudit v) { this.audit = Optional.ofNullable(v); return this; }

        public LineageEvent build() {
            return new LineageEvent(source, pipeline, destination, audit);
        }
    }
}
