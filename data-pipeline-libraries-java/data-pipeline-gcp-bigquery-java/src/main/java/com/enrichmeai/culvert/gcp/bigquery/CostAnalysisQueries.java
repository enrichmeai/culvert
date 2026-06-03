package com.enrichmeai.culvert.gcp.bigquery;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Objects;

/**
 * Loads named SQL blocks from the {@code cost_analysis.sql} resource file.
 *
 * <h2>SQL pack location</h2>
 * <p>The SQL file lives at
 * {@code com/enrichmeai/culvert/gcp/bigquery/sql/cost_analysis.sql} on the
 * classpath (inside this module's jar). Each block is delimited by a line of
 * the form {@code -- query: <name>}; the block extends from the line after
 * that marker to the next such marker (or end-of-file).
 *
 * <h2>Available query names</h2>
 * <ul>
 *   <li>{@code cost_by_run} — total estimated USD + slot-ms grouped by
 *       {@code run_id}, ordered by cost DESC.</li>
 *   <li>{@code cost_by_stage} — total estimated USD grouped by the
 *       {@code stage} label key (requires the {@code labels} array to be
 *       UNNESTed), ordered by cost DESC.</li>
 *   <li>{@code top_expensive_runs_7d} — top 10 {@code run_id}s by cost in
 *       the last 7 days.</li>
 *   <li>{@code budget_breach_log} — all rows where
 *       {@code estimated_cost_usd > ?} (positional parameter), ordered by
 *       {@code timestamp} DESC. Bind the ceiling value before executing.</li>
 * </ul>
 *
 * <h2>Usage</h2>
 * <pre>{@code
 * String sql = CostAnalysisQueries.loadQuery("cost_by_run");
 * // sql is a ready-to-use BigQuery Standard SQL string
 * }</pre>
 *
 * <p>Sprint-13 deliverable for issue <a href="https://github.com/enrichmeai/culvert/issues/72">#72</a> (T13.4).
 */
public final class CostAnalysisQueries {

    private static final String SQL_RESOURCE = "sql/cost_analysis.sql";
    private static final String QUERY_MARKER_PREFIX = "-- query: ";

    /**
     * Map of name → SQL body, loaded once at class-init from the classpath resource.
     * Loading eagerly keeps {@link #loadQuery} free of checked exceptions.
     */
    private static final Map<String, String> QUERIES;

    static {
        QUERIES = parseResource();
    }

    private CostAnalysisQueries() {
        throw new AssertionError("utility class — do not instantiate");
    }

    /**
     * Returns the SQL body for the named query block.
     *
     * @param name One of {@code cost_by_run}, {@code cost_by_stage},
     *             {@code top_expensive_runs_7d}, or {@code budget_breach_log}.
     * @return The SQL string for the named block (trimmed, non-empty).
     * @throws IllegalArgumentException if {@code name} is not recognised.
     * @throws NullPointerException     if {@code name} is null.
     */
    public static String loadQuery(String name) {
        Objects.requireNonNull(name, "query name must not be null");
        String sql = QUERIES.get(name);
        if (sql == null) {
            throw new IllegalArgumentException(
                    "Unknown cost-analysis query: '" + name + "'. "
                            + "Available: " + QUERIES.keySet());
        }
        return sql;
    }

    // --- internal -----------------------------------------------------------

    private static Map<String, String> parseResource() {
        InputStream stream = CostAnalysisQueries.class.getResourceAsStream(SQL_RESOURCE);
        if (stream == null) {
            throw new IllegalStateException(
                    "cost_analysis.sql not found on classpath at: "
                            + CostAnalysisQueries.class.getPackageName().replace('.', '/')
                            + "/" + SQL_RESOURCE);
        }
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(stream, StandardCharsets.UTF_8))) {
            return parse(reader);
        } catch (IOException e) {
            throw new IllegalStateException("Failed to read cost_analysis.sql", e);
        }
    }

    private static Map<String, String> parse(BufferedReader reader) throws IOException {
        Map<String, String> queries = new LinkedHashMap<>();
        String currentName = null;
        StringBuilder currentBody = new StringBuilder();

        String line;
        while ((line = reader.readLine()) != null) {
            if (line.startsWith(QUERY_MARKER_PREFIX)) {
                // Flush previous block before starting a new one.
                if (currentName != null) {
                    queries.put(currentName, currentBody.toString().trim());
                }
                currentName = line.substring(QUERY_MARKER_PREFIX.length()).trim();
                currentBody = new StringBuilder();
            } else if (currentName != null) {
                currentBody.append(line).append('\n');
            }
            // Lines before the first marker (file-level comments) are ignored.
        }

        // Flush the last block.
        if (currentName != null) {
            queries.put(currentName, currentBody.toString().trim());
        }
        return queries;
    }
}
