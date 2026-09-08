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
 * <p>Wires the selected cloud's adapter family onto a
 * {@link DefaultRuntimeContext} — GCP (default): {@link GcsBlobStore},
 * {@link BigQueryWarehouse}, {@link BigQueryJobControlRepository}; AWS
 * ({@code --cloud=aws}): {@code S3BlobStore}, {@code AthenaWarehouse},
 * {@code DynamoDbJobControlRepository} — builds the single-stage
 * {@link IngestionPipelines#of pipeline}, and runs it either on Beam's
 * {@link DirectRunner} (local) or on Cloud Dataflow
 * ({@code --runner=DataflowRunner}, GCP).
 *
 * <p><strong>This class is the cloud-agnostic thesis in one file:</strong> the
 * {@code IngestionStage}/{@code IngestionRunner} business logic below the
 * adapter wiring is byte-identical on both clouds. Swapping clouds changes
 * which constructors run in {@code main()} — nothing else.
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
 *
 *   Any other Beam/Dataflow flag is passed through to the runner, e.g.
 *   --tempLocation, --workerZone, --numWorkers, --maxNumWorkers,
 *   --machineType, --subnetwork, --serviceAccount, --usePublicIps.
 *   --cloud=gcp|aws                        (default: gcp — selects the adapter family)
 *   --athenaDatabase=analytics                          (aws only, required)
 *   --athenaOutputLocation=s3://bucket/athena-results/  (aws only, required)
 * </pre>
 *
 * <p><strong>Status:</strong> the {@link DirectRunner} path and the unit tests
 * exercise the full ingestion flow in-process. The {@code DataflowRunner} path
 * was proven against live GCP on 2026-09-08: two consecutive runs of the same
 * extract left <em>three</em> rows in {@code odp_generic.customers}, not six,
 * carrying the second run's {@code _run_id} — the idempotency guarantee, on
 * real BigQuery rather than a test double. Both runs recorded
 * {@code succeeded} in {@code job_control.pipeline_jobs}.
 *
 * <p>That run also needed {@code --workerZone} and {@code --workerMachineType}
 * to route around a zone stockout, which is what exposed that Beam flags were
 * being discarded here; see {@link #buildDataflowOptions}.
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
        String cloud = normalizeCloud(argMap.getOrDefault("cloud", "gcp"));

        // The cloud-agnostic seam in one screenful: the SAME IngestionStage /
        // IngestionRunner / pipeline below runs on either cloud — the only
        // thing that changes is which adapter family gets constructed here.
        BlobStore blobStore;
        Warehouse warehouse;
        JobControlRepository jobControlRepository;
        if ("aws".equals(cloud)) {
            software.amazon.awssdk.services.s3.S3Client s3 =
                    software.amazon.awssdk.services.s3.S3Client.create();
            software.amazon.awssdk.services.athena.AthenaClient athena =
                    software.amazon.awssdk.services.athena.AthenaClient.create();
            software.amazon.awssdk.services.dynamodb.DynamoDbClient dynamo =
                    software.amazon.awssdk.services.dynamodb.DynamoDbClient.create();
            blobStore = new com.enrichmeai.culvert.aws.s3.S3BlobStore(s3);
            warehouse = new com.enrichmeai.culvert.aws.athena.AthenaWarehouse(
                    athena,
                    require(argMap, "athenaDatabase"),
                    require(argMap, "athenaOutputLocation"));
            jobControlRepository = new com.enrichmeai.culvert.aws.dynamodb.DynamoDbJobControlRepository(
                    dynamo, jobControlTable);
        } else {
            BigQuery bigQuery = BigQueryOptions.getDefaultInstance().getService();
            blobStore = new GcsBlobStore();
            warehouse = new BigQueryWarehouse(project, bigQuery);
            jobControlRepository =
                    new BigQueryJobControlRepository(bigQuery, project, jobControlDataset, jobControlTable);
        }

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
            DataflowPipelineOptions options = buildDataflowOptions(args, argMap, project);
            PipelineResult result = pipeline.runOnDataflow(options, context);
            result.waitUntilFinish();
        } else {
            PipelineOptions options = PipelineOptionsFactory.create();
            options.setRunner(DirectRunner.class);
            org.apache.beam.sdk.Pipeline beam = pipeline.buildBeam(options, context);
            beam.run().waitUntilFinish();
        }
    }

    /**
     * Build the Dataflow options, letting Beam's own flags through.
     *
     * <p>This used to be {@code PipelineOptionsFactory.as(...)}, which creates
     * options from nothing and reads no command line at all. Only
     * {@code project}, {@code region} and {@code stagingLocation} were then set
     * by hand, so <strong>every other Beam flag was silently ignored</strong> —
     * {@code --workerZone}, {@code --numWorkers}, {@code --machineType},
     * {@code --subnetwork}, {@code --serviceAccount}, {@code --tempLocation}.
     * The job accepted them on the command line and discarded them, which is
     * the worst of both worlds: no effect and no error.
     *
     * <p>Found on 2026-09-08 trying to run this against real GCP. Dataflow kept
     * placing workers in a zone that was returning
     * {@code ZONE_RESOURCE_POOL_EXHAUSTED}, and there was no way to move them —
     * {@code --workerZone} was accepted and dropped. It also explains the
     * {@code "No tempLocation specified"} warning on a run that passed one, and
     * why a job asked to run in London staged itself to a {@code us-central1}
     * bucket.
     *
     * <p>This matters beyond stockouts: most enterprise estates mandate a
     * specific {@code --subnetwork} and {@code --serviceAccount} for Dataflow
     * workers, and neither could be supplied.
     *
     * <p>{@code withoutStrictParsing()} is required, not incidental: this class
     * defines its own flags ({@code --entity}, {@code --sourceUri}, …) which
     * Beam does not know. Strict parsing would reject them and the job would
     * refuse to start.
     *
     * <p>The three application-owned values are re-applied after parsing so the
     * app's required-argument validation stays authoritative — they come from
     * the same flags, so this changes nothing about them.
     *
     * <p>Package-private so the pass-through is directly testable; exercising
     * it through {@code main} would submit a real Dataflow job.
     */
    static DataflowPipelineOptions buildDataflowOptions(
            String[] args, Map<String, String> argMap, String project) {
        DataflowPipelineOptions options = PipelineOptionsFactory
                .fromArgs(args)
                .withoutStrictParsing()
                .as(DataflowPipelineOptions.class);
        options.setProject(project);
        if (argMap.get("region") != null) {
            options.setRegion(argMap.get("region"));
        }
        if (argMap.get("stagingLocation") != null) {
            options.setStagingLocation(argMap.get("stagingLocation"));
        }
        return options;
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

    /**
     * Normalizes and validates {@code --cloud}. Package-private for tests.
     * Azure is named explicitly so the error message states the roadmap
     * honestly rather than pretending the flag doesn't exist.
     */
    static String normalizeCloud(String cloud) {
        String normalized = cloud == null ? "gcp" : cloud.trim().toLowerCase(java.util.Locale.ROOT);
        switch (normalized) {
            case "gcp":
            case "aws":
                return normalized;
            case "azure":
                throw new IllegalArgumentException(
                        "--cloud=azure is not available yet: the Azure adapter family is a "
                                + "BlobStore-only skeleton (data-pipeline-azure-blob-java). "
                                + "GCP and AWS are supported today; Azure is on the roadmap.");
            default:
                throw new IllegalArgumentException(
                        "Unknown --cloud value '" + cloud + "': supported values are gcp (default) and aws.");
        }
    }
}
