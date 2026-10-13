package com.enrichmeai.culvert.deployments.ingestion;

import com.enrichmeai.culvert.schema.EntitySchema;
import com.enrichmeai.culvert.schema.SchemaField;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

/** #253: how a CSV cell in an INT64, FLOAT64 or BOOL column is read before validation. */
class CsvCellTypesTest {

    @Test
    void int64ReadsAWholeNumberAsALong() {
        assertThat(CsvCellTypes.cell("INT64", "720")).isEqualTo(720L);
        assertThat(CsvCellTypes.cell("INT64", " -3 ")).isEqualTo(-3L);
        assertThat(CsvCellTypes.cell("INT64", "+42")).isEqualTo(42L);
        assertThat(CsvCellTypes.cell("INT64", "9223372036854775807")).isEqualTo(Long.MAX_VALUE);
        assertThat(CsvCellTypes.cell("INT64", "-0")).isEqualTo(0L);
        assertThat(CsvCellTypes.cell("INT64", "007")).isEqualTo(7L);
    }

    @ParameterizedTest
    @ValueSource(strings = {"7.0", "1e3", "abc", "12a", "9223372036854775808", "0x10", "1_000", "1,000", "\u0663", "+", "-", "1."})
    void int64LeavesAnythingElseAsText(String cell) {
        assertThat(CsvCellTypes.cell("INT64", cell)).isEqualTo(cell);
    }

    @Test
    void float64ReadsAFiniteDecimalAsADouble() {
        assertThat(CsvCellTypes.cell("FLOAT64", "1234.50")).isEqualTo(1234.5d);
        assertThat(CsvCellTypes.cell("FLOAT64", "7")).isEqualTo(7.0d);
        assertThat(CsvCellTypes.cell("FLOAT64", "-.5")).isEqualTo(-0.5d);
        assertThat(CsvCellTypes.cell("FLOAT64", "6.02E23")).isEqualTo(6.02e23d);
        assertThat(CsvCellTypes.cell("FLOAT64", " 3. ")).isEqualTo(3.0d);
        assertThat(CsvCellTypes.cell("FLOAT64", "-0.0")).isEqualTo(-0.0d);
    }

    @ParameterizedTest
    @ValueSource(strings = {"NaN", "Infinity", "-Infinity", "0x1p3", "1d", "2f", "1e999", "abc", "1,5", ".", "\u0663", "+", "1e"})
    void float64LeavesAnythingElseAsText(String cell) {
        // NaN and Infinity are refused because JSON cannot carry them; 1e999 overflows to Infinity.
        assertThat(CsvCellTypes.cell("FLOAT64", cell)).isEqualTo(cell);
    }

    @Test
    void boolReadsTrueAndFalseInAnyCase() {
        assertThat(CsvCellTypes.cell("BOOL", "true")).isEqualTo(Boolean.TRUE);
        assertThat(CsvCellTypes.cell("BOOL", "FALSE")).isEqualTo(Boolean.FALSE);
        assertThat(CsvCellTypes.cell("BOOL", " True ")).isEqualTo(Boolean.TRUE);
    }

    @ParameterizedTest
    @ValueSource(strings = {"yes", "no", "1", "0", "t", "Y"})
    void boolLeavesAnythingElseAsText(String cell) {
        assertThat(CsvCellTypes.cell("BOOL", cell)).isEqualTo(cell);
    }

    @ParameterizedTest
    @ValueSource(strings = {"INT64", "FLOAT64", "BOOL"})
    void anEmptyCellInATypedColumnIsMissing(String type) {
        assertThat(CsvCellTypes.cell(type, "")).isNull();
        assertThat(CsvCellTypes.cell(type, "   ")).isNull();
    }

    @ParameterizedTest
    @ValueSource(strings = {"STRING", "NUMERIC", "DATE", "TIMESTAMP"})
    void everyOtherTypeIsUnchanged(String type) {
        assertThat(CsvCellTypes.cell(type, "")).isEqualTo("");
        assertThat(CsvCellTypes.cell(type, " 720 ")).isEqualTo(" 720 ");
    }

    @Test
    void typedRowConvertsDeclaredColumnsAndKeepsTheRestAndTheOrder() {
        EntitySchema schema = EntitySchema.of("decision", List.of(
                SchemaField.required("decision_id", "STRING"),
                SchemaField.nullable("score", "INT64"),
                SchemaField.nullable("approved", "BOOL")));
        Map<String, Object> raw = new LinkedHashMap<>();
        raw.put("decision_id", "dec-1");
        raw.put("score", "720");
        raw.put("approved", "");
        raw.put("extra", "kept");

        Map<String, Object> typed = CsvCellTypes.typed(raw, schema);

        assertThat(typed).containsExactly(
                Map.entry("decision_id", "dec-1"),
                Map.entry("score", 720L),
                new java.util.AbstractMap.SimpleEntry<>("approved", null),
                Map.entry("extra", "kept"));
        assertThat(raw).containsEntry("score", "720"); // the input is not changed
    }

    @ParameterizedTest
    @ValueSource(strings = {"STRING", "DATE", "TIMESTAMP", "NUMERIC", "INT64", "FLOAT64", "BOOL"})
    void aBlankCellInARequiredFieldOfAnyTypeIsMissing(String type) {
        // #255: the retired Python SchemaValidator treated value.strip() == "" as missing too.
        EntitySchema schema = EntitySchema.of("e", List.of(
                SchemaField.required("a", type), SchemaField.required("b", type),
                SchemaField.required("c", type)));
        Map<String, Object> raw = new LinkedHashMap<>();
        raw.put("a", "");
        raw.put("b", "  ");
        raw.put("c", "\u00A0\t\u202F"); // non-breaking spaces count, as Python's strip() does

        Map<String, Object> typed = CsvCellTypes.typed(raw, schema);

        assertThat(typed).containsEntry("a", null).containsEntry("b", null).containsEntry("c", null);
    }

    @Test
    void aCellOfNonBreakingSpacesInATypedColumnIsMissing() {
        assertThat(CsvCellTypes.cell("INT64", "\u00A0")).isNull();
        assertThat(CsvCellTypes.blank("\u2007 ")).isTrue();
        assertThat(CsvCellTypes.blank(" x ")).isFalse();
    }

    @Test
    void aBlankOptionalStringCellIsStillEmptyText() {
        EntitySchema schema = EntitySchema.of("e", List.of(
                SchemaField.nullable("note", "STRING"), SchemaField.required("id", "STRING")));
        Map<String, Object> raw = new LinkedHashMap<>();
        raw.put("note", "");
        raw.put("id", " x ");

        assertThat(CsvCellTypes.typed(raw, schema))
                .containsEntry("note", "")
                .containsEntry("id", " x "); // a required value with text is unchanged, spaces included
    }

    @Test
    void aNonStringValueIsLeftAlone() {
        Map<String, Object> raw = new HashMap<>();
        raw.put("score", 5L);
        EntitySchema schema = EntitySchema.of("e", List.of(SchemaField.nullable("score", "INT64")));

        assertThat(CsvCellTypes.typed(raw, schema)).containsEntry("score", 5L);
    }
}
