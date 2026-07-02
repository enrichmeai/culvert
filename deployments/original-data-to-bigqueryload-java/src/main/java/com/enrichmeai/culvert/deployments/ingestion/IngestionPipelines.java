package com.enrichmeai.culvert.deployments.ingestion;

import com.enrichmeai.culvert.contracts.PipelineStage;
import com.enrichmeai.culvert.deployments.ingestion.stages.IngestionStage;
import com.enrichmeai.culvert.gcp.dataflow.DataflowPipeline;

import java.util.List;

/**
 * Builds the (currently single-stage) {@link DataflowPipeline} topology for
 * this deployment.
 *
 * <p>A {@link DataflowPipeline} is still constructed — and {@link #validate()}
 * still runs — even though there is only one {@link IngestionStage}, so this
 * deployment produces a real Culvert DAG artifact (usable with
 * {@code buildBeam}/{@code runOnDataflow}/{@code PipelineToDagSpec}) rather
 * than calling {@link IngestionRunner} bare. See {@link IngestionRunner}'s
 * class Javadoc for why the parse/validate/load/reconcile steps are not
 * themselves split into separate {@code PipelineStage}s.
 */
public final class IngestionPipelines {

    private IngestionPipelines() {
        // factory — no instances
    }

    public static DataflowPipeline of(IngestionStage stage) {
        PipelineStage s = stage; // widen for List<PipelineStage>
        return new DataflowPipeline("original-data-to-bigqueryload", List.of(s));
    }
}
