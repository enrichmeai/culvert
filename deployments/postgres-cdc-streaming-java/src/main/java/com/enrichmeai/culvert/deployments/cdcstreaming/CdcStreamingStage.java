package com.enrichmeai.culvert.deployments.cdcstreaming;

import com.enrichmeai.culvert.contracts.PipelineStage;
import com.enrichmeai.culvert.contracts.RuntimeContext;
import com.enrichmeai.culvert.contracts.Sink;
import com.enrichmeai.culvert.contracts.Source;
import com.enrichmeai.culvert.contracts.Warehouse;
import com.google.pubsub.v1.PubsubMessage;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.Serializable;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;

/**
 * The single Culvert {@link PipelineStage} that ports the Python reference
 * pipeline's read → parse → ODP-write → dead-letter flow (gcp-pipeline-reference
 * deployments/postgres-cdc-streaming/src/streaming_pipeline/pipeline/runner.py:249-283,
 * the {@code ReadFromPubSub → ParseCDCEvent → FilterValid → TransformToODP →
 * AddAuditColumns → WriteToODP} chain).
 *
 * <h2>Why one stage, not five</h2>
 *
 * <p>Culvert's current {@code StageTransform}/{@code DataflowPipeline} bridge
 * (data-pipeline-libraries-java/data-pipeline-gcp-dataflow-java/src/main/java/com/enrichmeai/culvert/gcp/dataflow/StageTransform.java:20-38)
 * triggers each {@link PipelineStage#execute(RuntimeContext)} exactly once
 * per pipeline run, rooted at {@code PBegin} — it does not translate a stage
 * into an element-level {@code PCollection} transform. Splitting
 * read/parse/write into five separate {@code PipelineStage}s would not
 * produce a fused, per-record Beam DAG the way the Python
 * {@code beam.ParDo} chain does; it would just add stage-to-stage plumbing
 * with no corresponding execution benefit today. See README.md
 * "Streaming semantics caveats" for the full explanation and the path to
 * true element-level translation.
 *
 * <p>This stage therefore does the full pull-parse-write-dead-letter cycle
 * for one batch per {@code execute()} call, using the {@link Source}/
 * {@link Sink}/{@link Warehouse} contract adapters directly (constructor
 * injection), while still being a valid, testable {@link PipelineStage} that
 * {@link com.enrichmeai.culvert.gcp.dataflow.DataflowPipeline} can drive on
 * Dataflow. A production deployment runs it repeatedly (e.g. wrapped in a
 * polling loop or a Beam {@code GenerateSequence} + trigger — see
 * {@link CdcStreamingMain} for the launcher wiring notes).
 *
 * <h2>ODP write semantics ("streaming upsert")</h2>
 *
 * <p>The Python pipeline uses {@code WriteToBigQuery(method="STREAMING_INSERTS",
 * write_disposition=WRITE_APPEND)} (runner.py:277-283) — an append-only
 * streaming-insert sink; it does not do a true upsert/merge (Debezium
 * UPDATE/DELETE events are appended as new rows carrying
 * {@code _cdc_operation}, and de-duplication/point-in-time reconciliation is
 * left to a downstream MERGE or view). This port preserves that behaviour
 * using {@link Warehouse#execute(String, Map)} with a parameterised
 * multi-row {@code INSERT}, since {@link Warehouse} has no dedicated
 * streaming-insert method and {@link Warehouse#merge} is explicitly
 * unimplemented on this branch
 * (data-pipeline-libraries-java/data-pipeline-gcp-bigquery-java/src/main/java/com/enrichmeai/culvert/gcp/bigquery/BigQueryWarehouse.java:150-168,
 * throws {@code UnsupportedOperationException}). See README.md for the flagged gap.
 *
 * <h2>Dead-letter routing</h2>
 *
 * <p>Mirrors the Python parser's "drop silently, log, count" behaviour
 * (cdc_parser.py:124-131) but additionally publishes the raw offending
 * payload to a Pub/Sub dead-letter topic via {@link Sink}, since a
 * standalone Java Dataflow job has no Beam {@code DirectRunner} test harness
 * to inspect dropped elements the way {@code tests/unit/test_cdc_parser.py}
 * does — the dead-letter topic gives operators a way to inspect and replay
 * bad events, which the Python version has no runtime equivalent of.
 */
public final class CdcStreamingStage implements PipelineStage, Serializable {

    private static final long serialVersionUID = 1L;

    private static final Logger LOG = LoggerFactory.getLogger(CdcStreamingStage.class);

    private final Source<PubsubMessage> source;
    private final Sink<PubsubMessage> deadLetterSink;
    private final Warehouse odpWarehouse;
    private final String odpTable;
    private final String entityName;
    private final CdcEventParser parser;

    /**
     * @param source         Pull source for raw Debezium CDC events, e.g. a
     *                        {@link com.enrichmeai.culvert.gcp.pubsub.PubSubSource}
     *                        over the Kafka-Connect-fed subscription (mirrors
     *                        {@code --kafka_topic} in runner.py:70-74; despite
     *                        the flag name, the Python pipeline actually reads
     *                        from Pub/Sub — runner.py:254-259).
     * @param deadLetterSink Sink for events that fail parsing/validation.
     * @param odpWarehouse   BigQuery warehouse for the ODP target table.
     * @param odpTable       Fully-qualified ODP table name
     *                        ({@code project.dataset.table} or
     *                        {@code dataset.table}), mirrors
     *                        {@code --odp_dataset}/{@code --entity_name}
     *                        (runner.py:276).
     * @param entityName     Entity name, used only for stage naming/logging
     *                        (runner.py:97-101).
     */
    public CdcStreamingStage(Source<PubsubMessage> source,
                              Sink<PubsubMessage> deadLetterSink,
                              Warehouse odpWarehouse,
                              String odpTable,
                              String entityName) {
        this.source = Objects.requireNonNull(source, "source must not be null");
        this.deadLetterSink = Objects.requireNonNull(deadLetterSink, "deadLetterSink must not be null");
        this.odpWarehouse = Objects.requireNonNull(odpWarehouse, "odpWarehouse must not be null");
        this.odpTable = Objects.requireNonNull(odpTable, "odpTable must not be null");
        this.entityName = Objects.requireNonNull(entityName, "entityName must not be null");
        this.parser = new CdcEventParser();
    }

    @Override
    public String name() {
        return "cdc-" + entityName + "-odp";
    }

    @Override
    public List<String> inputs() {
        return List.of();
    }

    @Override
    public List<String> outputs() {
        return List.of("odp-rows");
    }

    /**
     * Pull one batch, parse each event, write valid rows to ODP, and
     * dead-letter invalid ones. Mirrors runner.py:249-283 end to end for a
     * single pull cycle.
     */
    @Override
    public void execute(RuntimeContext context) {
        Iterator<PubsubMessage> messages = source.read(context);

        List<Map<String, Object>> validRows = new ArrayList<>();
        List<PubsubMessage> deadLettered = new ArrayList<>();

        while (messages.hasNext()) {
            PubsubMessage message = messages.next();
            String payload = message.getData().toStringUtf8();

            Optional<ParsedCdcEvent> parsed = parser.parse(payload);
            if (parsed.isEmpty()) {
                deadLettered.add(message);
                continue;
            }

            Map<String, Object> withMetadata = mergeMetadata(parsed.get());
            Map<String, Object> odpRow = CdcTransforms.toOdp(withMetadata);
            Map<String, Object> audited = CdcTransforms.addStreamingAudit(odpRow, context.runId());
            validRows.add(audited);
        }

        if (!validRows.isEmpty()) {
            writeToOdp(validRows);
        }
        if (!deadLettered.isEmpty()) {
            deadLetterSink.write(deadLettered.iterator(), context);
            LOG.warn("Dead-lettered {} invalid CDC event(s) for entity={}", deadLettered.size(), entityName);
        }

        LOG.info("CDC batch complete: entity={} valid={} deadLettered={}",
                entityName, validRows.size(), deadLettered.size());
    }

    /**
     * Merge the CDC metadata fields onto the record payload, matching the
     * flat-dict shape {@code ParseCDCEventDoFn.process} produces
     * (cdc_parser.py:97-119) before {@code TransformToODPDoFn} strips nulls.
     */
    private Map<String, Object> mergeMetadata(ParsedCdcEvent event) {
        Map<String, Object> merged = new LinkedHashMap<>(event.record());
        merged.put(CdcEventParser.FIELD_CDC_OPERATION, event.operation().name());
        merged.put(CdcEventParser.FIELD_CDC_SOURCE_TABLE, event.sourceTable());
        merged.put(CdcEventParser.FIELD_CDC_SOURCE_DB, event.sourceDb());
        merged.put(CdcEventParser.FIELD_CDC_SOURCE_SCHEMA, event.sourceSchema());
        merged.put(CdcEventParser.FIELD_CDC_CONNECTOR, event.connector());
        merged.put(CdcEventParser.FIELD_CDC_CONNECTOR_VERSION, event.connectorVersion());
        merged.put(CdcEventParser.FIELD_CDC_EVENT_TIME, event.eventTimeIso());
        if (event.sourceTimeIso() != null) {
            merged.put(CdcEventParser.FIELD_CDC_SOURCE_TIME, event.sourceTimeIso());
        }
        return merged;
    }

    /**
     * Append-only streaming insert via {@link Warehouse#execute(String, Map)}.
     * See the class Javadoc "ODP write semantics" section for why this is a
     * parameterised {@code INSERT} rather than a first-class streaming-insert
     * API call or a {@code MERGE} (the latter throws
     * {@code UnsupportedOperationException} on this branch's
     * {@code BigQueryWarehouse}).
     */
    private void writeToOdp(List<Map<String, Object>> rows) {
        for (Map<String, Object> row : rows) {
            List<String> columns = new ArrayList<>(row.keySet());
            StringBuilder sql = new StringBuilder("INSERT INTO ").append(odpTable).append(" (");
            StringBuilder placeholders = new StringBuilder();
            Map<String, Object> params = new LinkedHashMap<>();
            for (int i = 0; i < columns.size(); i++) {
                String column = columns.get(i);
                String paramName = "p" + i;
                if (i > 0) {
                    sql.append(", ");
                    placeholders.append(", ");
                }
                sql.append(column);
                placeholders.append('@').append(paramName);
                params.put(paramName, row.get(column));
            }
            sql.append(") VALUES (").append(placeholders).append(')');
            odpWarehouse.execute(sql.toString(), params);
        }
    }
}
