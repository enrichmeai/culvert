package com.enrichmeai.culvert.deployments.segmenttransform;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.Map;

public class FieldFormatter {

    public String formatField(Object value, SegmentTemplate.FieldDefinition fieldDef, Map<String, String> context) {
        Object raw;
        if ("_literal".equals(fieldDef.getSource())) {
            raw = fieldDef.getLiteralValue();
        } else if ("_extract_date".equals(fieldDef.getSource())) {
            raw = context.get("extract_date");
        } else {
            raw = value;
        }

        switch (fieldDef.getType()) {
            case "string":
                return formatString(raw, fieldDef);
            case "integer":
                return formatInteger(raw, fieldDef);
            case "amount":
            case "rate":
                return formatDecimal(raw, fieldDef);
            case "date":
                return formatDate(raw, fieldDef);
            case "filler":
                return formatFiller(fieldDef);
            default:
                throw new IllegalArgumentException("Unknown field type: " + fieldDef.getType());
        }
    }

    private String formatString(Object value, SegmentTemplate.FieldDefinition fieldDef) {
        String text = (value == null) ? "" : value.toString().trim();
        if (text.length() > fieldDef.getWidth()) {
            text = text.substring(0, fieldDef.getWidth());
        }
        return pad(text, fieldDef.getWidth(), fieldDef.getPadChar(), "right".equals(fieldDef.getAlign()));
    }

    private String formatInteger(Object value, SegmentTemplate.FieldDefinition fieldDef) {
        String text = "0";
        if (value != null) {
            try {
                if (value instanceof Number) {
                    text = String.valueOf(((Number) value).longValue());
                } else {
                    text = String.valueOf(Long.parseLong(value.toString()));
                }
            } catch (NumberFormatException e) {
                text = "0";
            }
        }
        if (text.length() > fieldDef.getWidth()) {
            text = text.substring(0, fieldDef.getWidth());
        }
        return pad(text, fieldDef.getWidth(), fieldDef.getPadChar(), "right".equals(fieldDef.getAlign()));
    }

    private String formatDecimal(Object value, SegmentTemplate.FieldDefinition fieldDef) {
        BigDecimal decimal;
        if (value == null) {
            decimal = BigDecimal.ZERO;
        } else {
            try {
                if (value instanceof Number) {
                    decimal = new BigDecimal(value.toString());
                } else {
                    decimal = new BigDecimal(value.toString());
                }
            } catch (NumberFormatException e) {
                decimal = BigDecimal.ZERO;
            }
        }
        String text = decimal.setScale(fieldDef.getDecimalPlaces(), RoundingMode.HALF_UP).toPlainString();
        if (text.length() > fieldDef.getWidth()) {
            text = text.substring(0, fieldDef.getWidth());
        }
        // Decimals are typically right aligned
        return pad(text, fieldDef.getWidth(), fieldDef.getPadChar(), true);
    }

    private String formatDate(Object value, SegmentTemplate.FieldDefinition fieldDef) {
        String formatted = null;
        DateTimeFormatter targetFormatter = DateTimeFormatter.ofPattern(fieldDef.getDateFormat());

        if (value instanceof LocalDate) {
            formatted = ((LocalDate) value).format(targetFormatter);
        } else if (value instanceof LocalDateTime) {
            formatted = ((LocalDateTime) value).format(targetFormatter);
        } else if (value instanceof String && !((String) value).trim().isEmpty()) {
            String strValue = ((String) value).trim();
            String[] formats = {"yyyy-MM-dd", "yyyyMMdd", "yyyy-MM-dd HH:mm:ss"};
            for (String fmt : formats) {
                try {
                    if (fmt.contains("HH")) {
                        formatted = LocalDateTime.parse(strValue, DateTimeFormatter.ofPattern(fmt)).format(targetFormatter);
                    } else {
                        formatted = LocalDate.parse(strValue, DateTimeFormatter.ofPattern(fmt)).format(targetFormatter);
                    }
                    break;
                } catch (Exception ignored) {}
            }
            if (formatted == null) {
                formatted = strValue.replace("-", "");
            }
        }

        if (formatted == null) {
            formatted = fieldDef.getNullValue();
            if (formatted == null || formatted.isEmpty()) {
                formatted = repeat("0", fieldDef.getWidth());
            }
        }

        if (formatted.length() > fieldDef.getWidth()) {
            formatted = formatted.substring(0, fieldDef.getWidth());
        }
        return pad(formatted, fieldDef.getWidth(), "0", false);
    }

    private String formatFiller(SegmentTemplate.FieldDefinition fieldDef) {
        return repeat(fieldDef.getPadChar(), fieldDef.getWidth());
    }

    private String pad(String text, int width, String padChar, boolean rightAlign) {
        if (text.length() >= width) {
            return text.substring(0, width);
        }
        int padLen = width - text.length();
        String padding = repeat(padChar, padLen);
        return rightAlign ? padding + text : text + padding;
    }

    private String repeat(String s, int n) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < n; i++) {
            sb.append(s);
        }
        return sb.toString();
    }
}
