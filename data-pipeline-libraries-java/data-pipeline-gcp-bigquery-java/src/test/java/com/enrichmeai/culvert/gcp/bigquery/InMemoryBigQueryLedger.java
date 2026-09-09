package com.enrichmeai.culvert.gcp.bigquery;

import com.enrichmeai.culvert.jobcontrol.JobStatus;
import com.google.cloud.bigquery.BigQuery;
import com.google.cloud.bigquery.Field;
import com.google.cloud.bigquery.FieldValue;
import com.google.cloud.bigquery.FieldValueList;
import com.google.cloud.bigquery.Job;
import com.google.cloud.bigquery.JobInfo;
import com.google.cloud.bigquery.JobStatistics.QueryStatistics;
import com.google.cloud.bigquery.QueryJobConfiguration;
import com.google.cloud.bigquery.QueryParameterValue;
import com.google.cloud.bigquery.StandardSQLTypeName;
import com.google.cloud.bigquery.TableResult;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

/**
 * A fake job-control ledger: an append-only list of rows, read back through
 * whatever ranking the submitted SQL asks for.
 *
 * <p>It never applies an {@code UPDATE} or a {@code DELETE} to itself — it
 * records them instead, so a test can assert none was attempted.
 *
 * <p>The reason this is a behavioural fake rather than a stub: a mocked
 * BigQuery client returns whatever it was told to return no matter what the
 * query says, so a test built on one cannot tell a correct projection from a
 * broken one. This class instead <strong>reads the ranking out of the
 * submitted SQL</strong>, parsing the {@code ORDER BY} key list of
 * {@code BigQueryJobControlRepository.rankedCte} into a real comparator (see
 * {@link #comparatorFrom}) and ranking its rows with it. Change the ordering in
 * the repository and every test built on this fixture changes verdict — which
 * is the only way "the earliest terminal state wins" can be tested at unit
 * level at all.
 *
 * <p>It deliberately understands only the two reads its consumers need —
 * {@code getJob}'s outer query and {@code getPendingJobs}' — and both go
 * through the same parsed ranking. Any other projection consumer meets an
 * explicit refusal rather than a guess. The same holds inside a statement: an
 * unrecognised {@code ORDER BY} key or CTE filter is refused, never ignored.
 *
 * <p>Extracted from {@code BigQueryJobControlProjectionTest} so the projection
 * suite and {@link BigQueryJobControlContractTest} rank rows through one
 * implementation.
 */
final class InMemoryBigQueryLedger {

    private static final Pattern ORDER_BY =
            Pattern.compile("PARTITION BY run_id ORDER BY (.*?)\\) AS rn FROM");
    private static final Pattern TERMINAL_FLAG =
            Pattern.compile("^CASE WHEN status IN \\((.*?)\\) THEN 0 ELSE 1 END$");
    private static final Pattern TERMINAL_TIME =
            Pattern.compile("^CASE WHEN status IN \\((.*?)\\) THEN updated_at END$");

    /** The CTE's source table and its optional inside-the-ranking filter. */
    private static final Pattern CTE_SCOPE =
            Pattern.compile("\\) AS rn FROM \\S+(?: WHERE (.+?))?\\) SELECT ");
    /** {@code <immutable column> = @<param>} — the only filter shape modelled. */
    private static final Pattern SCOPE_FILTER =
            Pattern.compile("^(run_id|system_id|extract_date|job_type|pipeline_name) = @(\\w+)$");

    /** {@code getJob}: the whole projected row for one run. */
    private static final String GET_JOB_TAIL = "SELECT * FROM ranked WHERE rn = 1";
    /** {@code getPendingJobs}: the projected rows still in a pending state. */
    private static final String PENDING_TAIL =
            "SELECT * FROM ranked WHERE rn = 1 AND status IN (@created, @running) "
            + "ORDER BY created_at";

    private final BigQuery client = mock(BigQuery.class);
    private final List<Map<String, String>> rows = new ArrayList<>();
    private final List<String> deletes = new ArrayList<>();
    private final List<String> updates = new ArrayList<>();
    private long clock;

    InMemoryBigQueryLedger() throws InterruptedException {
        when(client.create(any(JobInfo.class))).thenAnswer(invocation -> {
            JobInfo info = invocation.getArgument(0);
            QueryJobConfiguration config = info.getConfiguration();
            return jobReporting(apply(config));
        });
        when(client.query(any(QueryJobConfiguration.class)))
                .thenAnswer(invocation -> project(invocation.getArgument(0)));
    }

    BigQuery client() {
        return client;
    }

    List<Map<String, String>> rowsFor(String runId) {
        return rows.stream().filter(r -> runId.equals(r.get("run_id"))).toList();
    }

    List<String> statusHistory(String runId) {
        return rowsFor(runId).stream().map(r -> r.get("status")).toList();
    }

    List<String> deletes() {
        return deletes;
    }

    List<String> updates() {
        return updates;
    }

    /** Appends a row the repository would refuse to write — a stray writer. */
    void appendRaw(String runId, JobStatus status) {
        Map<String, String> seed = new LinkedHashMap<>(rowsFor(runId).get(0));
        seed.put("status", status.getValue());
        seed.put("updated_at", String.valueOf(++clock));
        rows.add(seed);
    }

    // --- writes --------------------------------------------------------

    private long apply(QueryJobConfiguration config) {
        String sql = config.getQuery();
        if (sql.startsWith("INSERT INTO")) {
            rows.add(rowFrom(config));
            return 1L;
        }
        if (sql.startsWith("MERGE INTO")) {
            String runId = param(config, "run_id");
            if (!rowsFor(runId).isEmpty()) {
                return 0L;
            }
            rows.add(rowFrom(config));
            return 1L;
        }
        if (sql.startsWith("DELETE")) {
            deletes.add(sql);
            return 0L;
        }
        if (sql.startsWith("UPDATE")) {
            updates.add(sql);
            return 0L;
        }
        throw new UnsupportedOperationException("fake ledger cannot run: " + sql);
    }

    private Map<String, String> rowFrom(QueryJobConfiguration config) {
        Map<String, String> row = new LinkedHashMap<>();
        config.getNamedParameters().forEach((name, value) -> row.put(name, value.getValue()));
        // updated_at is stamped CURRENT_TIMESTAMP() by every writer, so the
        // fake supplies the clock. Monotonic, so ordering is unambiguous.
        row.put("updated_at", String.valueOf(++clock));
        return row;
    }

    // --- reads ---------------------------------------------------------

    /**
     * Runs one of the two supported reads: rank every partition in scope with
     * the ranking parsed out of this very statement, keep {@code rn = 1}, then
     * apply the outer query's own predicate.
     *
     * <p>{@code getPendingJobs}' trailing {@code ORDER BY created_at} is not
     * modelled — the fake's rows carry no server-stamped {@code created_at} —
     * so its rows come back in the order their runs first reached the ledger.
     * Nothing in the repository or its tests depends on that ordering; the
     * ranking <em>inside</em> the CTE, which they do depend on, is real.
     */
    private TableResult project(QueryJobConfiguration config) {
        String sql = config.getQuery();
        boolean pending = sql.endsWith(PENDING_TAIL);
        boolean getJob = !pending
                && sql.endsWith(GET_JOB_TAIL)
                && sql.contains("WHERE run_id = @run_id)");
        if (!pending && !getJob) {
            throw new UnsupportedOperationException(
                    "fake ledger only projects getJob and getPendingJobs; got: " + sql);
        }
        Matcher matcher = ORDER_BY.matcher(sql);
        if (!matcher.find()) {
            throw new UnsupportedOperationException("no ranking in: " + sql);
        }
        Comparator<Map<String, String>> ranking = comparatorFrom(matcher.group(1));

        List<Map<String, String>> projected = rankPartitions(scope(config, sql), ranking);
        if (pending) {
            Set<String> pendingStatuses =
                    Set.of(param(config, "created"), param(config, "running"));
            projected = projected.stream()
                    .filter(row -> pendingStatuses.contains(row.get("status")))
                    .toList();
        }
        TableResult result = mock(TableResult.class);
        when(result.iterateAll())
                .thenReturn(projected.stream().map(InMemoryBigQueryLedger::toFieldValues).toList());
        return result;
    }

    /**
     * The rows the CTE ranks: every row, less whatever its inside-the-ranking
     * filter removes. Only an equality on a column a state change carries
     * forward unchanged is modelled — such a predicate removes whole
     * partitions and cannot change which row wins inside one. Anything else
     * (a {@code status} predicate above all) is refused rather than guessed at,
     * because applying it here would silently model a different query from the
     * one the repository sent.
     */
    private List<Map<String, String>> scope(QueryJobConfiguration config, String sql) {
        Matcher cte = CTE_SCOPE.matcher(sql);
        if (!cte.find()) {
            throw new UnsupportedOperationException("no ranking CTE in: " + sql);
        }
        String filter = cte.group(1);
        if (filter == null) {
            return List.copyOf(rows);
        }
        Matcher predicate = SCOPE_FILTER.matcher(filter);
        if (!predicate.matches()) {
            throw new UnsupportedOperationException("unknown CTE filter: " + filter);
        }
        String column = predicate.group(1);
        String wanted = param(config, predicate.group(2));
        return rows.stream().filter(row -> Objects.equals(wanted, row.get(column))).toList();
    }

    /**
     * {@code ROW_NUMBER() OVER (PARTITION BY run_id ORDER BY …) … WHERE rn = 1}:
     * one winning row per run, chosen by the parsed ranking.
     */
    private static List<Map<String, String>> rankPartitions(
            List<Map<String, String>> scope, Comparator<Map<String, String>> ranking) {
        Map<String, List<Map<String, String>>> partitions = new LinkedHashMap<>();
        for (Map<String, String> row : scope) {
            partitions.computeIfAbsent(row.get("run_id"), key -> new ArrayList<>()).add(row);
        }
        List<Map<String, String>> winners = new ArrayList<>();
        partitions.values().forEach(partition -> {
            List<Map<String, String>> ranked = new ArrayList<>(partition);
            ranked.sort(ranking);
            winners.add(ranked.get(0));
        });
        return winners;
    }

    /**
     * Turns the CTE's {@code ORDER BY} key list into a comparator. Each key
     * is interpreted, not pattern-sniffed, so a changed ordering produces a
     * changed ranking rather than a silently unchanged one. An unrecognised
     * key is refused outright rather than ignored.
     */
    static Comparator<Map<String, String>> comparatorFrom(String orderBy) {
        Comparator<Map<String, String>> ranking = null;
        for (String key : splitKeys(orderBy)) {
            Comparator<Map<String, String>> next = keyComparator(key);
            ranking = ranking == null ? next : ranking.thenComparing(next);
        }
        if (ranking == null) {
            throw new UnsupportedOperationException("empty ORDER BY: " + orderBy);
        }
        return ranking;
    }

    private static Comparator<Map<String, String>> keyComparator(String rawKey) {
        String key = rawKey;
        boolean descending = false;
        if (key.endsWith(" DESC")) {
            key = key.substring(0, key.length() - " DESC".length());
            descending = true;
        } else if (key.endsWith(" ASC")) {
            key = key.substring(0, key.length() - " ASC".length());
        }

        Comparator<Map<String, String>> ascending;
        Matcher flag = TERMINAL_FLAG.matcher(key);
        Matcher time = TERMINAL_TIME.matcher(key);
        if (flag.matches()) {
            Set<String> terminal = literalSet(flag.group(1));
            ascending = Comparator.comparingInt(
                    row -> terminal.contains(row.get("status")) ? 0 : 1);
        } else if (time.matches()) {
            Set<String> terminal = literalSet(time.group(1));
            // NULL for a non-terminal row; BigQuery sorts NULLs first ASC.
            ascending = Comparator.comparing(
                    row -> terminal.contains(row.get("status"))
                            ? Long.valueOf(row.get("updated_at")) : null,
                    Comparator.nullsFirst(Comparator.naturalOrder()));
        } else if ("updated_at".equals(key)) {
            ascending = Comparator.comparingLong(row -> Long.parseLong(row.get("updated_at")));
        } else {
            throw new UnsupportedOperationException("unknown ORDER BY key: " + rawKey);
        }
        return descending ? ascending.reversed() : ascending;
    }

    /** Splits an ORDER BY list on commas that are not inside parentheses. */
    private static List<String> splitKeys(String orderBy) {
        List<String> keys = new ArrayList<>();
        int depth = 0;
        StringBuilder current = new StringBuilder();
        for (char c : orderBy.toCharArray()) {
            if (c == '(') {
                depth++;
            } else if (c == ')') {
                depth--;
            }
            if (c == ',' && depth == 0) {
                keys.add(current.toString().trim());
                current.setLength(0);
            } else {
                current.append(c);
            }
        }
        if (current.toString().trim().length() > 0) {
            keys.add(current.toString().trim());
        }
        return keys;
    }

    private static Set<String> literalSet(String literals) {
        Set<String> values = new LinkedHashSet<>();
        for (String literal : literals.split(",")) {
            values.add(literal.trim().replace("'", ""));
        }
        return values;
    }

    private static String param(QueryJobConfiguration config, String name) {
        QueryParameterValue value = config.getNamedParameters().get(name);
        return value == null ? null : value.getValue();
    }

    /** Only the non-timestamp columns; the mapper tolerates the rest missing. */
    private static FieldValueList toFieldValues(Map<String, String> row) {
        List<Field> fields = new ArrayList<>();
        List<FieldValue> values = new ArrayList<>();
        row.forEach((name, value) -> {
            if (name.endsWith("_at")) {
                return;
            }
            fields.add(Field.of(name, StandardSQLTypeName.STRING));
            values.add(FieldValue.of(FieldValue.Attribute.PRIMITIVE, value));
        });
        return FieldValueList.of(values, fields.toArray(new Field[0]));
    }

    private static Job jobReporting(long affectedRows) throws InterruptedException {
        QueryStatistics stats = mock(QueryStatistics.class);
        when(stats.getNumDmlAffectedRows()).thenReturn(affectedRows);
        Job completed = mock(Job.class);
        when(completed.getStatistics()).thenReturn(stats);
        Job submitted = mock(Job.class);
        when(submitted.waitFor()).thenReturn(completed);
        return submitted;
    }
}
