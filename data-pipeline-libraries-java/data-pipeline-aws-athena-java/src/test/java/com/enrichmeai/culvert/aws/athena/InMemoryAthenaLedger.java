package com.enrichmeai.culvert.aws.athena;

import com.enrichmeai.culvert.jobcontrol.JobStatus;
import software.amazon.awssdk.services.athena.AthenaClient;
import software.amazon.awssdk.services.athena.model.ColumnInfo;
import software.amazon.awssdk.services.athena.model.Datum;
import software.amazon.awssdk.services.athena.model.GetQueryExecutionRequest;
import software.amazon.awssdk.services.athena.model.GetQueryExecutionResponse;
import software.amazon.awssdk.services.athena.model.GetQueryResultsRequest;
import software.amazon.awssdk.services.athena.model.GetQueryResultsResponse;
import software.amazon.awssdk.services.athena.model.QueryExecution;
import software.amazon.awssdk.services.athena.model.QueryExecutionState;
import software.amazon.awssdk.services.athena.model.QueryExecutionStatus;
import software.amazon.awssdk.services.athena.model.ResultSet;
import software.amazon.awssdk.services.athena.model.ResultSetMetadata;
import software.amazon.awssdk.services.athena.model.Row;
import software.amazon.awssdk.services.athena.model.StartQueryExecutionRequest;
import software.amazon.awssdk.services.athena.model.StartQueryExecutionResponse;

import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.atomic.AtomicLong;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

/**
 * A stateful fake {@link AthenaClient} standing in for the
 * {@code job_control.pipeline_jobs} ledger: an append-only list of rows, read
 * back through whatever projection the submitted SQL asks for.
 *
 * <h2>Why it interprets the SQL instead of stubbing an answer</h2>
 *
 * <p>{@code AthenaWarehouseContractTest}'s mock returns the same row whatever
 * the query says, which is fine for a stateless warehouse stub and useless for a
 * projection: a shape test cannot tell a correct ranking from a broken one. This
 * class instead <strong>reads the ranking out of the submitted SQL</strong> —
 * {@link #comparatorFrom} parses the {@code ORDER BY} key list of the
 * {@code ranked} CTE into a comparator, taking the terminal status literals from
 * the SQL rather than assuming them. Change
 * {@code AthenaJobControlRepository.projection} and these tests change verdict.
 * An unrecognised ordering key, or a statement with no ranking at all, is
 * refused outright rather than guessed at, so deleting the projection fails the
 * suite instead of quietly passing it.
 *
 * <p>It never applies an {@code UPDATE} or a {@code DELETE} to itself — it
 * records the attempt instead, so a test can assert none was made (AD-2).
 *
 * <p>Its clock is a monotonic 1 ms tick, rendered in the same
 * {@code uuuu-MM-dd HH:mm:ss.SSS} shape Athena uses, so ordering is never
 * ambiguous and the repository's own timestamp parsing is exercised on the way
 * back.
 */
final class InMemoryAthenaLedger {

    /** Matches the {@code ranked} CTE's ORDER BY key list. */
    private static final Pattern ORDER_BY =
            Pattern.compile("PARTITION BY run_id ORDER BY (.*?)\\) AS rn FROM");
    private static final Pattern TERMINAL_FLAG =
            Pattern.compile("^CASE WHEN status IN \\((.*?)\\) THEN 0 ELSE 1 END$");
    private static final Pattern TERMINAL_TIME =
            Pattern.compile("^CASE WHEN status IN \\((.*?)\\) THEN updated_at END$");

    /** The end of the ranking CTE, and so the end of any filter inside it. */
    private static final String CTE_CLOSE = ") SELECT * FROM ranked";
    private static final Pattern LEDGER_FROM = Pattern.compile("AS rn FROM ([\\w.]+)");
    private static final Pattern OUTER_STATUS_IN =
            Pattern.compile("WHERE rn = 1 AND status IN \\((.*?)\\)");
    private static final Pattern OUTER_STATUS_EQ =
            Pattern.compile("WHERE rn = 1 AND status = '(.*?)'");
    /** {@code col = 'lit'} / {@code col = DATE 'lit'}, tolerating doubled quotes. */
    private static final Pattern PREDICATE =
            Pattern.compile("(\\w+) = (?:DATE )?'((?:[^']|'')*)'");

    private static final DateTimeFormatter TICK =
            DateTimeFormatter.ofPattern("uuuu-MM-dd HH:mm:ss.SSS").withZone(ZoneOffset.UTC);
    private static final Instant EPOCH_START = Instant.parse("2026-01-15T09:00:00Z");

    private final AthenaClient client = mock(AthenaClient.class);
    private final List<Map<String, String>> rows = new ArrayList<>();
    private final List<String> deletes = new ArrayList<>();
    private final List<String> updates = new ArrayList<>();
    /** Query-execution id -> the rows that execution's SELECT resolved to. */
    private final Map<String, List<Map<String, String>>> results = new LinkedHashMap<>();
    private final AtomicLong queryIds = new AtomicLong();
    private long clock;

    InMemoryAthenaLedger() {
        when(client.startQueryExecution(any(StartQueryExecutionRequest.class)))
                .thenAnswer(invocation -> {
                    StartQueryExecutionRequest request = invocation.getArgument(0);
                    String id = "fake-query-" + queryIds.incrementAndGet();
                    results.put(id, apply(request.queryString()));
                    return StartQueryExecutionResponse.builder().queryExecutionId(id).build();
                });

        when(client.getQueryExecution(any(GetQueryExecutionRequest.class)))
                .thenAnswer(invocation -> {
                    String id = ((GetQueryExecutionRequest) invocation.getArgument(0))
                            .queryExecutionId();
                    return GetQueryExecutionResponse.builder()
                            .queryExecution(QueryExecution.builder()
                                    .queryExecutionId(id)
                                    .status(QueryExecutionStatus.builder()
                                            .state(QueryExecutionState.SUCCEEDED)
                                            .build())
                                    .build())
                            .build();
                });

        when(client.getQueryResults(any(GetQueryResultsRequest.class)))
                .thenAnswer(invocation -> resultsFor(
                        ((GetQueryResultsRequest) invocation.getArgument(0)).queryExecutionId()));
    }

    AthenaClient client() {
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

    /**
     * Appends a row the repository would refuse to write — a stray writer, or
     * an event that arrived out of band. Copies the run's first row and changes
     * only the status, so the projection has something realistic to rank.
     */
    void appendRaw(String runId, JobStatus status) {
        Map<String, String> seed = new LinkedHashMap<>(rowsFor(runId).get(0));
        seed.put("status", status.getValue());
        seed.put("updated_at", tick());
        rows.add(seed);
    }

    private String tick() {
        return TICK.format(EPOCH_START.plus(Duration.ofMillis(++clock)));
    }

    // --- statement dispatch -------------------------------------------------

    private List<Map<String, String>> apply(String sql) {
        if (sql.startsWith("INSERT INTO")) {
            rows.add(rowFrom(sql));
            return List.of();
        }
        if (sql.startsWith("UPDATE ")) {
            updates.add(sql);
            return List.of();
        }
        if (sql.startsWith("DELETE ")) {
            deletes.add(sql);
            return List.of();
        }
        if (sql.startsWith("WITH ranked AS (")) {
            return project(sql);
        }
        throw new UnsupportedOperationException("fake ledger cannot run: " + sql);
    }

    // --- writes -------------------------------------------------------------

    /**
     * Parses {@code INSERT INTO t (cols) VALUES (…)} into a row. The repository
     * has no parameter binding to lean on (Athena offers none), so the literals
     * are all there is — which is also why this fake exercises the escaping.
     */
    private Map<String, String> rowFrom(String sql) {
        int columnsOpen = sql.indexOf('(');
        int columnsClose = sql.indexOf(')', columnsOpen);
        List<String> columns = List.of(sql.substring(columnsOpen + 1, columnsClose).split(",\\s*"));

        String valuesClause = sql.substring(sql.indexOf("VALUES (") + "VALUES (".length(),
                sql.lastIndexOf(')'));
        List<String> values = splitTopLevel(valuesClause);
        if (columns.size() != values.size()) {
            throw new IllegalStateException("INSERT column/value arity mismatch: "
                    + columns.size() + " vs " + values.size() + " in " + sql);
        }

        Map<String, String> row = new LinkedHashMap<>();
        for (int i = 0; i < columns.size(); i++) {
            row.put(columns.get(i), literalValue(values.get(i)));
        }
        return row;
    }

    /** Turns one SQL literal back into the value it encodes. */
    private String literalValue(String literal) {
        String value = literal.trim();
        if ("NULL".equals(value)) {
            return null;
        }
        if ("CAST(now() AS timestamp)".equals(value)) {
            // The server-side wall clock, supplied by the fake so that ordering
            // is monotonic and unambiguous.
            return tick();
        }
        if (value.startsWith("TIMESTAMP '") || value.startsWith("DATE '")) {
            value = value.substring(value.indexOf('\''));
        }
        if (value.startsWith("'") && value.endsWith("'")) {
            // Undo the doubling AthenaJobControlRepository.stringLiteral applies.
            return value.substring(1, value.length() - 1).replace("''", "'");
        }
        return value;
    }

    // --- reads --------------------------------------------------------------

    private List<Map<String, String>> project(String sql) {
        Matcher orderBy = ORDER_BY.matcher(sql);
        if (!orderBy.find()) {
            throw new UnsupportedOperationException("no ranking in: " + sql);
        }
        Comparator<Map<String, String>> ranking = comparatorFrom(orderBy.group(1));

        // 1. The immutable-column filter pushed inside the projection.
        List<Map<String, String>> scoped = new ArrayList<>();
        for (Map<String, String> row : rows) {
            if (matchesInnerFilter(sql, row)) {
                scoped.add(row);
            }
        }

        // 2. Rank each run's partition, keeping rn = 1.
        List<Map<String, String>> winners = new ArrayList<>();
        for (String runId : new LinkedHashSet<>(scoped.stream()
                .map(r -> r.get("run_id")).toList())) {
            List<Map<String, String>> partition = new ArrayList<>(
                    scoped.stream().filter(r -> runId.equals(r.get("run_id"))).toList());
            if (partition.isEmpty()) {
                continue;
            }
            partition.sort(ranking);
            winners.add(partition.get(0));
        }

        // 3. The status predicate, applied only after rn = 1.
        List<Map<String, String>> filtered = new ArrayList<>();
        for (Map<String, String> row : winners) {
            if (matchesOuterStatus(sql, row)) {
                filtered.add(row);
            }
        }

        if (sql.contains("ORDER BY created_at DESC")) {
            filtered.sort(Comparator.comparing((Map<String, String> r) -> r.get("created_at"))
                    .reversed());
        } else if (sql.contains("ORDER BY created_at")) {
            filtered.sort(Comparator.comparing(r -> r.get("created_at")));
        }
        if (sql.endsWith("LIMIT 1") && filtered.size() > 1) {
            filtered = List.of(filtered.get(0));
        }
        return filtered;
    }

    /**
     * Applies the immutable-column filter pushed inside the ranking CTE.
     *
     * <p>An absent {@code WHERE} means every partition is in scope — that is
     * {@code getPendingJobs(Optional.empty())}. A {@code WHERE} this fake cannot
     * fully account for is <strong>refused</strong>, never treated as absent:
     * silently widening a filtered scan to the whole ledger would turn a
     * scoping bug into a passing test.
     */
    private static boolean matchesInnerFilter(String sql, Map<String, String> row) {
        Matcher from = LEDGER_FROM.matcher(sql);
        if (!from.find()) {
            throw new UnsupportedOperationException("no ledger FROM clause in: " + sql);
        }
        int close = sql.indexOf(CTE_CLOSE, from.end());
        if (close < 0) {
            throw new UnsupportedOperationException(
                    "ranking CTE is not closed by \"" + CTE_CLOSE + "\": " + sql);
        }
        String clause = sql.substring(from.end(), close).trim();
        if (clause.isEmpty()) {
            return true;
        }
        if (!clause.startsWith("WHERE ")) {
            throw new UnsupportedOperationException(
                    "unparseable filter inside the projection: " + clause);
        }

        String predicates = clause.substring("WHERE ".length());
        List<String> recognised = new ArrayList<>();
        boolean matched = true;
        Matcher predicate = PREDICATE.matcher(predicates);
        while (predicate.find()) {
            recognised.add(predicate.group(0));
            // Undo the quote doubling stringLiteral applied before comparing.
            if (!predicate.group(2).replace("''", "'").equals(row.get(predicate.group(1)))) {
                matched = false;
            }
        }
        // Every conjunct must be accounted for; an unrecognised one is refused
        // rather than ignored, which would silently widen the filter.
        if (!String.join(" AND ", recognised).equals(predicates)) {
            throw new UnsupportedOperationException(
                    "unrecognised predicate inside the projection: " + predicates);
        }
        return matched;
    }

    private static boolean matchesOuterStatus(String sql, Map<String, String> row) {
        Matcher in = OUTER_STATUS_IN.matcher(sql);
        if (in.find()) {
            return literalSet(in.group(1)).contains(row.get("status"));
        }
        Matcher eq = OUTER_STATUS_EQ.matcher(sql);
        if (eq.find()) {
            return eq.group(1).equals(row.get("status"));
        }
        return true;
    }

    /**
     * Turns the CTE's {@code ORDER BY} key list into a comparator. Each key is
     * interpreted, not pattern-sniffed, so a changed ordering produces a changed
     * ranking rather than a silently unchanged one. An unrecognised key is
     * refused outright rather than ignored.
     */
    private static Comparator<Map<String, String>> comparatorFrom(String orderBy) {
        Comparator<Map<String, String>> ranking = null;
        for (String key : splitTopLevel(orderBy)) {
            Comparator<Map<String, String>> next = keyComparator(key.trim());
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
            ascending = Comparator.comparingInt(row -> terminal.contains(row.get("status")) ? 0 : 1);
        } else if (time.matches()) {
            Set<String> terminal = literalSet(time.group(1));
            // NULL for a non-terminal row. Trino sorts NULLs LAST on ASC; the
            // preceding key has already segregated terminal from non-terminal,
            // so this key only ever compares within one group and the choice is
            // not load-bearing.
            ascending = Comparator.comparing(
                    row -> terminal.contains(row.get("status")) ? row.get("updated_at") : null,
                    Comparator.nullsLast(Comparator.naturalOrder()));
        } else if ("updated_at".equals(key)) {
            ascending = Comparator.comparing(row -> row.get("updated_at"));
        } else {
            throw new UnsupportedOperationException("unknown ORDER BY key: " + rawKey);
        }
        return descending ? ascending.reversed() : ascending;
    }

    /** Splits on commas that are neither inside parentheses nor inside a literal. */
    private static List<String> splitTopLevel(String clause) {
        List<String> parts = new ArrayList<>();
        StringBuilder current = new StringBuilder();
        int depth = 0;
        boolean inLiteral = false;
        for (int i = 0; i < clause.length(); i++) {
            char c = clause.charAt(i);
            if (c == '\'') {
                // A doubled '' inside a literal is an escaped quote, not a close.
                if (inLiteral && i + 1 < clause.length() && clause.charAt(i + 1) == '\'') {
                    current.append("''");
                    i++;
                    continue;
                }
                inLiteral = !inLiteral;
            } else if (!inLiteral && c == '(') {
                depth++;
            } else if (!inLiteral && c == ')') {
                depth--;
            }
            if (c == ',' && depth == 0 && !inLiteral) {
                parts.add(current.toString().trim());
                current.setLength(0);
            } else {
                current.append(c);
            }
        }
        if (!current.toString().trim().isEmpty()) {
            parts.add(current.toString().trim());
        }
        return parts;
    }

    private static Set<String> literalSet(String literals) {
        Set<String> values = new LinkedHashSet<>();
        for (String literal : literals.split(",")) {
            values.add(literal.trim().replace("'", ""));
        }
        return values;
    }

    // --- Athena result shaping ----------------------------------------------

    /**
     * Athena echoes the column header names as row 0 of page 1, and
     * {@code AthenaWarehouse.streamRows} skips it — so the fake must emit one,
     * or the first real row is eaten.
     */
    private GetQueryResultsResponse resultsFor(String queryExecutionId) {
        List<Map<String, String>> resolved = results.getOrDefault(queryExecutionId, List.of());
        List<String> columns = resolved.isEmpty()
                ? List.of()
                : new ArrayList<>(resolved.get(0).keySet());

        ResultSetMetadata.Builder metadata = ResultSetMetadata.builder();
        List<ColumnInfo> columnInfo = new ArrayList<>();
        for (String column : columns) {
            columnInfo.add(ColumnInfo.builder().name(column).label(column).type("varchar").build());
        }
        metadata.columnInfo(columnInfo);

        List<Row> athenaRows = new ArrayList<>();
        if (!columns.isEmpty()) {
            List<Datum> header = new ArrayList<>();
            for (String column : columns) {
                header.add(Datum.builder().varCharValue(column).build());
            }
            athenaRows.add(Row.builder().data(header).build());
        }
        for (Map<String, String> row : resolved) {
            List<Datum> data = new ArrayList<>();
            for (String column : columns) {
                data.add(Datum.builder().varCharValue(row.get(column)).build());
            }
            athenaRows.add(Row.builder().data(data).build());
        }

        return GetQueryResultsResponse.builder()
                .resultSet(ResultSet.builder()
                        .resultSetMetadata(metadata.build())
                        .rows(athenaRows)
                        .build())
                .build();
    }
}
