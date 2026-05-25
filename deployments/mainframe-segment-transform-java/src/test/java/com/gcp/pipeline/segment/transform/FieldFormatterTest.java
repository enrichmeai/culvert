package com.gcp.pipeline.segment.transform;

import org.junit.Before;
import org.junit.Test;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import static org.junit.Assert.assertEquals;

public class FieldFormatterTest {

    private FieldFormatter formatter;
    private Map<String, String> context;

    @Before
    public void setUp() {
        formatter = new FieldFormatter();
        context = new HashMap<>();
        context.put("extract_date", "20260514");
    }

    @Test
    public void testFormatString() {
        SegmentTemplate.FieldDefinition field = new SegmentTemplate.FieldDefinition();
        field.setName("test");
        field.setType("string");
        field.setWidth(10);
        field.setAlign("left");
        field.setPadChar(" ");

        assertEquals("hello     ", formatter.formatField("hello", field, context));
        assertEquals("verylongst", formatter.formatField("verylongstring", field, context));
        
        field.setAlign("right");
        assertEquals("     hello", formatter.formatField("hello", field, context));
    }

    @Test
    public void testFormatInteger() {
        SegmentTemplate.FieldDefinition field = new SegmentTemplate.FieldDefinition();
        field.setName("test");
        field.setType("integer");
        field.setWidth(5);
        field.setAlign("right");
        field.setPadChar("0");

        assertEquals("00123", formatter.formatField(123, field, context));
        assertEquals("00000", formatter.formatField(null, field, context));
        assertEquals("00456", formatter.formatField("456", field, context));
    }

    @Test
    public void testFormatAmount() {
        SegmentTemplate.FieldDefinition field = new SegmentTemplate.FieldDefinition();
        field.setName("test");
        field.setType("amount");
        field.setWidth(10);
        field.setDecimalPlaces(2);
        field.setPadChar(" ");

        assertEquals("    123.46", formatter.formatField(123.456, field, context));
        assertEquals("      0.00", formatter.formatField(null, field, context));
    }

    @Test
    public void testFormatDate() {
        SegmentTemplate.FieldDefinition field = new SegmentTemplate.FieldDefinition();
        field.setName("test");
        field.setType("date");
        field.setWidth(8);
        field.setDateFormat("yyyyMMdd");

        assertEquals("20260514", formatter.formatField("2026-05-14", field, context));
        assertEquals("00000000", formatter.formatField(null, field, context));
    }

    @Test
    public void testExtractDateSource() {
        SegmentTemplate.FieldDefinition field = new SegmentTemplate.FieldDefinition();
        field.setName("test");
        field.setSource("_extract_date");
        field.setType("date");
        field.setWidth(8);
        field.setDateFormat("yyyyMMdd");

        assertEquals("20260514", formatter.formatField(null, field, context));
    }
}
