package com.enrichmeai.culvert.gcp.bigquery;

import com.enrichmeai.culvert.jobcontrol.FailureStage;
import com.enrichmeai.culvert.jobcontrol.JobStatus;
import com.enrichmeai.culvert.jobcontrol.JobType;
import com.enrichmeai.culvert.jobcontrol.PipelineJob;
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
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

/**
 * AD-12's behavioural suite: the append-only guarantees, asserted through
 * behaviour rather than through the text of the SQL.
 *
 * <p>{@link BigQueryJobControlRepositoryTest} pins the SQL's shape, but a
 * mocked client returns whatever it was told to return no matter what the query
 * says — so a shape test cannot tell a correct projection from a broken one.
 * The fake here closes that hole: it holds the rows the repository appends and
 * <strong>reads the ranking out of the submitted SQL</strong>, parsing the
 * {@code ORDER BY} key list of the CTE into a comparator (see
 * {@link Ledger#comparatorFrom}). Change the ordering in
 * {@code BigQueryJobControlRepository.rankedCte} and these tests change
 * verdict — which is the only way "the earliest terminal state wins" can be
 * tested at unit level at all.
 *
 * <p>The fake deliberately understands only {@code getJob}'s outer query. Any
 * other projection consumer meets an explicit refusal rather than a guess.
 */
class BigQueryJobControlProjectionTest {

    private static final String PROJECT = "my-project";
    private static final String DATASET = "job_control";
    private static final String TABLE = "pipeline_jobs";

    private Ledger ledger;
    private BigQueryJobControlRepository repo;

    @BeforeEach
    void setUp() throws InterruptedException {
        ledger = new Ledger();
        repo = new BigQueryJobControlRepository(ledger.client(), PROJECT, DATASET, TABLE);
    }

    private PipelineJob newJob() {
        return PipelineJob.builder("run-1", "system-A", "customer-ingest",
                        LocalDate.of(2026, 1, 15), JobStatus.CREATED)
                .jobType(JobType.INGESTION)
                .entityType("customer")
                .targetTable("my-project.warehouse.customers")
                .build();
    }

    /** Drives a run as far as {@code SUCCEEDED} through the repository itself. */
    private void runToSuccess() {
        repo.createJob(newJob());
        repo.updateStatus("run-1", JobStatus.RUNNING, Optional.empty());
        repo.updateStatus("run-1", JobStatus.SUCCEEDED, Optional.of(1_000L));
    }

    // --- AD-12, guarantee 1: failure-then-success reads FAILED --------------

    /**
     * A run that failed and then had a success row land after it reads
     * {@code FAILED}. Nothing was overwritten to achieve that — both rows are
     * in the ledger and the projection picks the earlier terminal one.
     */
    @Test
    void appendFailureThenSuccessReadsFailed() {
        repo.createJob(newJob());
        repo.updateStatus("run-1", JobStatus.RUNNING, Optional.empty());
        repo.markFailed("run-1", "E001", "reconciliation mismatch",
                FailureStage.VALIDATION, Optional.empty());
        // A success event landing after the failure: the control-flow defect
        // the external review found (a runner reporting success after already
        // having marked the run failed). It cannot go through updateStatus,
        // which rejects it — so it is appended the way a stray writer would.
        ledger.appendRaw("run-1", JobStatus.SUCCEEDED);

        assertThat(repo.getJob("run-1")).get()
                .extracting(PipelineJob::status).isEqualTo(JobStatus.FAILED);
        assertThat(ledger.rowsFor("run-1")).hasSize(4);
    }

    // --- AD-12, guarantee 2: the data-loss guard ---------------------------

    /**
     * The guard the whole design exists for. A succeeded run with a LATE
     * failure row still reads {@code SUCCEEDED}, so it is not retryable, so
     * {@link RetryOrchestrator} never reaches {@code cleanupPartialLoad} — the
     * {@code DELETE FROM <targetTable> WHERE _run_id} that would erase the rows
     * the successful run had just loaded.
     *
     * <p>This test fails if terminal precedence is removed: under plain
     * recency the late {@code failed} row wins, {@code FAILED} is retryable,
     * and the delete goes through.
     */
    @Test
    void appendSuccessThenLateFailureReadsSucceededAndIsNotRetryable() {
        runToSuccess();
        ledger.appendRaw("run-1", JobStatus.FAILED);

        assertThat(repo.getJob("run-1")).get()
                .extracting(PipelineJob::status).isEqualTo(JobStatus.SUCCEEDED);

        assertThatThrownBy(() -> new RetryOrchestrator(repo).prepareRetry("run-1"))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("SUCCEEDED")
                .hasMessageContaining("Nothing was deleted.");
        assertThat(ledger.deletes()).isEmpty();
    }

    /** The same guarantee, one layer down: the ledger itself is never mutated. */
    @Test
    void everyStateChangeAddsARowAndRemovesNone() {
        runToSuccess();
        repo.updateCostMetrics("run-1", 4.25, 100L, 200L);

        assertThat(ledger.rowsFor("run-1")).hasSize(4);
        assertThat(ledger.statusHistory("run-1"))
                .containsExactly("created", "running", "succeeded", "succeeded");
        assertThat(ledger.deletes()).isEmpty();
        assertThat(ledger.updates()).isEmpty();
    }

    // --- AD-12, guarantee 3: illegal transitions still throw ---------------

    @Test
    void aTransitionOutOfATerminalStateIsStillRejected() {
        runToSuccess();

        assertThatThrownBy(() -> repo.markRetrying("run-1", 1))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("SUCCEEDED")
                .hasMessageContaining("expected one of");
        assertThatThrownBy(() -> repo.markFailed("run-1", "E001", "too late",
                FailureStage.LOAD, Optional.empty()))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("SUCCEEDED");
        assertThatThrownBy(() -> repo.updateStatus("run-1", JobStatus.RUNNING, Optional.empty()))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("expected one of");

        // Three rejections, and not one of them reached the ledger.
        assertThat(ledger.rowsFor("run-1")).hasSize(3);
    }

    @Test
    void createJobRefusesASecondHistoryForTheSameRun() {
        repo.createJob(newJob());

        assertThatThrownBy(() -> repo.createJob(newJob()))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("already exists");
        assertThat(ledger.rowsFor("run-1")).hasSize(1);
    }

    // --- the projection's other two rules ----------------------------------

    /** With no terminal row, the projection falls back to the latest row. */
    @Test
    void beforeTerminalTheLatestRowWins() {
        repo.createJob(newJob());
        repo.updateStatus("run-1", JobStatus.RUNNING, Optional.empty());
        repo.markFailed("run-1", "E001", "first", FailureStage.VALIDATION, Optional.empty());
        // `failed` is terminal, so back the run out and check the pre-terminal
        // rule on a separate run instead.
        repo.createJob(PipelineJob.builder("run-2", "system-A", "customer-ingest",
                LocalDate.of(2026, 1, 15), JobStatus.CREATED).build());
        repo.updateStatus("run-2", JobStatus.RUNNING, Optional.empty());
        repo.markRetrying("run-2", 1);

        assertThat(repo.getJob("run-2")).get()
                .extracting(PipelineJob::status).isEqualTo(JobStatus.RETRYING);
        assertThat(repo.getJob("run-1")).get()
                .extracting(PipelineJob::status).isEqualTo(JobStatus.FAILED);
    }

    /**
     * The consequence of AD-3 rule 1 that deserves to be deliberate rather than
     * discovered: cost metrics recorded after a run has finished are appended
     * to the ledger but never win the projection, so they do not read back
     * through this class. Documented on
     * {@code BigQueryJobControlRepository.updateCostMetrics}.
     */
    @Test
    void costMetricsRecordedAfterATerminalStateAreWriteOnly() {
        runToSuccess();

        repo.updateCostMetrics("run-1", 99.99, 1_000L, 2_000L);

        assertThat(repo.getJob("run-1")).get()
                .extracting(PipelineJob::estimatedCostUsd).isEqualTo(0.0);
        // The row is in the ledger; it just is not the projected one.
        assertThat(ledger.rowsFor("run-1")).hasSize(4);
        assertThat(ledger.rowsFor("run-1").get(3).get("estimated_cost_usd")).isEqualTo("99.99");
    }

    /** Recorded before the run finishes, the same call reads back. */
    @Test
    void costMetricsRecordedBeforeTheRunFinishesReadBack() {
        repo.createJob(newJob());
        repo.updateStatus("run-1", JobStatus.RUNNING, Optional.empty());

        repo.updateCostMetrics("run-1", 99.99, 1_000L, 2_000L);

        assertThat(repo.getJob("run-1")).get()
                .extracting(PipelineJob::estimatedCostUsd).isEqualTo(99.99);
    }

    // =======================================================================

    /**
     * A fake job-control ledger: an append-only list of rows, read back through
     * whatever ranking the submitted SQL asks for.
     *
     * <p>It never applies an {@code UPDATE} or a {@code DELETE} to itself — it
     * records them instead, so a test can assert none was attempted.
     */
    private static final class Ledger {

        private static final Pattern ORDER_BY =
                Pattern.compile("PARTITION BY run_id ORDER BY (.*?)\\) AS rn FROM");
        private static final Pattern TERMINAL_FLAG =
                Pattern.compile("^CASE WHEN status IN \\((.*?)\\) THEN 0 ELSE 1 END$");
        private static final Pattern TERMINAL_TIME =
                Pattern.compile("^CASE WHEN status IN \\((.*?)\\) THEN updated_at END$");

        private final BigQuery client = mock(BigQuery.class);
        private final List<Map<String, String>> rows = new ArrayList<>();
        private final List<String> deletes = new ArrayList<>();
        private final List<String> updates = new ArrayList<>();
        private long clock;

        Ledger() throws InterruptedException {
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

        private TableResult project(QueryJobConfiguration config) {
            String sql = config.getQuery();
            if (!sql.endsWith("SELECT * FROM ranked WHERE rn = 1")
                    || !sql.contains("WHERE run_id = @run_id)")) {
                throw new UnsupportedOperationException(
                        "fake ledger only projects getJob; got: " + sql);
            }
            Matcher matcher = ORDER_BY.matcher(sql);
            if (!matcher.find()) {
                throw new UnsupportedOperationException("no ranking in: " + sql);
            }
            Comparator<Map<String, String>> ranking = comparatorFrom(matcher.group(1));

            List<Map<String, String>> partition =
                    new ArrayList<>(rowsFor(param(config, "run_id")));
            partition.sort(ranking);
            List<FieldValueList> winner = partition.isEmpty()
                    ? List.of()
                    : List.of(toFieldValues(partition.get(0)));

            TableResult result = mock(TableResult.class);
            when(result.iterateAll()).thenReturn(winner);
            return result;
        }

        /**
         * Turns the CTE's {@code ORDER BY} key list into a comparator. Each key
         * is interpreted, not pattern-sniffed, so a changed ordering produces a
         * changed ranking rather than a silently unchanged one. An unrecognised
         * key is refused outright rather than ignored.
         */
        private static Comparator<Map<String, String>> comparatorFrom(String orderBy) {
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
}
