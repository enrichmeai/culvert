package com.enrichmeai.culvert.contracttests;

import com.enrichmeai.culvert.contracts.StageMetrics;
import com.enrichmeai.culvert.contracts.StageMetricsHook;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * Contract tests every {@link StageMetricsHook} implementation must pass.
 *
 * <p>The Java mirror of the Python {@code StageMetricsHookContract}
 * ({@code data_pipeline_contract_tests/stage_metrics_hook.py}), case for case.
 * Each case cites its Python twin's line. The defining guarantee, from the
 * {@link StageMetricsHook} Javadoc, is that a monitoring-backend failure is
 * logged and swallowed, never propagated to the pipeline.
 *
 * <p>Like the Python mixin, the three "accepts" cases check only that a valid
 * snapshot is taken without an exception, so a hook that writes nothing passes
 * them. What each adapter actually sends (the three series and their labels)
 * is checked by its own unit test, because the shape is backend-specific.
 *
 * <p>Subclasses provide:
 * <ul>
 *   <li>{@link #hook()}: the hook, over a backend double that accepts writes;</li>
 *   <li>{@link #failingHook()}: the same implementation, over a backend double
 *       that throws on every write.</li>
 * </ul>
 */
public abstract class StageMetricsHookContractTest {

    protected abstract StageMetricsHook hook();

    protected abstract StageMetricsHook failingHook();

    private static StageMetrics metrics(long rows, double latencyMs, long errors) {
        return new StageMetrics("pipe-1", "run-abc", "my-stage", rows, latencyMs, errors);
    }

    /** Python {@code test_record_stage_metrics_returns_none} (stage_metrics_hook.py:73). */
    @Test
    void recordStageMetricsAcceptsAValidSnapshot() {
        assertThatCode(() -> hook().recordStageMetrics(metrics(100, 42.5, 0)))
                .doesNotThrowAnyException();
    }

    /** Python {@code test_record_stage_metrics_all_fields} (stage_metrics_hook.py:80). */
    @Test
    void recordStageMetricsAcceptsZeroValues() {
        assertThatCode(() -> hook().recordStageMetrics(metrics(0, 0.0, 0)))
                .doesNotThrowAnyException();
    }

    /** Python {@code test_record_stage_metrics_with_errors} (stage_metrics_hook.py:88). */
    @Test
    void recordStageMetricsAcceptsANonZeroErrorCount() {
        assertThatCode(() -> hook().recordStageMetrics(metrics(100, 42.5, 5)))
                .doesNotThrowAnyException();
    }

    /** Python {@code test_backend_failure_is_swallowed} (stage_metrics_hook.py:92). */
    @Test
    void backendFailureIsSwallowed() {
        assertThatCode(() -> failingHook().recordStageMetrics(metrics(100, 42.5, 0)))
                .as("a monitoring outage must not stop the pipeline")
                .doesNotThrowAnyException();
    }

    /** Python {@code test_null_metrics_rejected} (stage_metrics_hook.py:103). */
    @Test
    void nullMetricsRejected() {
        assertThatThrownBy(() -> hook().recordStageMetrics(null))
                .isInstanceOfAny(NullPointerException.class, IllegalArgumentException.class);
    }
}
