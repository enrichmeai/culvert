package com.enrichmeai.culvert.deployments.ingestion;

import com.enrichmeai.culvert.schema.EntitySchema;
import com.enrichmeai.culvert.schema.SchemaField;

import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;
import java.util.regex.Pattern;

/**
 * Reads a CSV cell in an INT64, FLOAT64 or BOOL column as a number or a
 * boolean, before {@link com.enrichmeai.culvert.dataquality.DataQualityTransform}
 * validates the row (#253).
 *
 * <p>A CSV cell is always text, and {@code DataQualityTransform} checks those
 * three types against {@code Number} and {@code Boolean}, so without this
 * every value in such a column was a TYPE_MISMATCH. The retired Python
 * pipeline's {@code SchemaValidator} only checked that a cell could be read as
 * its type, and was looser: it accepted thousands separators ({@code 1,000})
 * and {@code 1/0/yes/no} as booleans. Those are refused here.
 *
 * <ul>
 *   <li><b>INT64:</b> a whole number that fits in a {@code long}, becomes a {@link Long}.</li>
 *   <li><b>FLOAT64:</b> a finite decimal number, with an optional exponent, becomes
 *       a {@link Double}. NaN, Infinity, hex and Java suffixes ({@code 1d}) are not
 *       numbers here: JSON cannot carry the first two, and a CSV producer does not
 *       write the others.</li>
 *   <li><b>BOOL:</b> {@code true} or {@code false}, in any case, becomes a {@link Boolean}.</li>
 * </ul>
 *
 * <p>Spaces around a cell are ignored. An empty cell is a missing value
 * ({@code null}), so an optional column loads it as NULL and a required one
 * fails as MISSING_REQUIRED. Anything else is left as the text it was, so the
 * validator reports the TYPE_MISMATCH with the value. Every other declared
 * type is left unchanged.
 *
 * <p>A blank cell (empty, or only whitespace, non-breaking spaces included)
 * in a {@code REQUIRED} field is missing whatever the field's type (#255), so
 * it fails as MISSING_REQUIRED instead of loading as {@code ""}; the retired
 * Python {@code SchemaValidator} treated it the same way. A blank cell in an
 * optional field of another type still loads as {@code ""}.
 */
final class CsvCellTypes {

    // ASCII digits only: Long.parseLong would also accept other scripts' digits.
    private static final Pattern INT64 = Pattern.compile("[+-]?[0-9]+");
    private static final Pattern FLOAT64 = Pattern.compile("[+-]?([0-9]+\\.?[0-9]*|\\.[0-9]+)([eE][+-]?[0-9]+)?");

    private CsvCellTypes() {
    }

    /**
     * A copy of {@code row} with each cell of a declared INT64, FLOAT64 or BOOL column converted,
     * and a blank cell in a required field made missing.
     */
    static Map<String, Object> typed(Map<String, Object> row, EntitySchema schema) {
        Map<String, Object> out = new LinkedHashMap<>(row);
        for (SchemaField field : schema.fields()) {
            if (out.containsKey(field.name())) {
                Object raw = out.get(field.name());
                boolean blankRequired = "REQUIRED".equals(field.mode()) && raw instanceof String s && blank(s);
                out.put(field.name(), blankRequired ? null : cell(field.type(), raw));
            }
        }
        return out;
    }

    /**
     * Empty, or only whitespace. Non-breaking spaces count, as they do for Python's
     * {@code str.strip()}; Java's {@code isBlank} and {@code strip} skip them.
     */
    static boolean blank(String text) {
        return text.codePoints().allMatch(c -> Character.isWhitespace(c) || Character.isSpaceChar(c));
    }

    /** One cell: the converted value, {@code null} for an empty cell, or {@code raw} unchanged. */
    static Object cell(String type, Object raw) {
        if (!(raw instanceof String text)) {
            return raw;
        }
        if (!"INT64".equals(type) && !"FLOAT64".equals(type) && !"BOOL".equals(type)) {
            return raw;
        }
        if (blank(text)) {
            return null;
        }
        String value = text.strip();
        switch (type) {
            case "INT64":
                if (INT64.matcher(value).matches()) {
                    try {
                        return Long.parseLong(value);
                    } catch (NumberFormatException tooBig) {
                        return raw;
                    }
                }
                return raw;
            case "FLOAT64":
                if (FLOAT64.matcher(value).matches()) {
                    double d = Double.parseDouble(value);
                    return Double.isFinite(d) ? d : raw;
                }
                return raw;
            default: // BOOL
                String lower = value.toLowerCase(Locale.ROOT);
                if (lower.equals("true")) {
                    return Boolean.TRUE;
                }
                return lower.equals("false") ? Boolean.FALSE : raw;
        }
    }
}
