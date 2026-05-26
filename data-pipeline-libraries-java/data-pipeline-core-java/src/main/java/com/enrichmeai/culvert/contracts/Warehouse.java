package com.enrichmeai.culvert.contracts;

import com.enrichmeai.culvert.schema.EntitySchema;

import java.util.Iterator;
import java.util.List;
import java.util.Map;

/**
 * Tabular query/load abstraction.
 *
 * <p>Deliberately conservative — only the operations every serious warehouse
 * supports. Cloud-specific operations (BigQuery clustering, partitioning,
 * BI Engine, slot-aware predicates; Redshift sortkeys; Snowflake clustering;
 * Synapse distribution) are exposed via a cloud-specific extension class in
 * the cloud module (e.g.
 * {@code com.enrichmeai.culvert.gcp.bigquery.BigQueryExtensions}).
 *
 * <p>Java mirror of the Python {@code Warehouse} Protocol. {@code fqtn}
 * (fully-qualified table name) is an opaque string; the warehouse parses it
 * according to its own conventions ({@code project.dataset.table} for
 * BigQuery, {@code database.schema.table} for Redshift/Snowflake).
 */
public interface Warehouse {

    /**
     * Execute a SELECT and stream rows as maps.
     *
     * <p>Implementations should not buffer the entire result in memory;
     * iterating the result must be lazy.
     *
     * @param sql    The SELECT statement.
     * @param params Named parameter bindings. May be empty.
     * @return Lazy iterator over row maps.
     */
    Iterator<Map<String, Object>> query(String sql, Map<String, Object> params);

    /**
     * Execute a DML/DDL statement that does not return rows (INSERT, UPDATE,
     * MERGE, CREATE, DROP, ALTER).
     */
    void execute(String sql, Map<String, Object> params);

    /**
     * Bulk-load an object at {@code uri} into {@code targetTable}.
     *
     * @param uri          A {@link BlobStore} URI ({@code gs://}, {@code s3://}). The
     *                     warehouse arranges access (same-cloud loads only).
     * @param targetTable  Fully-qualified table name.
     * @param schema       The target schema.
     * @return Number of rows loaded.
     */
    long loadFromUri(String uri, String targetTable, EntitySchema schema);

    /**
     * MERGE source into target on {@code keys}. Standard upsert semantics:
     * matched rows are updated, unmatched source rows are inserted, target
     * rows missing from source are left alone.
     *
     * @return Rows affected.
     */
    long merge(String sourceTable, String targetTable, List<String> keys);

    /**
     * Copy {@code sourceTable} to {@code targetTable}. Should be a
     * metadata-only operation where the warehouse supports it.
     *
     * @return Rows copied.
     */
    long copy(String sourceTable, String targetTable);

    /** Return true if a table at {@code fqtn} exists. */
    boolean tableExists(String fqtn);
}
