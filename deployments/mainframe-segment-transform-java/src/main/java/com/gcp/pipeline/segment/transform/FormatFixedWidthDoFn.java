package com.gcp.pipeline.segment.transform;

import com.google.api.services.bigquery.model.TableRow;
import org.apache.beam.sdk.transforms.DoFn;
import org.apache.beam.sdk.values.KV;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.HashMap;
import java.util.Map;

public class FormatFixedWidthDoFn extends DoFn<TableRow, String> {
    private static final Logger LOG = LoggerFactory.getLogger(FormatFixedWidthDoFn.class);
    
    private final SegmentTemplate template;
    private final String extractDate;
    private transient FieldFormatter formatter;
    private transient Map<String, String> context;

    public FormatFixedWidthDoFn(SegmentTemplate template, String extractDate) {
        this.template = template;
        this.extractDate = extractDate;
    }

    @Setup
    public void setup() {
        this.formatter = new FieldFormatter();
        this.context = new HashMap<>();
        this.context.put("extract_date", extractDate);
    }

    @ProcessElement
    public void processElement(@Element TableRow row, OutputReceiver<String> out) {
        try {
            StringBuilder line = new StringBuilder();
            for (SegmentTemplate.FieldDefinition fieldDef : template.getOutput().getFields()) {
                Object rawValue = null;
                if (!"_literal".equals(fieldDef.getSource()) && !"_extract_date".equals(fieldDef.getSource())) {
                    rawValue = row.get(fieldDef.getSource());
                }
                line.append(formatter.formatField(rawValue, fieldDef, context));
            }

            String record = line.toString();
            if (record.length() != template.getRecordLength()) {
                throw new RuntimeException(String.format(
                    "Record length %d != expected %d for segment %s",
                    record.length(), template.getRecordLength(), template.getSegmentId()
                ));
            }
            out.output(record);
        } catch (Exception e) {
            LOG.error("Error formatting record: {}", e.getMessage(), e);
            // In a real production scenario, we might want to route this to an error-tagged output
            throw e; 
        }
    }
}
