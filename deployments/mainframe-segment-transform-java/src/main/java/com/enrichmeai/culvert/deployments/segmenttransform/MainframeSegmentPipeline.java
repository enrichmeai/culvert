package com.enrichmeai.culvert.deployments.segmenttransform;

import com.enrichmeai.culvert.contracts.JobControlRepository;
import com.enrichmeai.culvert.gcp.bigquery.BigQueryJobControlRepository;
import com.enrichmeai.culvert.jobcontrol.FailureStage;
import com.enrichmeai.culvert.jobcontrol.JobStatus;
import com.google.api.services.bigquery.model.TableRow;
import com.google.cloud.bigquery.BigQueryOptions;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.dataformat.yaml.YAMLFactory;
import org.apache.beam.sdk.PipelineResult;
import org.apache.beam.sdk.options.Default;
import org.apache.beam.sdk.options.Description;
import org.apache.beam.sdk.options.PipelineOptions;
import org.apache.beam.sdk.options.PipelineOptionsFactory;
import org.apache.beam.sdk.options.Validation;
import org.apache.beam.sdk.io.gcp.bigquery.BigQueryIO;
import org.apache.beam.sdk.io.TextIO;
import org.apache.beam.sdk.Pipeline;
import org.apache.beam.sdk.transforms.Count;
import org.apache.beam.sdk.transforms.DoFn;
import org.apache.beam.sdk.transforms.MapElements;
import org.apache.beam.sdk.transforms.ParDo;
import org.apache.beam.sdk.values.PCollection;
import org.apache.beam.sdk.values.TypeDescriptors;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.HashMap;
import java.util.Map;
import java.util.Optional;
import java.util.function.Supplier;

public class MainframeSegmentPipeline {
    private static final Logger LOG = LoggerFactory.getLogger(MainframeSegmentPipeline.class);

    public interface SegmentOptions extends PipelineOptions {
        @Description("GCS path to segment template YAML")
        @Validation.Required
        String getTemplatePath();
        void setTemplatePath(String value);

        @Description("Output bucket name")
        @Validation.Required
        String getOutputBucket();
        void setOutputBucket(String value);

        @Description("Extract date (YYYYMMDD)")
        @Validation.Required
        String getExtractDate();
        void setExtractDate(String value);

        @Description("Period start date (YYYY-MM-DD)")
        String getPeriodStart();
        void setPeriodStart(String value);

        @Description("Period end date (YYYY-MM-DD)")
        String getPeriodEnd();
        void setPeriodEnd(String value);

        @Description("Extract month (YYYYMM)")
        String getExtractMonth();
        void setExtractMonth(String value);

        @Description("FDP source project")
        String getFdpProject();
        void setFdpProject(String value);

        @Description("Run ID")
        String getRunId();
        void setRunId(String value);
        
        @Description("GCP Project ID")
        String getGcpProjectId();
        void setGcpProjectId(String value);

        @Description("Fully-qualified job_control table, project.dataset.table. "
                + "Must be the same table fdp-trigger's JOB_CONTROL_TABLE names: "
                + "the trigger inserts the 'running' row there and this pipeline "
                + "writes the terminal status to it. Defaults to "
                + "<gcpProjectId>.job_control.pipeline_jobs when absent.")
        String getJobControlTable();
        void setJobControlTable(String value);

        @Description("Write the terminal job-control status on completion. "
                + "Set false only for local runs that have no job_control row. "
                + "Deliberately NOT exposed in metadata.json: a launched job must "
                + "not be able to opt out of reporting its own completion, which "
                + "would leave a 'running' row latching the dedup gate closed.")
        @Default.Boolean(true)
        boolean getReportJobControlStatus();
        void setReportJobControlStatus(boolean value);
    }

    /**
     * Whether a run id actually arrived on the command line. Blank counts as
     * absent: {@code --runId=} must not be mistaken for a run whose
     * {@code job_control} row could be completed.
     */
    static boolean runIdSupplied(String runId) {
        return runId != null && !runId.isBlank();
    }

    /** Dataset used when {@code jobControlTable} is not supplied. */
    static final String DEFAULT_JOB_CONTROL_DATASET = "job_control";

    /** Table used when {@code jobControlTable} is not supplied. */
    static final String DEFAULT_JOB_CONTROL_TABLE = "pipeline_jobs";

    public static void main(String[] args) throws IOException {
        SegmentOptions options = PipelineOptionsFactory.fromArgs(args).withValidation().as(SegmentOptions.class);
        run(options);
    }

    public static void run(SegmentOptions options) throws IOException {
        // 1. Load Template
        SegmentTemplate template = loadTemplate(options.getTemplatePath());
        
        String fdpProject = options.getFdpProject() != null ? options.getFdpProject() : options.getGcpProjectId();
        // Keep "supplied" and "synthesised" apart. fdp-trigger inserts the
        // job_control row keyed on the run_id it passes in, so only a SUPPLIED
        // run_id has a row to complete. A synthesised one (manual / local run)
        // has none, and writing a terminal status for it would throw on every
        // such invocation.
        boolean runIdSupplied = runIdSupplied(options.getRunId());
        String runId = runIdSupplied ? options.getRunId() : "manual-" + System.currentTimeMillis();
        String periodLabel = options.getExtractMonth() != null ? options.getExtractMonth() : options.getExtractDate().substring(0, 6);
        
        String outputDir = String.format("gs://%s/segments/%s/%s/%s", 
                options.getOutputBucket(), periodLabel, runId, template.getSegmentId());
        String outputPrefix = outputDir + "/" + template.getOutput().getFilePrefix();

        // 2. Prepare Query
        String query = template.getQuery()
                .replace("{project}", fdpProject)
                .replace("{period_start}", options.getPeriodStart())
                .replace("{period_end}", options.getPeriodEnd());

        LOG.info("Starting pipeline for segment: {} using query: {}", template.getSegmentId(), query);

        Pipeline pipeline = Pipeline.create(options);

        // 3. Build DAG
        PCollection<TableRow> rows = pipeline.apply("ReadFromBigQuery",
                BigQueryIO.readTableRows()
                        .fromQuery(query)
                        .usingStandardSql()
                        .withMethod(BigQueryIO.TypedRead.Method.DIRECT_READ));

        PCollection<String> formatted = rows.apply("FormatFixedWidth",
                ParDo.of(new FormatFixedWidthDoFn(template, options.getExtractDate())));

        TextIO.Write write = TextIO.write().to(outputPrefix)
                .withSuffix(template.getOutput().getFileSuffix())
                .withShardNameTemplate(template.getOutput().getShardTemplate());
        
        if (template.getOutput().getMaxRecordsPerShard() > 0) {
            // Note: Java SDK doesn't have exact 'max_records_per_shard' in TextIO like Python, 
            // but we can use withNumShards or other mechanisms if needed.
            // For now, we'll let Beam handle sharding or use a simple approach.
        }

        formatted.apply("WriteSegmentFiles", write);

        // 4. Manifest generation
        PCollection<Long> count = formatted.apply("CountRecords", Count.globally());
        
        String manifestPath = outputPrefix + ".manifest";
        
        count.apply("BuildManifest", MapElements.into(TypeDescriptors.strings())
                .via(totalRecords -> buildManifestJson(totalRecords, template, periodLabel, runId, options.getExtractDate())))
             .apply("WriteManifest", TextIO.write().to(manifestPath).withoutSharding());

        // 5. Run, then report completion to job_control.
        //
        // waitUntilFinish() RETURNS the terminal state; a Dataflow job that
        // runs and fails comes back as FAILED rather than throwing, so both
        // the returned state and a thrown exception have to reach the
        // terminal write. Without the state check, the on-failure path would
        // silently never fire for the commonest failure mode.
        //
        // Throwable, not RuntimeException: an Error (OOM, NoClassDefFoundError
        // in the launcher) must still close the row out, or it stays 'running'
        // and re-latches the dedup gate.
        PipelineResult.State state = null;
        Throwable pipelineFailure = null;
        try {
            state = pipeline.run().waitUntilFinish();
        } catch (Throwable t) {
            pipelineFailure = t;
        }

        completeRun(() -> openJobControlRepository(options), runId, runIdSupplied,
                options.getReportJobControlStatus(), state, pipelineFailure);
    }

    /**
     * Closes a finished run out: reports its terminal status, then fails the
     * process if the run itself did not succeed.
     *
     * <p>Separated from {@link #run} so it is reachable from a test with a
     * {@link JobControlRepository} double. Everything above this point in
     * {@code run} builds a Beam DAG that cannot be exercised offline, so
     * wiring the terminal write in there left it unverified -- disabling the
     * call kept the whole suite green.
     *
     * <p>The repository arrives as a {@link Supplier} so no BigQuery client is
     * built for a run that is not going to report.
     *
     * @param repository             opens the job-control port, lazily
     * @param runIdSupplied          whether {@code runId} came from options rather
     *                               than being synthesised
     * @param reportJobControlStatus the {@code --reportJobControlStatus} switch
     * @param state                  terminal pipeline state, or null if the run threw
     * @param pipelineFailure        what the run threw, or null
     */
    static void completeRun(Supplier<JobControlRepository> repository, String runId,
                            boolean runIdSupplied, boolean reportJobControlStatus,
                            PipelineResult.State state, Throwable pipelineFailure) {
        if (runIdSupplied && reportJobControlStatus) {
            try {
                reportTerminalStatus(repository.get(), runId, state, pipelineFailure);
            } catch (RuntimeException writeFailure) {
                // AD-5: a failed terminal write is never swallowed. Carry the
                // pipeline's own failure along so neither cause is lost.
                if (pipelineFailure != null) {
                    writeFailure.addSuppressed(pipelineFailure);
                }
                throw writeFailure;
            }
        } else {
            LOG.warn("Not writing a terminal job-control status for runId={}: "
                            + "runIdSupplied={} reportJobControlStatus={}. "
                            + "A run with no supplied runId has no job_control row to complete.",
                    runId, runIdSupplied, reportJobControlStatus);
        }

        if (pipelineFailure != null) {
            throw asUnchecked(pipelineFailure);
        }
        if (state != PipelineResult.State.DONE) {
            throw new IllegalStateException(
                    "Pipeline finished in state " + state + " (expected DONE); runId=" + runId);
        }
    }

    /** Rethrows the run's own failure without wrapping it where it need not be. */
    private static RuntimeException asUnchecked(Throwable t) {
        if (t instanceof RuntimeException runtime) {
            return runtime;
        }
        if (t instanceof Error error) {
            throw error;
        }
        return new IllegalStateException(t);
    }

    /**
     * Writes this run's terminal job-control status.
     *
     * <p>The status goes through {@link JobControlRepository} -- the port --
     * never as raw BigQuery DML (spine AD-14), and uses Culvert's own
     * {@link JobStatus} vocabulary, which is what {@code fdp-trigger}'s dedup
     * gate reads (AD-17). Before this existed nothing ever wrote a terminal
     * status, so every row stayed {@code running} and the gate latched closed
     * against legitimate retries.
     *
     * <p>Nothing here is caught. A terminal write that fails must fail the job
     * loudly rather than let it exit 0 over a stale {@code running} row
     * (AD-5).
     *
     * <p>The record count is deliberately not reported: reading it back needs
     * a Beam Counter plus {@code result.metrics()}, the column is already 0
     * from the trigger's INSERT, and nothing in this flow reads it.
     *
     * @param repository      the job-control port
     * @param runId           the run whose row is being completed; must be the
     *                        id the trigger inserted
     * @param state           terminal pipeline state, or null if the run threw
     * @param pipelineFailure the exception the run threw, or null
     */
    static void reportTerminalStatus(JobControlRepository repository, String runId,
                                     PipelineResult.State state, Throwable pipelineFailure) {
        if (pipelineFailure == null) {
            if (state == PipelineResult.State.DONE) {
                LOG.info("Marking runId={} {}", runId, JobStatus.SUCCEEDED.getValue());
                repository.updateStatus(runId, JobStatus.SUCCEEDED, Optional.empty());
                return;
            }
            // RUNNING / STOPPED / UNKNOWN / null are not outcomes. Recording one
            // as 'failed' would invent a result for a job that may still be
            // alive -- and 'SEGMENT_TRANSFORM_null' is not a diagnosis.
            if (state == null || !state.isTerminal()) {
                throw new IllegalStateException(
                        "Refusing to record non-terminal pipeline state as failed: state="
                                + state + "; runId=" + runId);
            }
        }

        String errorCode = pipelineFailure != null
                ? "SEGMENT_TRANSFORM_EXCEPTION"
                : "SEGMENT_TRANSFORM_" + state;
        String errorMessage = pipelineFailure != null
                ? pipelineFailure.toString()
                : "Pipeline finished in state " + state;
        LOG.warn("Marking runId={} {}: {}", runId, JobStatus.FAILED.getValue(), errorMessage);
        repository.markFailed(runId, errorCode, errorMessage,
                FailureStage.TRANSFORMATION, Optional.empty());
    }

    /**
     * Builds the BigQuery-backed job-control repository for this run.
     *
     * <p>Constructed explicitly rather than through
     * {@code new BigQueryJobControlRepository()}: the no-arg constructor reads
     * {@code GCP_PROJECT} / {@code JOB_CONTROL_DATASET} / {@code JOB_CONTROL_TABLE}
     * from the environment, and none of those are set on a Flex Template
     * launcher.
     */
    private static JobControlRepository openJobControlRepository(SegmentOptions options) {
        String[] parts = resolveJobControlTable(options.getJobControlTable(), options.getGcpProjectId());
        return new BigQueryJobControlRepository(
                BigQueryOptions.newBuilder().setProjectId(parts[0]).build().getService(),
                parts[0], parts[1], parts[2]);
    }

    /**
     * Splits the configured {@code project.dataset.table} into its three parts,
     * or derives the default location from the GCP project.
     *
     * <p>The default must stay in step with {@code fdp-trigger}'s
     * {@code JOB_CONTROL_TABLE}: the trigger writes the {@code running} row and
     * this pipeline completes it, so a disagreement about the table silently
     * re-latches the dedup gate. Pass {@code --jobControlTable} whenever the
     * trigger points anywhere other than
     * {@code <gcpProjectId>.job_control.pipeline_jobs}.
     *
     * @return {@code {project, dataset, table}}
     */
    static String[] resolveJobControlTable(String configured, String gcpProjectId) {
        if (configured != null && !configured.isBlank()) {
            String[] parts = configured.split("\\.");
            if (parts.length != 3) {
                throw new IllegalArgumentException(
                        "jobControlTable must be project.dataset.table, got: " + configured);
            }
            return parts;
        }
        if (gcpProjectId == null || gcpProjectId.isBlank()) {
            throw new IllegalArgumentException(
                    "Cannot locate job_control: pass --jobControlTable or --gcpProjectId");
        }
        return new String[]{gcpProjectId, DEFAULT_JOB_CONTROL_DATASET, DEFAULT_JOB_CONTROL_TABLE};
    }

    private static SegmentTemplate loadTemplate(String path) throws IOException {
        ObjectMapper mapper = new ObjectMapper(new YAMLFactory());
        // Handle GCS paths if necessary, but for simplicity assuming local or accessible via File
        // In Dataflow, we might need to use GCS client to read the YAML.
        if (path.startsWith("gs://")) {
            // Simplified: read from GCS (real implementation would use GCS API)
            // For this exercise, I'll assume it's passed as a local path or handled by the environment
            throw new UnsupportedOperationException("GCS path reading not implemented in this PoC");
        }
        return mapper.readValue(new File(path), SegmentTemplate.class);
    }

    private static String buildManifestJson(Long totalRecords, SegmentTemplate template, String period, String runId, String extractDate) {
        Map<String, Object> manifest = new HashMap<>();
        manifest.put("segment", template.getSegmentId());
        manifest.put("period", period);
        manifest.put("run_id", runId);
        manifest.put("extract_date", extractDate);
        manifest.put("total_records", totalRecords);
        manifest.put("record_length", template.getRecordLength());
        manifest.put("max_records_per_shard", template.getOutput().getMaxRecordsPerShard());
        manifest.put("file_pattern", template.getOutput().getFilePrefix() + "*" + template.getOutput().getFileSuffix());
        
        try {
            return new ObjectMapper().writeValueAsString(manifest);
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }
}
