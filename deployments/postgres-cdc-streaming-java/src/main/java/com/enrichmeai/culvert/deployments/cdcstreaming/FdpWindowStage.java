package com.enrichmeai.culvert.deployments.cdcstreaming;

import com.enrichmeai.culvert.contracts.PipelineStage;
import com.enrichmeai.culvert.contracts.RuntimeContext;
import com.enrichmeai.culvert.contracts.Warehouse;

import java.io.Serializable;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

/**
 * Ports the FDP (Feature Data Platform) windowing + write stage from
 * {@code runner.py:285-313}: read back rows written to ODP in the current
 * window, apply {@code TransformToFDPDoFn}-equivalent shaping
 * ({@link CdcTransforms#toFdp}), and write to the FDP realtime table.
 *
 * <h2>Streaming semantics caveat (see README.md for the full writeup)</h2>
 *
 * <p>The Python pipeline uses a genuine Beam windowing strategy —
 * {@code FixedWindows} with an {@code AfterWatermark} trigger and an early
 * {@code AfterProcessingTime} firing
 * (deployments/postgres-cdc-streaming/src/streaming_pipeline/pipeline/windows.py:31-55),
 * i.e. watermark-driven, re-triggering, discarding-accumulation windows over
 * an unbounded {@code PCollection}. Culvert's {@code StageTransform} adapter
 * triggers a {@link PipelineStage#execute(RuntimeContext)} call exactly once
 * per pipeline run (data-pipeline-libraries-java/data-pipeline-gcp-dataflow-java/src/main/java/com/enrichmeai/culvert/gcp/dataflow/StageTransform.java:40-48)
 * — there is no watermark, trigger, or accumulation-mode concept at the
 * {@code PipelineStage} contract level today.
 *
 * <p>This port therefore approximates one fixed-window firing per
 * {@code execute()} call: it queries ODP rows whose {@code _processed_at}
 * falls within {@code [now - windowSize, now)}, computed from wall-clock
 * time rather than the Beam event-time watermark. Early/late firing,
 * allowed lateness, and discarding-vs-accumulating semantics are NOT
 * reproduced — a caller wanting true watermark-driven windowing must write
 * a direct Beam pipeline against the Beam SDK (this deployment's pom
 * declares {@code beam-sdks-java-core} for exactly that reason; the
 * contracts here cover the I/O seams, not the windowing engine). This is a
 * known, documented gap, not an oversight — flagged per the task's DoD.
 */
public final class FdpWindowStage implements PipelineStage, Serializable {

    private static final long serialVersionUID = 1L;

    private final Warehouse warehouse;
    private final String odpTable;
    private final String fdpTable;
    private final String entityName;
    private final Duration windowSize;
    private final boolean maskPii;

    public FdpWindowStage(Warehouse warehouse,
                           String odpTable,
                           String fdpTable,
                           String entityName,
                           Duration windowSize,
                           boolean maskPii) {
        this.warehouse = Objects.requireNonNull(warehouse, "warehouse must not be null");
        this.odpTable = Objects.requireNonNull(odpTable, "odpTable must not be null");
        this.fdpTable = Objects.requireNonNull(fdpTable, "fdpTable must not be null");
        this.entityName = Objects.requireNonNull(entityName, "entityName must not be null");
        this.windowSize = Objects.requireNonNull(windowSize, "windowSize must not be null");
        this.maskPii = maskPii;
    }

    @Override
    public String name() {
        return "cdc-" + entityName + "-fdp";
    }

    @Override
    public List<String> inputs() {
        return List.of("odp-rows");
    }

    @Override
    public List<String> outputs() {
        return List.of("fdp-rows");
    }

    @Override
    public void execute(RuntimeContext context) {
        Instant windowEnd = Instant.now();
        Instant windowStart = windowEnd.minus(windowSize);
        String windowStartIso = windowStart.toString();
        String windowEndIso = windowEnd.toString();

        String sql = "SELECT * FROM " + odpTable
                + " WHERE _processed_at >= @windowStart AND _processed_at < @windowEnd";
        Map<String, Object> params = Map.of(
                "windowStart", windowStartIso,
                "windowEnd", windowEndIso);

        Iterator<Map<String, Object>> odpRows = warehouse.query(sql, params);
        List<Map<String, Object>> fdpRows = new ArrayList<>();
        while (odpRows.hasNext()) {
            Map<String, Object> odpRow = odpRows.next();
            Map<String, Object> fdpRow = CdcTransforms.toFdp(odpRow, maskPii, windowStartIso, windowEndIso);
            Map<String, Object> withAudit = new LinkedHashMap<>(fdpRow);
            withAudit.put("_run_id", context.runId());
            withAudit.put("_fdp_processed_at", Instant.now().toString());
            fdpRows.add(withAudit);
        }

        for (Map<String, Object> row : fdpRows) {
            insertRow(row);
        }
    }

    private void insertRow(Map<String, Object> row) {
        List<String> columns = new ArrayList<>(row.keySet());
        StringBuilder sql = new StringBuilder("INSERT INTO ").append(fdpTable).append(" (");
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
        warehouse.execute(sql.toString(), params);
    }
}
