package com.enrichmeai.culvert;

import com.enrichmeai.culvert.audit.AuditRecord;
import com.enrichmeai.culvert.finops.CostMetrics;
import com.enrichmeai.culvert.finops.FinOpsTag;
import com.enrichmeai.culvert.governance.DataClassification;
import com.enrichmeai.culvert.governance.MaskingPolicy;
import com.enrichmeai.culvert.governance.MaskingStrategy;
import com.enrichmeai.culvert.governance.RetentionPolicy;
import com.enrichmeai.culvert.jobcontrol.JobStatus;
import com.enrichmeai.culvert.jobcontrol.JobType;
import com.enrichmeai.culvert.jobcontrol.PipelineJob;
import com.enrichmeai.culvert.lineage.LineageAudit;
import com.enrichmeai.culvert.lineage.LineageDestination;
import com.enrichmeai.culvert.lineage.LineageEvent;
import com.enrichmeai.culvert.lineage.LineagePipeline;
import com.enrichmeai.culvert.lineage.LineageSource;
import com.enrichmeai.culvert.schema.EntitySchema;
import com.enrichmeai.culvert.schema.SchemaField;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.time.LocalDate;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * Smoke test for the supporting records and enums.
 *
 * <p>Mirror of the Python {@code tests/test_supporting_types.py}. Verifies
 * minimal construction, defaults, and the convenience factories.
 */
class SupportingTypesTest {

    @Test
    void pipeline_job_minimal_construction_via_builder() {
        PipelineJob job = PipelineJob.builder(
                "run-1", "retail", "customer_fdp",
                LocalDate.of(2026, 5, 26), JobStatus.CREATED).build();
        assertThat(job.jobType()).isEqualTo(JobType.INGESTION);
        assertThat(job.retryCount()).isZero();
        assertThat(job.entityType()).isEmpty();
        assertThat(job.failureStage()).isEmpty();
    }

    @Test
    void audit_record_minimal_construction_via_builder() {
        AuditRecord record = AuditRecord.builder()
                .runId("run-1")
                .pipelineName("customer_fdp")
                .entityType("customer")
                .sourceFile("gs://b/p")
                .recordCount(42)
                .processedTimestamp(Instant.now())
                .processingDurationSeconds(1.5)
                .success(true)
                .build();
        assertThat(record.errorCount()).isZero();
        assertThat(record.auditHash()).isEmpty();
        assertThat(record.metadata()).isEmpty();
    }

    @Test
    void cost_metrics_zero_factory() {
        CostMetrics m = CostMetrics.zero("run-1");
        assertThat(m.runId()).isEqualTo("run-1");
        assertThat(m.estimatedCostUsd()).isZero();
        assertThat(m.labels()).isEmpty();
    }

    @Test
    void finops_tag_of_factory() {
        FinOpsTag tag = FinOpsTag.of("retail", "prod", "cc1", "data-platform", "run-1");
        assertThat(tag.extra()).isEmpty();
    }

    @Test
    void masking_policy_defaults() {
        MaskingPolicy p = MaskingPolicy.of(MaskingStrategy.PARTIAL);
        assertThat(p.replacement()).isEqualTo("*");
        assertThat(p.salt()).isEmpty();
    }

    @Test
    void masking_strategy_values_match_python_enum() {
        // These string values are the wire format. Both Java and Python must
        // serialise the same strings, otherwise cross-language audit records
        // and metrics won't deserialise.
        assertThat(MaskingStrategy.FULL.getValue()).isEqualTo("full");
        assertThat(MaskingStrategy.PARTIAL.getValue()).isEqualTo("partial");
        assertThat(MaskingStrategy.REDACTED.getValue()).isEqualTo("redacted");
        assertThat(MaskingStrategy.HASH.getValue()).isEqualTo("hash");
        assertThat(MaskingStrategy.NONE.getValue()).isEqualTo("none");
    }

    @Test
    void retention_policy_of_days_factory() {
        RetentionPolicy r = RetentionPolicy.ofDays(2555);
        assertThat(r.legalHold()).isFalse();
        assertThat(r.purpose()).isEmpty();
    }

    @Test
    void retention_policy_rejects_negative_days() {
        assertThatThrownBy(() -> RetentionPolicy.ofDays(-1))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void data_classification_string_values() {
        assertThat(DataClassification.PUBLIC.getValue()).isEqualTo("public");
        assertThat(DataClassification.RESTRICTED.getValue()).isEqualTo("restricted");
    }

    @Test
    void entity_schema_construction() {
        EntitySchema s = EntitySchema.of("customer", List.of(
                SchemaField.required("id", "STRING"),
                new SchemaField("email", "STRING", "NULLABLE",
                        Optional.empty(),
                        Optional.of(DataClassification.RESTRICTED),
                        Optional.empty())));
        assertThat(s.version()).isEqualTo("1");
        assertThat(s.fields()).hasSize(2);
        assertThat(s.fields().get(1).classification()).contains(DataClassification.RESTRICTED);
    }

    @Test
    void lineage_event_builder_and_access() {
        LineageEvent e = LineageEvent.builder()
                .source(LineageSource.of("file", "gs://b/p"))
                .pipeline(new LineagePipeline("run-1", "customer_fdp", "ingest",
                        Optional.empty(), Optional.empty()))
                .destination(LineageDestination.of("table", "bigquery://x.y.z"))
                .audit(new LineageAudit(10, 10, 0, "hash"))
                .build();
        assertThat(e.pipeline()).isPresent();
        assertThat(e.pipeline().orElseThrow().runId()).isEqualTo("run-1");
        assertThat(e.audit().orElseThrow().recordCountSource()).isEqualTo(10);
    }

    @Test
    void cost_metrics_builder_pattern() {
        CostMetrics m = CostMetrics.builder("run-1")
                .estimatedCostUsd(0.42)
                .billedBytesScanned(1024)
                .slotMillis(500)
                .labels(Map.of("system", "retail"))
                .build();
        assertThat(m.estimatedCostUsd()).isEqualTo(0.42);
        assertThat(m.billedBytesScanned()).isEqualTo(1024);
        assertThat(m.slotMillis()).isEqualTo(500);
        assertThat(m.labels()).containsEntry("system", "retail");
    }
}
