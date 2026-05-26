package com.enrichmeai.culvert.deployments.segmenttransform;

import com.google.api.services.bigquery.model.TableRow;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.dataformat.yaml.YAMLFactory;
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
    }

    public static void main(String[] args) throws IOException {
        SegmentOptions options = PipelineOptionsFactory.fromArgs(args).withValidation().as(SegmentOptions.class);
        run(options);
    }

    public static void run(SegmentOptions options) throws IOException {
        // 1. Load Template
        SegmentTemplate template = loadTemplate(options.getTemplatePath());
        
        String fdpProject = options.getFdpProject() != null ? options.getFdpProject() : options.getGcpProjectId();
        String runId = options.getRunId() != null ? options.getRunId() : "manual-" + System.currentTimeMillis();
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

        pipeline.run().waitUntilFinish();
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
