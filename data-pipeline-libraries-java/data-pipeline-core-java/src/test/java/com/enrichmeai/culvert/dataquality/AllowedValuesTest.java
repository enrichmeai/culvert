package com.enrichmeai.culvert.dataquality;

import com.enrichmeai.culvert.schema.EntitySchema;
import com.enrichmeai.culvert.schema.SchemaField;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Function;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * Allowed values on a STRING field (#259): {@link SchemaField#allowed()} and the
 * {@link ViolationKind#NOT_ALLOWED} check in {@link DataQualityTransform}. The Python
 * {@code TestAllowedValues} in {@code test_dataquality.py} runs the same cases.
 */
class AllowedValuesTest {

    private static final SchemaField STATUS =
            SchemaField.nullable("status", "STRING").withAllowed(List.of("A", "I", "C"));

    private static ValidationResult<Map<String, Object>> validate(SchemaField field, Object value) {
        Map<String, Object> row = new HashMap<>();
        row.put(field.name(), value);
        return new DataQualityTransform<Map<String, Object>>(
                EntitySchema.of("accounts", List.of(field)), Function.identity()).validate(row);
    }

    private static List<ViolationKind> kinds(ValidationResult<Map<String, Object>> result) {
        assertThat(result).isInstanceOf(ValidationResult.InvalidRow.class);
        return ((ValidationResult.InvalidRow<Map<String, Object>>) result).violations().stream()
                .map(FieldViolation::violationKind).toList();
    }

    @Test
    void aValueOutsideTheListIsNotAllowed() {
        ValidationResult<Map<String, Object>> result = validate(STATUS, "X");

        assertThat(kinds(result)).containsExactly(ViolationKind.NOT_ALLOWED);
        FieldViolation v = ((ValidationResult.InvalidRow<Map<String, Object>>) result).violations().get(0);
        assertThat(v.fieldName()).isEqualTo("status");
        assertThat(v.detail()).isEqualTo("Field 'status' value 'X' is not one of [A, I, C]");
    }

    @ParameterizedTest
    @ValueSource(strings = {"A", "I", "C"})
    void aListedValuePasses(String value) {
        assertThat(validate(STATUS, value).isValid()).isTrue();
    }

    @ParameterizedTest
    @ValueSource(strings = {"a", " A", "A "})
    void theComparisonIsExact(String value) {
        assertThat(kinds(validate(STATUS, value))).containsExactly(ViolationKind.NOT_ALLOWED);
    }

    @ParameterizedTest
    @ValueSource(strings = {"", "  ", " "})
    void aBlankValueInAnOptionalFieldPasses(String value) {
        assertThat(validate(STATUS, value).isValid()).isTrue();
    }

    @Test
    void noValueInAnOptionalFieldPasses() {
        assertThat(validate(STATUS, null).isValid()).isTrue();
    }

    @Test
    void aNextLineCharacterIsNotBlank() {
        // U+0085: Python's isspace() says yes, Java's whitespace test says no; both treat it as a value.
        assertThat(kinds(validate(STATUS, "\u0085"))).containsExactly(ViolationKind.NOT_ALLOWED);
    }

    @Test
    void aBlankValueInARequiredFieldIsNotAllowed() {
        SchemaField required = SchemaField.required("status", "STRING").withAllowed(List.of("A", "I", "C"));

        assertThat(kinds(validate(required, ""))).containsExactly(ViolationKind.NOT_ALLOWED);
    }

    @Test
    void aTypeMismatchIsNotAlsoReportedAsNotAllowed() {
        assertThat(kinds(validate(STATUS, 7L))).containsExactly(ViolationKind.TYPE_MISMATCH);
    }

    @Test
    void theValuesAreACopy() {
        List<String> values = new ArrayList<>(List.of("A", "I"));
        SchemaField field = SchemaField.nullable("s", "STRING").withAllowed(values);
        values.add("C");

        assertThat(field.allowed()).contains(List.of("A", "I"));
        assertThatThrownBy(() -> field.allowed().get().add("C")).isInstanceOf(UnsupportedOperationException.class);
    }

    @Test
    void aFieldRefusesAllowedValuesOnAnotherType() {
        assertThatThrownBy(() -> SchemaField.nullable("n", "INT64").withAllowed(List.of("1")))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("allowed values are for STRING fields, and 'n' is INT64");
    }

    @Test
    void aFieldRefusesAnEmptyList() {
        assertThatThrownBy(() -> STATUS.withAllowed(List.of()))
                .isInstanceOf(IllegalArgumentException.class).hasMessage("allowed must not be empty");
    }

    @Test
    void aFieldRefusesANullValue() {
        assertThatThrownBy(() -> STATUS.withAllowed(Arrays.asList("A", null)))
                .isInstanceOf(IllegalArgumentException.class).hasMessage("allowed values must be strings");
    }

    @Test
    void aFieldRefusesABlankValue() {
        assertThatThrownBy(() -> STATUS.withAllowed(List.of("A", " ")))
                .isInstanceOf(IllegalArgumentException.class).hasMessage("allowed values must not be blank");
    }

    @Test
    void aFieldRefusesADuplicateValue() {
        assertThatThrownBy(() -> STATUS.withAllowed(List.of("A", "A")))
                .isInstanceOf(IllegalArgumentException.class).hasMessage("duplicate allowed value 'A'");
    }

    @Test
    void theExistingConstructorsLeaveAllowedEmpty() {
        assertThat(SchemaField.nullable("s", "STRING").allowed()).isEmpty();
        assertThat(SchemaField.required("s", "STRING").withRange(NumericRange.of(0, 1)).allowed()).isEmpty();
    }
}
