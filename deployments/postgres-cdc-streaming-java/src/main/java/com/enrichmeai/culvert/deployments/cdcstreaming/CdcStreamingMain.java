package com.enrichmeai.culvert.deployments.cdcstreaming;

import com.enrichmeai.culvert.autoconfig.AutoConfig;
import com.enrichmeai.culvert.contracts.RuntimeContext;
import com.enrichmeai.culvert.gcp.bigquery.BigQueryWarehouse;
import com.enrichmeai.culvert.gcp.dataflow.DataflowPipeline;
import com.enrichmeai.culvert.gcp.pubsub.PubSubSink;
import com.enrichmeai.culvert.gcp.pubsub.PubSubSource;
import com.enrichmeai.culvert.runtime.DefaultRuntimeContext;
import com.google.cloud.bigquery.BigQuery;
import com.google.cloud.bigquery.BigQueryOptions;
import com.google.cloud.pubsub.v1.Publisher;
import com.google.cloud.pubsub.v1.stub.GrpcSubscriberStub;
import com.google.cloud.pubsub.v1.stub.SubscriberStubSettings;
import com.google.pubsub.v1.ProjectSubscriptionName;
import com.google.pubsub.v1.ProjectTopicName;
import org.apache.beam.runners.dataflow.options.DataflowPipelineOptions;
import org.apache.beam.sdk.options.PipelineOptionsFactory;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * Launcher for the Java Dataflow port of the postgres-cdc-streaming
 * deployment (T20.6, issue #141).
 *
 * <p>Mirrors {@code run_streaming_pipeline()} in the Python reference
 * (deployments/postgres-cdc-streaming/src/streaming_pipeline/pipeline/runner.py:169-346):
 * builds the runtime context, wires the Pub/Sub source + dead-letter sink +
 * BigQuery ODP/FDP warehouses, assembles a two-stage {@link DataflowPipeline}
 * ({@link CdcStreamingStage} → {@link FdpWindowStage}), and submits it to
 * Cloud Dataflow.
 *
 * <h2>Required environment variables</h2>
 * <ul>
 *   <li>{@code GCP_PROJECT} — project ID for Pub/Sub + BigQuery + Dataflow.</li>
 *   <li>{@code GCP_REGION} — Dataflow region.</li>
 *   <li>{@code CDC_SUBSCRIPTION} — fully-qualified Pub/Sub subscription name
 *       for inbound Debezium CDC events (mirrors {@code --kafka_topic},
 *       runner.py:70-74 — despite the flag name, the Python pipeline actually
 *       subscribes to Pub/Sub, runner.py:254-259).</li>
 *   <li>{@code CDC_DEAD_LETTER_TOPIC} — fully-qualified Pub/Sub topic for
 *       invalid/unparseable events.</li>
 *   <li>{@code CDC_ENTITY_NAME} — entity name, e.g. {@code customers}
 *       (mirrors {@code --entity_name}, runner.py:98-101).</li>
 *   <li>{@code CDC_ODP_TABLE} / {@code CDC_FDP_TABLE} — fully-qualified
 *       BigQuery table names (mirrors {@code --odp_dataset}/{@code --fdp_dataset},
 *       runner.py:88-96).</li>
 *   <li>{@code CDC_WINDOW_SECONDS} (optional, default 60) — FDP window size
 *       in seconds (mirrors {@code --window_size_seconds}, runner.py:104-109;
 *       see {@link FdpWindowStage} for the caveat on how this window is
 *       approximated without a true Beam {@code WindowFn}).</li>
 *   <li>{@code GCS_STAGING_LOCATION} / {@code GCS_TEMP_LOCATION} — Dataflow
 *       staging/temp GCS paths.</li>
 * </ul>
 *
 * <p>Run locally against the DirectRunner first (see README.md "How to run")
 * before submitting to Cloud Dataflow — this class always targets Dataflow
 * via {@link DataflowPipeline#runOnDataflow}; use
 * {@link com.enrichmeai.culvert.gcp.dataflow.DataflowPipeline#buildBeam(org.apache.beam.sdk.options.PipelineOptions)}
 * directly with a {@code DirectRunner}-configured {@code PipelineOptions} for
 * local smoke-testing (see the unit tests in this package for that pattern).
 */
public final class CdcStreamingMain {

    private static final Logger LOG = LoggerFactory.getLogger(CdcStreamingMain.class);

    private CdcStreamingMain() {
    }

    public static void main(String[] args) throws Exception {
        String project = requireEnv("GCP_PROJECT");
        String region = requireEnv("GCP_REGION");
        String subscriptionName = requireEnv("CDC_SUBSCRIPTION");
        String deadLetterTopicName = requireEnv("CDC_DEAD_LETTER_TOPIC");
        String entityName = requireEnv("CDC_ENTITY_NAME");
        String odpTable = requireEnv("CDC_ODP_TABLE");
        String fdpTable = requireEnv("CDC_FDP_TABLE");
        String stagingLocation = requireEnv("GCS_STAGING_LOCATION");
        String tempLocation = requireEnv("GCS_TEMP_LOCATION");
        long windowSeconds = Long.parseLong(System.getenv().getOrDefault("CDC_WINDOW_SECONDS", "60"));

        String runId = "stream-" + UUID.randomUUID();
        LOG.info("Starting postgres-cdc-streaming-java: runId={} entity={}", runId, entityName);

        // --- Adapters (mirrors runner.py's WriteToBigQuery / ReadFromPubSub wiring) ---
        GrpcSubscriberStub subscriberStub = GrpcSubscriberStub.create(
                SubscriberStubSettings.newBuilder().build());
        PubSubSource source = new PubSubSource(
                subscriberStub,
                ProjectSubscriptionName.of(project, subscriptionName).toString());

        Publisher deadLetterPublisher = Publisher.newBuilder(
                ProjectTopicName.of(project, deadLetterTopicName)).build();
        PubSubSink deadLetterSink = new PubSubSink(deadLetterPublisher);

        BigQuery bigQueryClient = BigQueryOptions.newBuilder().setProjectId(project).build().getService();
        BigQueryWarehouse warehouse = new BigQueryWarehouse(project, bigQueryClient);

        // --- Pipeline assembly ---
        CdcStreamingStage odpStage = new CdcStreamingStage(
                source, deadLetterSink, warehouse, odpTable, entityName);
        FdpWindowStage fdpStage = new FdpWindowStage(
                warehouse, odpTable, fdpTable, entityName, Duration.ofSeconds(windowSeconds), true);

        DataflowPipeline pipeline = new DataflowPipeline(
                "postgres-cdc-streaming-java-" + entityName, List.of(odpStage, fdpStage));

        RuntimeContext context = DefaultRuntimeContext
                .fromAutoConfig(runId, "prod", Map.of("entity", entityName), AutoConfig.discover());

        DataflowPipelineOptions options = PipelineOptionsFactory
                .as(DataflowPipelineOptions.class);
        options.setProject(project);
        options.setRegion(region);
        options.setStagingLocation(stagingLocation);
        options.setGcpTempLocation(tempLocation);
        options.setStreaming(true);
        options.setJobName("postgres-cdc-streaming-java-" + entityName.toLowerCase());

        pipeline.runOnDataflow(options, context);
    }

    private static String requireEnv(String name) {
        String value = System.getenv(name);
        if (value == null || value.isBlank()) {
            throw new IllegalStateException("Required environment variable not set: " + name);
        }
        return value;
    }
}
