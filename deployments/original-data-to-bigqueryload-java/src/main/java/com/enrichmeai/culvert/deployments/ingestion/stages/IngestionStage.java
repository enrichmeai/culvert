package com.enrichmeai.culvert.deployments.ingestion.stages;

import com.enrichmeai.culvert.contracts.PipelineStage;
import com.enrichmeai.culvert.contracts.RuntimeContext;
import com.enrichmeai.culvert.contracts.BlobStore;
import com.enrichmeai.culvert.contracts.JobControlRepository;
import com.enrichmeai.culvert.contracts.Warehouse;
import com.enrichmeai.culvert.deployments.ingestion.IngestionRequest;
import com.enrichmeai.culvert.deployments.ingestion.IngestionResult;
import com.enrichmeai.culvert.deployments.ingestion.IngestionRunner;

import java.io.Serializable;
import java.util.List;
import java.util.Objects;

/**
 * Single {@link PipelineStage} wrapping one {@link IngestionRunner#run} call.
 *
 * <p>Named {@code "ingest"}; no {@link #inputs()} (it is the pipeline's only
 * stage) and no {@link #outputs()} (its effects — the BigQuery load, the
 * quarantine write, the job-control transitions — are all side effects
 * reached through the {@link RuntimeContext} adapters, not a downstream
 * {@code PipelineStage} input). See {@link IngestionRunner}'s class Javadoc
 * for why this deployment does not split parse/validate/load/reconcile into
 * separate {@code PipelineStage}s wired through Beam {@code PCollection}s.
 *
 * <p>Resolves {@link BlobStore}, {@link Warehouse}, and
 * {@link JobControlRepository} from the {@link RuntimeContext} via
 * {@link RuntimeContext#get(Class)} at {@link #execute} time (worker-side, per
 * the {@code StageTransform}/T10.6 pattern —
 * {@code data-pipeline-gcp-dataflow-java/.../StageTransform.java:70-93}: adapters
 * are resolved inside {@code execute}, never captured at construction time,
 * since {@code DefaultRuntimeContext}'s registry is {@code transient} and is
 * not shipped to Beam workers).
 *
 * <p>Implements {@link Serializable} because {@code StageTransform} captures
 * the stage in a Beam {@code DoFn} (see {@code StageTransform.java:119-128}).
 * The {@link IngestionRequest} fields are plain strings, so this stage is
 * trivially serializable.
 */
public final class IngestionStage implements PipelineStage, Serializable {

    private static final long serialVersionUID = 1L;

    private final String runId;
    private final String entity;
    private final String sourceUri;
    private final String extractDate;
    private final String targetTable;
    private final String stagingPathPrefix;
    private final String errorPathPrefix;

    public IngestionStage(
            String runId,
            String entity,
            String sourceUri,
            String extractDate,
            String targetTable,
            String stagingPathPrefix,
            String errorPathPrefix) {
        this.runId = Objects.requireNonNull(runId, "runId must not be null");
        this.entity = Objects.requireNonNull(entity, "entity must not be null");
        this.sourceUri = Objects.requireNonNull(sourceUri, "sourceUri must not be null");
        this.extractDate = Objects.requireNonNull(extractDate, "extractDate must not be null");
        this.targetTable = Objects.requireNonNull(targetTable, "targetTable must not be null");
        this.stagingPathPrefix =
                Objects.requireNonNull(stagingPathPrefix, "stagingPathPrefix must not be null");
        this.errorPathPrefix = Objects.requireNonNull(errorPathPrefix, "errorPathPrefix must not be null");
    }

    @Override
    public String name() {
        return "ingest";
    }

    @Override
    public List<String> inputs() {
        return List.of();
    }

    @Override
    public List<String> outputs() {
        return List.of();
    }

    @Override
    public void execute(RuntimeContext context) {
        BlobStore blobStore = context.get(BlobStore.class);
        Warehouse warehouse = context.get(Warehouse.class);
        JobControlRepository jobControlRepository = context.get(JobControlRepository.class);

        IngestionRunner runner = new IngestionRunner(
                blobStore, warehouse, jobControlRepository, stagingPathPrefix, errorPathPrefix);

        IngestionResult result = runner.run(
                new IngestionRequest(runId, entity, sourceUri, extractDate, targetTable));
        lastResult = result;
    }

    // Package-visible escape hatch for tests that run the stage directly and
    // want to assert on the outcome without re-deriving it from adapter state.
    // Transient: not part of the Beam-serialized identity of the stage.
    private transient IngestionResult lastResult;

    public IngestionResult lastResult() {
        return lastResult;
    }
}
