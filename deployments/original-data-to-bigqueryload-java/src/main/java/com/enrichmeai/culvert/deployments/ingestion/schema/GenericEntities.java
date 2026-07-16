package com.enrichmeai.culvert.deployments.ingestion.schema;

import com.enrichmeai.culvert.schema.EntitySchema;
import com.enrichmeai.culvert.schema.SchemaField;

import java.util.List;
import java.util.Map;

/**
 * Entity registry ported from the retired Python reference's
 * {@code data_ingestion.schema.registry} / {@code data_ingestion.config.constants}
 * (removed 2026-07; in git history at
 * {@code deployments/original-data-to-bigqueryload/src/data_ingestion/schema/*.py}
 * and {@code .../config/constants.py}).
 *
 * <p>Four entities: customers, accounts, decision, applications. Each maps to
 * an {@link EntitySchema} (for {@link com.enrichmeai.culvert.dataquality.DataQualityTransform}
 * validation and {@link com.enrichmeai.culvert.gcp.bigquery.BigQueryWarehouse#loadFromUri}
 * schema) and a CSV header list (for {@code CsvRowParser}).
 *
 * <h2>Fidelity gaps (flagged, not silently dropped)</h2>
 * <p>Culvert's {@link SchemaField} carries {@code name/type/mode/description/
 * classification/masking/range} — it has <strong>no {@code allowed_values}
 * (enum) constraint</strong>, unlike the Python {@code SchemaField.allowed_values}
 * (e.g. {@code status in ["A","I","C"]}, {@code decision_code in
 * ["APPROVE","DECLINE","REVIEW","PENDING"]}). {@link com.enrichmeai.culvert.dataquality.DataQualityTransform}
 * therefore does NOT enforce these enums — a value like {@code status=ZZZ} loads
 * successfully in this Java port where the Python pipeline would reject it. This
 * is a genuine behavioural gap versus the Python original, not an oversight;
 * closing it requires either a Culvert core change (out of T20.5 scope) or a
 * bespoke enum-check stage layered on top of {@code DataQualityTransform}. See
 * README "Known gaps vs the Python reference".
 *
 * <p>Wire-type mapping: Culvert's {@code DataQualityTransform} only type-checks
 * {@code STRING/INT64/FLOAT64/BOOL} (see
 * {@code DataQualityTransform.WIRE_TYPE_MAP}); other declared types pass the
 * type check unconditionally. The Python schema's {@code NUMERIC}, {@code FLOAT},
 * {@code INTEGER}, {@code TIMESTAMP}, {@code DATE} types are mapped here to their
 * closest Culvert/BigQuery-schema equivalent for {@code loadFromUri}'s generated
 * BigQuery schema ({@code BigQueryWarehouse.mapSqlType} recognises
 * STRING/INT64/FLOAT64/BOOL/DATE/DATETIME/TIMESTAMP/NUMERIC/BIGNUMERIC/BYTES/JSON),
 * but DQ-stage type checking for those extra types is a no-op, same as the
 * INTEGER/NUMERIC/FLOAT/TIMESTAMP fields below.
 */
public final class GenericEntities {

    public static final String SYSTEM_ID = "Generic";

    public static final String CUSTOMERS = "customers";
    public static final String ACCOUNTS = "accounts";
    public static final String DECISION = "decision";
    public static final String APPLICATIONS = "applications";

    private static final EntitySchema CUSTOMERS_SCHEMA = EntitySchema.of(CUSTOMERS, List.of(
            SchemaField.required("customer_id", "STRING"),
            SchemaField.required("first_name", "STRING"),
            SchemaField.required("last_name", "STRING"),
            SchemaField.required("ssn", "STRING"),
            SchemaField.required("dob", "DATE"),
            SchemaField.nullable("status", "STRING"),
            SchemaField.nullable("created_date", "DATE")));

    private static final EntitySchema ACCOUNTS_SCHEMA = EntitySchema.of(ACCOUNTS, List.of(
            SchemaField.required("account_id", "STRING"),
            SchemaField.required("customer_id", "STRING"),
            SchemaField.nullable("account_type", "STRING"),
            SchemaField.nullable("balance", "NUMERIC"),
            SchemaField.nullable("status", "STRING"),
            SchemaField.nullable("open_date", "DATE")));

    private static final EntitySchema DECISION_SCHEMA = EntitySchema.of(DECISION, List.of(
            SchemaField.required("decision_id", "STRING"),
            SchemaField.required("customer_id", "STRING"),
            SchemaField.nullable("application_id", "STRING"),
            SchemaField.required("decision_code", "STRING"),
            SchemaField.required("decision_date", "TIMESTAMP"),
            SchemaField.nullable("score", "INT64"),
            SchemaField.nullable("reason_codes", "STRING")));

    private static final EntitySchema APPLICATIONS_SCHEMA = EntitySchema.of(APPLICATIONS, List.of(
            SchemaField.required("application_id", "STRING"),
            SchemaField.required("customer_id", "STRING"),
            SchemaField.nullable("loan_amount", "FLOAT64"),
            SchemaField.nullable("interest_rate", "FLOAT64"),
            SchemaField.nullable("term_months", "INT64"),
            SchemaField.required("application_date", "DATE"),
            SchemaField.required("status", "STRING"),
            SchemaField.nullable("event_type", "STRING"),
            SchemaField.nullable("account_type", "STRING")));

    private static final Map<String, EntitySchema> SCHEMAS = Map.of(
            CUSTOMERS, CUSTOMERS_SCHEMA,
            ACCOUNTS, ACCOUNTS_SCHEMA,
            DECISION, DECISION_SCHEMA,
            APPLICATIONS, APPLICATIONS_SCHEMA);

    // CSV headers — ported verbatim from
    // deployments/original-data-to-bigqueryload/src/data_ingestion/config/constants.py:8-47.
    private static final Map<String, List<String>> HEADERS = Map.of(
            CUSTOMERS, List.of("customer_id", "first_name", "last_name", "ssn", "dob", "status", "created_date"),
            ACCOUNTS, List.of("account_id", "customer_id", "account_type", "balance", "status", "open_date"),
            DECISION, List.of("decision_id", "customer_id", "application_id", "decision_code", "decision_date",
                    "score", "reason_codes"),
            APPLICATIONS, List.of("application_id", "customer_id", "loan_amount", "interest_rate", "term_months",
                    "application_date", "status", "event_type", "account_type"));

    private GenericEntities() {
        // registry — no instances
    }

    public static EntitySchema schemaFor(String entity) {
        EntitySchema schema = SCHEMAS.get(entity);
        if (schema == null) {
            throw new IllegalArgumentException("Unknown entity: " + entity);
        }
        return schema;
    }

    public static List<String> headersFor(String entity) {
        List<String> headers = HEADERS.get(entity);
        if (headers == null) {
            throw new IllegalArgumentException("Unknown entity: " + entity);
        }
        return headers;
    }

    public static boolean isKnownEntity(String entity) {
        return SCHEMAS.containsKey(entity);
    }
}
