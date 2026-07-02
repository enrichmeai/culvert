package com.enrichmeai.culvert.deployments.cdcstreaming;

import org.junit.jupiter.api.Test;

import java.util.HashMap;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Unit tests for {@link CdcTransforms}, mirroring the behaviour of
 * {@code TransformToODPDoFn}, {@code TransformToFDPDoFn}, and
 * {@code AddStreamingAuditDoFn} from transforms.py (gcp-pipeline-reference
 * deployments/postgres-cdc-streaming/src/streaming_pipeline/pipeline/transforms.py).
 */
class CdcTransformsTest {

    @Test
    void toOdpStripsNullValuedKeys() {
        Map<String, Object> element = new HashMap<>();
        element.put("customer_id", "C001");
        element.put("email", null);
        element.put("status", "active");

        Map<String, Object> result = CdcTransforms.toOdp(element);

        assertThat(result).containsEntry("customer_id", "C001");
        assertThat(result).containsEntry("status", "active");
        assertThat(result).doesNotContainKey("email");
    }

    @Test
    void addStreamingAuditInjectsRunIdAndProcessedAt() {
        Map<String, Object> element = Map.of("customer_id", "C001");

        Map<String, Object> result = CdcTransforms.addStreamingAudit(element, "run-123");

        assertThat(result).containsEntry("_run_id", "run-123");
        assertThat(result).containsEntry("customer_id", "C001");
        assertThat(result.get("_processed_at")).isNotNull();
    }

    @Test
    void toFdpDerivesFullNameFromFirstAndLastName() {
        Map<String, Object> element = Map.of(
                "customer_id", "C001",
                "first_name", "Jane",
                "last_name", "Smith");

        Map<String, Object> result = CdcTransforms.toFdp(element, true, "2026-01-01T00:00:00Z", "2026-01-01T00:01:00Z");

        assertThat(result).containsEntry("full_name", "Jane Smith");
    }

    @Test
    void toFdpFallsBackToNameFieldWhenFirstLastAbsent() {
        Map<String, Object> element = Map.of("customer_id", "C001", "name", "Bob Lee");

        Map<String, Object> result = CdcTransforms.toFdp(element, true, "2026-01-01T00:00:00Z", "2026-01-01T00:01:00Z");

        assertThat(result).containsEntry("full_name", "Bob Lee");
    }

    @Test
    void toFdpMasksEmailDomainWhenMaskPiiTrue() {
        Map<String, Object> element = Map.of("customer_id", "C001", "email", "jane@example.com");

        Map<String, Object> result = CdcTransforms.toFdp(element, true, "2026-01-01T00:00:00Z", "2026-01-01T00:01:00Z");

        assertThat(result).containsEntry("email_domain", "****");
    }

    @Test
    void toFdpRevealsEmailDomainWhenMaskPiiFalse() {
        Map<String, Object> element = Map.of("customer_id", "C001", "email", "jane@example.com");

        Map<String, Object> result = CdcTransforms.toFdp(element, false, "2026-01-01T00:00:00Z", "2026-01-01T00:01:00Z");

        assertThat(result).containsEntry("email_domain", "example.com");
    }

    @Test
    void toFdpMasksSsnKeepingLastFourDigits() {
        Map<String, Object> element = Map.of("customer_id", "C001", "ssn", "123456789");

        Map<String, Object> result = CdcTransforms.toFdp(element, true, "2026-01-01T00:00:00Z", "2026-01-01T00:01:00Z");

        assertThat(result).containsEntry("ssn_masked", "XXX-XX-6789");
    }

    @Test
    void toFdpHandlesShortSsnGracefully() {
        Map<String, Object> element = Map.of("customer_id", "C001", "ssn", "12");

        Map<String, Object> result = CdcTransforms.toFdp(element, true, "2026-01-01T00:00:00Z", "2026-01-01T00:01:00Z");

        assertThat(result).containsEntry("ssn_masked", "XXX-XX-****");
    }

    @Test
    void toFdpStampsWindowBoundaries() {
        Map<String, Object> element = Map.of("customer_id", "C001");

        Map<String, Object> result = CdcTransforms.toFdp(
                element, true, "2026-01-01T00:00:00Z", "2026-01-01T00:01:00Z");

        assertThat(result).containsEntry("window_start", "2026-01-01T00:00:00Z");
        assertThat(result).containsEntry("window_end", "2026-01-01T00:01:00Z");
    }

    @Test
    void toFdpPreservesCdcMetadata() {
        Map<String, Object> element = Map.of(
                "customer_id", "C001",
                CdcEventParser.FIELD_CDC_OPERATION, "UPDATE",
                CdcEventParser.FIELD_CDC_EVENT_TIME, "2026-01-01T00:00:30Z");

        Map<String, Object> result = CdcTransforms.toFdp(
                element, true, "2026-01-01T00:00:00Z", "2026-01-01T00:01:00Z");

        assertThat(result).containsEntry("cdc_operation", "UPDATE");
        assertThat(result).containsEntry("cdc_event_time", "2026-01-01T00:00:30Z");
    }
}
