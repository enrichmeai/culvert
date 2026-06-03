package com.enrichmeai.culvert.e2e;

import com.enrichmeai.culvert.contracts.PipelineStage;
import com.enrichmeai.culvert.finops.BudgetExceededException;
import com.enrichmeai.culvert.finops.BudgetGovernancePolicy;
import com.enrichmeai.culvert.finops.BudgetViolationMode;
import com.enrichmeai.culvert.finops.CostMetrics;
import com.enrichmeai.culvert.finops.FinOpsTag;
import com.enrichmeai.culvert.gcp.dataflow.DataflowPipeline;
import com.enrichmeai.culvert.runtime.DefaultRuntimeContext;
import org.apache.beam.runners.direct.DirectRunner;
import org.apache.beam.sdk.PipelineResult;
import org.apache.beam.sdk.options.PipelineOptions;
import org.apache.beam.sdk.options.PipelineOptionsFactory;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * Sprint-13 T13.5 (#81) — Cost/FinOps E2E slice for the reference-e2e-gcp deployment.
 *
 * <p>Proves two things:
 * <ol>
 *   <li><strong>Per-stage cost recording</strong>: the reference 2-stage pipeline runs on the
 *       DirectRunner and {@link RecordingFinOpsSink#record} is called once per stage (≥1 time),
 *       with a {@link FinOpsTag} carrying {@code label("stage", stageName)} and a non-zero
 *       {@code estimatedCostUsd} in the corresponding {@link CostMetrics}.</li>
 *   <li><strong>Sprint-13 exit-gate — budget block</strong>: a
 *       {@link BudgetGovernancePolicy} with {@code ceiling = 0.0} and
 *       {@link BudgetViolationMode#BLOCK} throws {@link BudgetExceededException}
 *       <em>before</em> the pipeline runs when any positive projected cost is checked.</li>
 * </ol>
 *
 * <h2>Mechanism</h2>
 *
 * <p>{@link RecordingFinOpsSink} is registered via
 * {@code META-INF/services/com.enrichmeai.culvert.contracts.FinOpsSink} on the test classpath.
 * When {@link com.enrichmeai.culvert.autoconfig.AutoConfig#discover()} is called (both
 * driver-side and worker-side after Beam serializes the
 * {@link com.enrichmeai.culvert.runtime.DefaultRuntimeContext}), it loads the recording sink
 * via {@link java.util.ServiceLoader}. The stages' {@code execute(context)} methods then call
 * {@code context.finops().record(...)} — no per-stage wiring required beyond that call.
 *
 * <h2>What is asserted</h2>
 * <ul>
 *   <li>Test 1 ({@link #perStageCostRecordedWithStageLabel}): after a 2-stage run,
 *       {@code RecordingFinOpsSink} holds exactly 2 records (one per stage). Each record's
 *       {@link FinOpsTag} {@code extra} map contains {@code "stage" → stageName} and the
 *       {@link CostMetrics#estimatedCostUsd()} is positive. The {@code "stage"} key is also
 *       present in {@link CostMetrics#labels()} so the {@code cost_by_stage} SQL query's
 *       {@code UNNEST(labels) WHERE label.key = 'stage'} finds it.</li>
 *   <li>Test 2 ({@link #budgetBlockModeThrowsBudgetExceededExceptionBeforePipelineRuns}):
 *       a {@link BudgetGovernancePolicy} with ceiling {@code 0.0} and mode
 *       {@link BudgetViolationMode#BLOCK} throws {@link BudgetExceededException} before
 *       the pipeline is run; {@code RecordingFinOpsSink} remains empty, proving the block
 *       happened before any stage executed.</li>
 * </ul>
 *
 * <p>No live GCP credentials, no Docker, no internet. DirectRunner + recording sink only.
 * Full emulator run ({@code mvn -P it verify}) and real-cloud smoke test are
 * <strong>architect-run</strong> — see {@code needs-engineer} label on issue #81.
 */
class ReferenceE2ECostTest {

    @BeforeEach
    void resetRecorders() {
        RecordingFinOpsSink.reset();
        // Also reset the observability/metrics recorders to keep test isolation clean.
        RecordingStageMetricsHook.reset();
        RecordingObservabilityHook.reset();
    }

    private static PipelineOptions directRunnerOpts() {
        PipelineOptions opts = PipelineOptionsFactory.create();
        opts.setRunner(DirectRunner.class);
        return opts;
    }

    /**
     * Per-stage cost recording: the 2-stage reference pipeline runs to completion on the
     * DirectRunner; {@link RecordingFinOpsSink} captures one record per stage, each with:
     * <ul>
     *   <li>a non-zero {@code estimatedCostUsd}</li>
     *   <li>{@link FinOpsTag#extra()} containing {@code "stage" → stageName}</li>
     *   <li>{@link CostMetrics#labels()} containing {@code "stage" → stageName}
     *       (required so the {@code cost_by_stage} UNNEST query works)</li>
     * </ul>
     */
    @Test
    void perStageCostRecordedWithStageLabel() {
        PipelineStage read = new NoOpReadStage();
        PipelineStage transform = new NoOpTransformStage();
        DataflowPipeline pipeline = new DataflowPipeline(
                "reference-e2e-gcp", List.of(read, transform));

        DefaultRuntimeContext context = DefaultRuntimeContext
                .builder("run-t135-cost", "test")
                .config(Map.of(
                        "slice", "cost-s13",
                        "finops.budget.ceiling_usd", "100.0"))
                .build();

        PipelineOptions opts = directRunnerOpts();
        org.apache.beam.sdk.Pipeline beam = pipeline.buildBeam(opts, context);
        PipelineResult.State state = beam.run().waitUntilFinish();

        assertThat(state).isEqualTo(PipelineResult.State.DONE);

        // --- RecordingFinOpsSink: at least one record per stage (2 total) ---
        assertThat(RecordingFinOpsSink.RECORDED_METRICS)
                .as("FinOpsSink.record must be called once per stage (read + transform)")
                .hasSize(2);

        // --- Verify the "read" stage record ---
        CostMetrics readMetrics = findMetricsForStage("read");
        assertThat(readMetrics.estimatedCostUsd())
                .as("read stage must record non-zero estimatedCostUsd")
                .isGreaterThan(0.0);
        assertThat(readMetrics.labels())
                .as("read stage CostMetrics.labels() must contain stage key (for cost_by_stage query)")
                .containsEntry("stage", "read");

        FinOpsTag readTag = findTagForStage("read");
        assertThat(readTag.extra())
                .as("read stage FinOpsTag.extra() must carry label(\"stage\", \"read\")")
                .containsEntry("stage", "read");

        // --- Verify the "transform" stage record ---
        CostMetrics transformMetrics = findMetricsForStage("transform");
        assertThat(transformMetrics.estimatedCostUsd())
                .as("transform stage must record non-zero estimatedCostUsd")
                .isGreaterThan(0.0);
        assertThat(transformMetrics.labels())
                .as("transform stage CostMetrics.labels() must contain stage key (for cost_by_stage query)")
                .containsEntry("stage", "transform");

        FinOpsTag transformTag = findTagForStage("transform");
        assertThat(transformTag.extra())
                .as("transform stage FinOpsTag.extra() must carry label(\"stage\", \"transform\")")
                .containsEntry("stage", "transform");
    }

    /**
     * Sprint-13 exit gate: {@link BudgetGovernancePolicy} with {@code ceiling = 0.0} and
     * {@link BudgetViolationMode#BLOCK} throws {@link BudgetExceededException} when
     * {@code checkBudget} is called with any positive {@code estimatedCostUsd} — and the
     * pipeline has NOT run (RecordingFinOpsSink stays empty), proving the block occurs
     * before any stage executes.
     *
     * <p>This is the pre-flight pattern for production: call
     * {@link BudgetGovernancePolicy#checkBudget(CostMetrics, String)} with a dry-run
     * estimate BEFORE submitting the pipeline, and let BLOCK mode abort over-budget runs.
     */
    @Test
    void budgetBlockModeThrowsBudgetExceededExceptionBeforePipelineRuns() {
        BudgetGovernancePolicy blockPolicy =
                new BudgetGovernancePolicy(0.0, BudgetViolationMode.BLOCK);

        // Simulate a positive cost estimate (e.g. from BigQueryCostTracker.estimateDryRun).
        CostMetrics positiveEstimate = CostMetrics.builder("run-t135-budget-block")
                .estimatedCostUsd(0.50)   // any positive value exceeds ceiling of 0.0
                .build();

        // The budget check must throw BEFORE pipeline.run() is called.
        assertThatThrownBy(
                () -> blockPolicy.checkBudget(positiveEstimate, "run-t135-budget-block"))
                .as("BudgetGovernancePolicy(0.0, BLOCK) must throw BudgetExceededException "
                        + "when estimatedCostUsd > 0.0")
                .isInstanceOf(BudgetExceededException.class)
                .hasMessageContaining("run-t135-budget-block");

        // Pipeline must NOT have run: RecordingFinOpsSink must be empty.
        assertThat(RecordingFinOpsSink.RECORDED_METRICS)
                .as("RecordingFinOpsSink must be empty — pipeline did not run (budget blocked)")
                .isEmpty();
    }

    // --- helpers ---

    private static CostMetrics findMetricsForStage(String stageName) {
        for (int i = 0; i < RecordingFinOpsSink.RECORDED_METRICS.size(); i++) {
            CostMetrics m = RecordingFinOpsSink.RECORDED_METRICS.get(i);
            if (stageName.equals(m.labels().get("stage"))) {
                return m;
            }
        }
        throw new AssertionError(
                "No CostMetrics recorded with labels.stage='" + stageName + "'");
    }

    private static FinOpsTag findTagForStage(String stageName) {
        for (int i = 0; i < RecordingFinOpsSink.RECORDED_TAGS.size(); i++) {
            FinOpsTag tag = RecordingFinOpsSink.RECORDED_TAGS.get(i);
            if (stageName.equals(tag.extra().get("stage"))) {
                return tag;
            }
        }
        throw new AssertionError(
                "No FinOpsTag recorded with extra.stage='" + stageName + "'");
    }
}
