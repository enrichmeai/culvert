package com.gcp.pipeline.segment.transform;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;
import java.util.List;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class SegmentTemplate implements Serializable {
    private static final long serialVersionUID = 1L;

    @JsonProperty("segment_id")
    private String segmentId;
    
    @JsonProperty("segment_name")
    private String segmentName;
    
    private String description;
    
    @JsonProperty("record_length")
    private int recordLength;
    
    private SourceConfig source;
    private String query;
    private OutputConfig output;

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class SourceConfig implements Serializable {
        private static final long serialVersionUID = 1L;
        private String dataset;
        private String table;
        
        @JsonProperty("partition_column")
        private String partitionColumn;
    }

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class OutputConfig implements Serializable {
        private static final long serialVersionUID = 1L;
        
        @JsonProperty("file_prefix")
        private String filePrefix;
        
        @JsonProperty("file_suffix")
        private String fileSuffix;
        
        @JsonProperty("shard_template")
        private String shardTemplate;
        
        @JsonProperty("max_records_per_shard")
        private int maxRecordsPerShard;
        
        private List<FieldDefinition> fields;
    }

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class FieldDefinition implements Serializable {
        private static final long serialVersionUID = 1L;
        private String name;
        private String source;
        private int width;
        private String type; // string, integer, amount, rate, date, filler
        private String align = "left";
        
        @JsonProperty("pad_char")
        private String padChar = " ";
        
        @JsonProperty("decimal_places")
        private int decimalPlaces = 2;
        
        @JsonProperty("date_format")
        private String dateFormat = "yyyyMMdd";
        
        @JsonProperty("null_value")
        private String nullValue = "";
        
        @JsonProperty("literal_value")
        private String literalValue = "";
    }
}
