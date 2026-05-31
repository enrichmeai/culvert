package com.enrichmeai.culvert.gcp.bigquery;

import com.enrichmeai.culvert.itsupport.BigQueryEmulatorContainer;
import com.google.cloud.bigquery.BigQuery;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInstance;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import java.util.Iterator;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Integration tests for {@link BigQueryWarehouse} exercised against a real
 * BigQuery emulator (goccy/bigquery-emulator) via the it-support
 * {@link BigQueryEmulatorContainer} fixture.
 *
 * <p>Where {@code BigQueryWarehouseTest} mocks the {@link BigQuery} client and
 * asserts on the SQL that gets built, this IT drives the adapter end-to-end:
 * it creates a real table, inserts rows, then exercises
 * {@link BigQueryWarehouse#query(String, Map)} and
 * {@link BigQueryWarehouse#tableExists(String)} against the live emulator and
 * asserts on the rows that actually come back.
 *
 * <p>Scope is kept to the goccy emulator's supported standard-SQL subset:
 * {@code CREATE TABLE}, {@code INSERT ... VALUES} and {@code SELECT}. The
 * emulator returns INT64/FLOAT64 values over its REST endpoint as their string
 * form (the same behaviour the unit test relies on), so numeric assertions
 * compare against the string representation; the STRING column is asserted
 * directly.
 *
 * <p>Table setup runs through {@link BigQueryWarehouse#execute(String, Map)}
 * (the adapter's DDL/DML path) rather than the raw SDK insertAll streaming API,
 * which the emulator does not support.
 *
 * <p>Sprint-10 deliverable (T10.2).
 */
@Testcontainers
@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class BigQueryWarehouseIT {

    @Container
    static final BigQueryEmulatorContainer EMULATOR = new BigQueryEmulatorContainer();

    private BigQueryWarehouse warehouse;
    private String dataset;
    private String table;

    @BeforeAll
    void setUp() {
        // Wire the warehouse with the emulator's seeded project and a client
        // pointed at the running container. Two-part fqtns (dataset.table)
        // then resolve against this project id inside the adapter.
        warehouse = new BigQueryWarehouse(EMULATOR.getProjectId(), EMULATOR.newClient());
        dataset = EMULATOR.getDatasetId();
        table = "customers";

        String fqtn = "`" + EMULATOR.getProjectId() + "." + dataset + "." + table + "`";

        // CREATE then INSERT via the adapter's execute() path — the emulator
        // supports standard-SQL DDL/DML but not the streaming insertAll API.
        warehouse.execute(
                "CREATE TABLE " + fqtn + " ("
                        + "id INT64, "
                        + "name STRING, "
                        + "score FLOAT64)",
                Map.of());

        warehouse.execute(
                "INSERT INTO " + fqtn + " (id, name, score) VALUES "
                        + "(1, 'alice', 9.5), "
                        + "(2, 'bob', 7.25)",
                Map.of());
    }

    @Test
    void queryReturnsInsertedRows() {
        String fqtn = dataset + "." + table;

        Iterator<Map<String, Object>> rows = warehouse.query(
                "SELECT id, name, score FROM `"
                        + EMULATOR.getProjectId() + "." + fqtn + "` ORDER BY id",
                Map.of());

        assertThat(rows.hasNext()).isTrue();
        Map<String, Object> first = rows.next();
        // Emulator returns INT64/FLOAT64 over REST as their string form (same
        // as the mocked unit test); the STRING column is the stable assertion.
        assertThat(first).containsEntry("name", "alice");
        assertThat(first.get("id")).hasToString("1");

        assertThat(rows.hasNext()).isTrue();
        Map<String, Object> second = rows.next();
        assertThat(second).containsEntry("name", "bob");
        assertThat(second.get("id")).hasToString("2");

        assertThat(rows.hasNext()).isFalse();
    }

    @Test
    void queryWithPredicateFiltersRows() {
        // Literal predicate (no @named parameters) keeps this inside the
        // emulator's guaranteed CREATE/INSERT/SELECT subset; named-parameter
        // binding is already covered by the mocked unit test.
        Iterator<Map<String, Object>> rows = warehouse.query(
                "SELECT id, name FROM `"
                        + EMULATOR.getProjectId() + "." + dataset + "." + table + "` "
                        + "WHERE name = 'bob'",
                Map.of());

        assertThat(rows.hasNext()).isTrue();
        Map<String, Object> row = rows.next();
        assertThat(row).containsEntry("name", "bob");
        assertThat(row.get("id")).hasToString("2");
        assertThat(rows.hasNext()).isFalse();
    }

    @Test
    void tableExistsTrueForCreatedTable() {
        // Two-part fqtn resolves against the warehouse's configured project id.
        assertThat(warehouse.tableExists(dataset + "." + table)).isTrue();
    }

    @Test
    void tableExistsFalseForMissingTable() {
        assertThat(warehouse.tableExists(dataset + ".no_such_table")).isFalse();
    }
}
