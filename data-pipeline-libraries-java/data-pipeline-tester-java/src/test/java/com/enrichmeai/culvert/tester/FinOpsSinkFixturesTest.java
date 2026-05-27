package com.enrichmeai.culvert.tester;

import com.enrichmeai.culvert.finops.CostMetrics;
import com.enrichmeai.culvert.finops.FinOpsTag;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class FinOpsSinkFixturesTest {

    @Test
    void captureSinkRecordsEveryInvocation() {
        FinOpsSinkFixtures.CaptureSink sink = FinOpsSinkFixtures.captureSink();
        FinOpsTag tag = FinOpsTag.of("retail", "dev", "cc-100", "data-eng", "run-1");
        CostMetrics m1 = new CostMetrics("run-1", 1.5, 10L, 20L, 0L, 0L, 0L, 0.0,
                Map.of(), Instant.parse("2026-01-01T00:00:00Z"));
        CostMetrics m2 = new CostMetrics("run-1", 0.5, 5L, 0L, 0L, 0L, 0L, 0.0,
                Map.of(), Instant.parse("2026-01-01T00:01:00Z"));

        sink.record(m1, tag);
        sink.record(m2, tag);

        assertThat(sink.recordCount()).isEqualTo(2);
        assertThat(sink.records()).hasSize(2);
        assertThat(sink.records().get(0).metrics()).isEqualTo(m1);
        assertThat(sink.records().get(0).tags()).isEqualTo(tag);
        assertThat(sink.records().get(1).metrics()).isEqualTo(m2);
    }

    @Test
    void captureSinkClearResetsState() {
        FinOpsSinkFixtures.CaptureSink sink = FinOpsSinkFixtures.captureSink();
        sink.record(CostMetrics.zero("run-1"),
                FinOpsTag.of("retail", "dev", "cc", "owner", "run-1"));
        assertThat(sink.recordCount()).isEqualTo(1);
        sink.clear();
        assertThat(sink.recordCount()).isZero();
    }

    @Test
    void captureSinkRejectsNullArgs() {
        FinOpsSinkFixtures.CaptureSink sink = FinOpsSinkFixtures.captureSink();
        assertThatThrownBy(() -> sink.record(null,
                FinOpsTag.of("retail", "dev", "cc", "owner", "run-1")))
                .isInstanceOf(NullPointerException.class);
        assertThatThrownBy(() -> sink.record(CostMetrics.zero("run-1"), null))
                .isInstanceOf(NullPointerException.class);
    }
}
