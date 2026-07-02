package com.enrichmeai.culvert.deployments.ingestion;

import com.enrichmeai.culvert.contracts.BlobStore;
import com.enrichmeai.culvert.contracts.JobControlRepository;
import com.enrichmeai.culvert.contracts.RuntimeContext;
import com.enrichmeai.culvert.contracts.Warehouse;
import com.enrichmeai.culvert.deployments.ingestion.stages.IngestionStage;
import com.enrichmeai.culvert.gcp.bigquery.BigQueryJobControlRepository;
import com.enrichmeai.culvert.gcp.bigquery.BigQueryWarehouse;
import com.enrichmeai.culvert.gcp.dataflow.DataflowPipeline;
import com.enrichmeai.culvert.gcp.gcs.GcsBlobStore;
import com.enrichmeai.culvert.runtime.DefaultRuntimeContext;
import com.google.cloud.bigquery.BigQuery;
import com.google.cloud.bigquery.BigQueryOptions;
import org.apache.beam.runners.dataflow.options.DataflowPipelineOptions;
import org.apache.beam.runners.direct.DirectRunner;
import org.apache.beam.sdk.PipelineResult;
import org.apache.beam.sdk.options.PipelineOptions;
import org.apache.beam.sdk.options.PipelineOptionsFactory;

import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

/**
 * CLI launcher for the {@code original-data-to-bigqueryload} Java deployment.
 *
 * <p>Wires real GCP adapters ({@link GcsBlobStore}, {@link BigQueryWarehouse},
 * {@link BigQueryJobControlRepository}) onto a {@link DefaultRuntimeContext},
 * builds the single-stage {@link IngestionPipelines#of pipeline}, and runs it
 * either on Beam's {@link DirectRunner} (local) or on Cloud Dataflow
 * ({@code --runner=DataflowRunner}), mirroring the Python reference's
 * {@code python -m data_ingestion.pipeline.run --entity=... --source_file=...}
 * entry point
 * ({@code deployments/original-data-to-bigqueryload/src/data_ingestion/pipeline/runner.py}).
 *
 * <h2>Args</h2>
 * <pre>
 *   --entity=customers|accounts|decision|applications   (required)
 *   --sourceUri=gs://bucket/path/to/file.csv             (required)
 *   --extractDate=yyyyMMdd                               (required)
 *   --project=my-gcp-project                             (required)
 *   --targetTable=dataset.table  (or project.dataset.table)   (required)
 *   --stagingPathPrefix=gs://bucket/staging               (required)
 *   --errorPathPrefix=gs://bucket/errors                  (required)
 *   --jobControlDataset=job_control                       (default: job_control)
 *   --jobControlTable=pipeline_jobs                       (default: pipeline_jobs)
 *   --runId=my-run-id                     (default: generated)
 *   --runner=DirectRunner|DataflowRunner   (default: DirectRunner)
 *   --region=us-central1                   (DataflowRunner only)
 *   --stagingLocation=gs://bucket/dataflow-staging  (DataflowRunner only)
 * </pre>
 *
 * <p><strong>Honest status:</strong> the {@link DirectRunner} path and the unit
 * tests exercise the full ingestion flow in-process against real or in-memory
 * adapters. The {@code DataflowRunner} path has not been run against live GCP
 * as part of T20.5 — see the deployment README "Known gaps" section.
 */
public final class IngestionMain {

    private IngestionMain() {
        // CLI entry point — no instances
    }

    public static void main(String[] args) {
        Map<String, String> argMap = parseArgs(args);

        String entity = require(argMap, "entity");
        String sourceUri = require(argMap, "sourceUri");
        String extractDate = require(argMap, "extractDate");
        String project = require(argMap, "project");
        String targetTable = require(argMap, "targetTable");
        String stagingPathPrefix = require(argMap, "stagingPathPrefix");
        String errorPathPrefix = require(argMap, "errorPathPrefix");
        String jobControlDataset = argMap.getOrDefault("jobControlDataset", "job_control");
        String jobControlTable = argMap.getOrDefault("jobControlTable", "pipeline_jobs");
        String runId = argMap.getOrDefault("runId", "generic-" + entity + "-" + UUID.randomUUID());
        String runner = argMap.getOrDefault("runner", "DirectRunner");

        BigQuery bigQuery = BigQueryOptions.getDefaultInstance().getService();

        BlobStore blobStore = new GcsBlobStore();
        Warehouse warehouse = new BigQueryWarehouse(project, bigQuery);
        JobControlRepository jobControlRepository =
                new BigQueryJobControlRepository(bigQuery, project, jobControlDataset, jobControlTable);

        RuntimeContext context = DefaultRuntimeContext.builder(runId, argMap.getOrDefault("environment", "dev"))
                .config(Map.of("entity", entity, "project", project))
                .register(BlobStore.class, blobStore)
                .register(Warehouse.class, warehouse)
                .register(JobControlRepository.class, jobControlRepository)
                .build();

        IngestionStage stage = new IngestionStage(
                runId, entity, sourceUri, extractDate, targetTable, stagingPathPrefix, errorPathPrefix);
        DataflowPipeline pipeline = IngestionPipelines.of(stage);
        pipeline.validate();

        if ("DataflowRunner".equalsIgnoreCase(runner)) {
            DataflowPipelineOptions options = PipelineOptionsFactory.as(DataflowPipelineOptions.class);
            options.setProject(project);
            options.setRegion(argMap.get("region"));
            options.setStagingLocation(argMap.get("stagingLocation"));
            PipelineResult result = pipeline.runOnDataflow(options, context);
            result.waitUntilFinish();
        } else {
            PipelineOptions options = PipelineOptionsFactory.create();
            options.setRunner(DirectRunner.class);
            org.apache.beam.sdk.Pipeline beam = pipeline.buildBeam(options, context);
            beam.run().waitUntilFinish();
        }
    }

    private static Map<String, String> parseArgs(String[] args) {
        Map<String, String> map = new HashMap<>();
        for (String arg : args) {
            if (!arg.startsWith("--")) {
                continue;
            }
            String stripped = arg.substring(2);
            int eq = stripped.indexOf('=');
            if (eq < 0) {
                map.put(stripped, "true");
            } else {
                map.put(stripped.substring(0, eq), stripped.substring(eq + 1));
            }
        }
        return map;
    }

    private static String require(Map<String, String> args, String key) {
        String value = args.get(key);
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException("Missing required argument: --" + key);
        }
        return value;
    }
}
