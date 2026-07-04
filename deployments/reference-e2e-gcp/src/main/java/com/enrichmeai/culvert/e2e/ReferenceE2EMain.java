package com.enrichmeai.culvert.e2e;

import com.enrichmeai.culvert.contracts.PipelineStage;
import com.enrichmeai.culvert.contracts.RuntimeContext;
import com.enrichmeai.culvert.gcp.dataflow.DataflowPipeline;
import com.enrichmeai.culvert.runtime.DefaultRuntimeContext;
import org.apache.beam.runners.dataflow.options.DataflowPipelineOptions;
import org.apache.beam.runners.direct.DirectRunner;
import org.apache.beam.sdk.PipelineResult;
import org.apache.beam.sdk.options.PipelineOptions;
import org.apache.beam.sdk.options.PipelineOptionsFactory;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.security.SecureRandom;
import java.time.Instant;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Launcher for the reference end-to-end pipeline — the framework's deployable
 * smoke test and benchmark (closes the long-standing Sprint-16 gap: the e2e
 * slices previously existed only as JUnit/DirectRunner tests and could not be
 * submitted to real Dataflow).
 *
 * <p>Runs the same two-stage skeleton the e2e test slices exercise
 * ({@link NoOpReadStage} {@code >>} {@link NoOpTransformStage}) — deliberately
 * declared out of dependency order so the topological sort is exercised — but
 * as a submittable job. On the {@code dataflow} runner this proves, on real
 * workers, exactly the seams DirectRunner cannot: job submission, the
 * {@code StageTransform} DoFn serialization boundary (T10.6), worker-side
 * context rebuild, and the observability/FinOps emission path under real
 * latency. Wall-clock timing is printed for use as a release-over-release
 * benchmark baseline.
 *
 * <h2>Usage</h2>
 * <pre>
 *   # Local smoke (no cloud, no cost):
 *   java -cp ... com.enrichmeai.culvert.e2e.ReferenceE2EMain --runner=direct
 *
 *   # Real Dataflow (requires project + staging bucket; incurs cost):
 *   java -cp ... com.enrichmeai.culvert.e2e.ReferenceE2EMain \
 *       --runner=dataflow --project=MY_PROJECT --region=europe-west2 \
 *       --tempLocation=gs://MY_BUCKET/temp
 * </pre>
 *
 * <p>Exit code 0 on {@code DONE}, 1 on any other terminal state or error.
 */
public final class ReferenceE2EMain {

    private static final Logger LOG = LoggerFactory.getLogger(ReferenceE2EMain.class);

    private static final DateTimeFormatter RUN_ID_TS =
            DateTimeFormatter.ofPattern("yyyyMMdd'T'HHmmss'Z'").withZone(ZoneOffset.UTC);

    private ReferenceE2EMain() {
    }

    public static void main(String[] args) {
        Map<String, String> opts = parseArgs(args);
        String runner = opts.getOrDefault("runner", "direct");
        String environment = opts.getOrDefault("environment", "e2e");
        String runId = generateRunId();

        PipelineStage read = new NoOpReadStage();
        PipelineStage transform = new NoOpTransformStage();
        // Out of dependency order on purpose — exercises the topological sort.
        DataflowPipeline pipeline = new DataflowPipeline(
                "reference-e2e-gcp", List.of(transform, read));
        pipeline.validate();

        RuntimeContext context = DefaultRuntimeContext
                .builder(runId, environment)
                .config(Map.of("deployment", "reference-e2e-gcp", "runner", runner))
                .build();

        LOG.info("reference-e2e-gcp starting: run_id={} runner={} environment={}",
                runId, runner, environment);
        long startMillis = System.currentTimeMillis();

        PipelineResult.State state;
        try {
            state = switch (runner) {
                case "direct" -> runDirect(pipeline, context);
                case "dataflow" -> runDataflow(pipeline, context, opts);
                default -> throw new IllegalArgumentException(
                        "unknown --runner=" + runner + " (expected direct|dataflow)");
            };
        } catch (RuntimeException e) {
            LOG.error("reference-e2e-gcp FAILED: run_id={} error={}", runId, e.getMessage(), e);
            System.exit(1);
            return; // unreachable; keeps the compiler happy about 'state'
        }

        long elapsedMillis = System.currentTimeMillis() - startMillis;
        LOG.info("reference-e2e-gcp finished: run_id={} state={} wall_clock_ms={}",
                runId, state, elapsedMillis);
        System.exit(state == PipelineResult.State.DONE ? 0 : 1);
    }

    private static PipelineResult.State runDirect(DataflowPipeline pipeline, RuntimeContext context) {
        PipelineOptions options = PipelineOptionsFactory.create();
        options.setRunner(DirectRunner.class);
        return pipeline.buildBeam(options, context).run().waitUntilFinish();
    }

    private static PipelineResult.State runDataflow(DataflowPipeline pipeline, RuntimeContext context,
                                                    Map<String, String> opts) {
        String project = require(opts, "project");
        String region = require(opts, "region");
        String tempLocation = require(opts, "tempLocation");

        DataflowPipelineOptions options =
                PipelineOptionsFactory.create().as(DataflowPipelineOptions.class);
        options.setProject(project);
        options.setRegion(region);
        options.setTempLocation(tempLocation);
        options.setJobName("reference-e2e-gcp-" + context.runId().toLowerCase().replace(':', '-'));
        return pipeline.runOnDataflow(options, context).waitUntilFinish();
    }

    // --- helpers ------------------------------------------------------------

    /** Wire-format run id: {@code yyyyMMdd'T'HHmmss'Z'-<4 hex>} (docs/CONTRACT.md). */
    static String generateRunId() {
        byte[] suffix = new byte[2];
        new SecureRandom().nextBytes(suffix);
        return RUN_ID_TS.format(Instant.now()) + String.format("-%02x%02x", suffix[0], suffix[1]);
    }

    /** Parses {@code --key=value} args; bare {@code --key} becomes {@code "true"}. */
    static Map<String, String> parseArgs(String[] args) {
        Map<String, String> parsed = new HashMap<>();
        for (String arg : args) {
            if (!arg.startsWith("--")) {
                throw new IllegalArgumentException("unexpected argument: " + arg);
            }
            String body = arg.substring(2);
            int eq = body.indexOf('=');
            if (eq < 0) {
                parsed.put(body, "true");
            } else {
                parsed.put(body.substring(0, eq), body.substring(eq + 1));
            }
        }
        return parsed;
    }

    private static String require(Map<String, String> opts, String key) {
        String value = opts.get(key);
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(
                    "--" + key + " is required for --runner=dataflow");
        }
        return value;
    }
}
