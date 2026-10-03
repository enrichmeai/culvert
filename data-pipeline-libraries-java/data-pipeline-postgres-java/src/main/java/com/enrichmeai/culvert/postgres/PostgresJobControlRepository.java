package com.enrichmeai.culvert.postgres;

import com.enrichmeai.culvert.contracts.JobControlRepository;
import com.enrichmeai.culvert.jobcontrol.EntityStatus;
import com.enrichmeai.culvert.jobcontrol.FailedJob;
import com.enrichmeai.culvert.jobcontrol.FailureStage;
import com.enrichmeai.culvert.jobcontrol.FdpJobStatus;
import com.enrichmeai.culvert.jobcontrol.JobStatus;
import com.enrichmeai.culvert.jobcontrol.JobType;
import com.enrichmeai.culvert.jobcontrol.PipelineJob;
import org.postgresql.ds.PGSimpleDataSource;

import javax.sql.DataSource;
import java.sql.Connection;
import java.sql.Date;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Types;
import java.time.Instant;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.EnumSet;
import java.util.List;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;
import java.util.regex.Pattern;

/**
 * {@link JobControlRepository} on PostgreSQL, in plain JDBC. Runs the same on Cloud SQL, RDS or a
 * self-hosted server. Apply {@code job_control.sql} (shipped next to this class) once per
 * database before use.
 *
 * <h2>Append-only, like every other backend (AD-2)</h2>
 * <p>{@code job_control.pipeline_jobs} holds one row per state change. Nothing here
 * {@code UPDATE}s or {@code DELETE}s the ledger. Each transition reads the run's projected state,
 * carries it forward with its own change, and {@code INSERT}s the result with
 * {@code updated_at = clock_timestamp()}. A transactional store does not mean mutating a row in
 * place: the semantics are the BigQuery reference's (BigQueryJobControlRepository.java:726,
 * {@code rankedCte}).
 *
 * <h2>Reads are a projection; the first terminal state is final (AD-3)</h2>
 * <p>Every read ranks a run's rows with {@code ROW_NUMBER() OVER (PARTITION BY run_id ...)}:
 * a terminal row ({@code succeeded}, {@code failed}, {@code cancelled}) beats a non-terminal one,
 * the earliest terminal row wins, and with no terminal row the latest row wins. {@code seq}
 * (ledger order) breaks {@code updated_at} ties. Only immutable columns are filtered inside the
 * ranking; status filters go outside it, after {@code rn = 1}.
 *
 * <h2>What PostgreSQL adds</h2>
 * <ul>
 *   <li>{@link #createJob} is rejected by the server for a {@code runId} that already exists: a
 *       partial unique index allows one {@code opens_run} row per run (SQLSTATE 23505), like
 *       BigQuery's {@code MERGE} and DynamoDB's {@code attribute_not_exists}, and unlike Athena's
 *       plain {@code INSERT} (JobControlRepository.java:39-46).
 *   <li>Each transition runs in one transaction that first locks the run's opening row
 *       ({@code SELECT ... FOR UPDATE}), so two writers racing the same transition are serialised:
 *       the second reads the first's result and is rejected by the guard. On the other backends
 *       read-then-append is not atomic. This is a property of the adapter, not a contract method.
 *       The transition runs at READ COMMITTED whatever the connection's default, because the
 *       guard must see the previous writer's commit once the lock is granted; the connection's
 *       autocommit and isolation are restored before it is closed (or returned to a pool).
 * </ul>
 *
 * <p>{@link #cleanupPartialLoad} is the only {@code DELETE}, and it targets the caller's
 * warehouse table, never the ledger.
 */
public final class PostgresJobControlRepository implements JobControlRepository {

    /** The table {@code job_control.sql} creates. */
    public static final String DEFAULT_TABLE = "job_control.pipeline_jobs";

    private static final Set<JobStatus> TERMINAL_STATES =
            EnumSet.of(JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED);
    private static final String IS_TERMINAL = "status IN ('succeeded','failed','cancelled')";
    private static final Pattern QUALIFIED_NAME =
            Pattern.compile("[A-Za-z_][A-Za-z0-9_]*(\\.[A-Za-z_][A-Za-z0-9_]*)?");
    private static final String UNIQUE_VIOLATION = "23505";

    private static final String LEDGER_COLUMNS =
            "run_id, opens_run, system_id, pipeline_name, extract_date, status, job_type, "
            + "entity_type, source_file, target_table, record_count, error_count, retry_count, "
            + "failure_stage, error_code, error_message, error_file_path, "
            + "estimated_cost_usd, billed_bytes_scanned, billed_bytes_written, "
            + "created_at, updated_at, started_at, completed_at";

    private final DataSource dataSource;
    private final String table;

    /** A repository over {@link #DEFAULT_TABLE}. */
    public PostgresJobControlRepository(DataSource dataSource) {
        this(dataSource, DEFAULT_TABLE);
    }

    /**
     * @param table {@code schema.table} or {@code table}: letters, digits and underscores only
     */
    public PostgresJobControlRepository(DataSource dataSource, String table) {
        this.dataSource = Objects.requireNonNull(dataSource, "dataSource must not be null");
        this.table = quote(Objects.requireNonNull(table, "table must not be null"));
    }

    /**
     * The {@code ServiceLoader} constructor. Reads {@code CULVERT_POSTGRES_URL} (a
     * {@code jdbc:postgresql://} URL), {@code CULVERT_POSTGRES_USER},
     * {@code CULVERT_POSTGRES_PASSWORD} and {@code CULVERT_POSTGRES_JOB_CONTROL_TABLE} (default
     * {@link #DEFAULT_TABLE}), or the {@code culvert.postgres.*} system properties.
     *
     * @throws IllegalStateException if no URL is set
     */
    public PostgresJobControlRepository() {
        this(dataSourceFromEnvironment(),
                setting("CULVERT_POSTGRES_JOB_CONTROL_TABLE", "culvert.postgres.job_control_table")
                        .orElse(DEFAULT_TABLE));
    }

    private static DataSource dataSourceFromEnvironment() {
        String url = setting("CULVERT_POSTGRES_URL", "culvert.postgres.url").orElseThrow(() ->
                new IllegalStateException("PostgresJobControlRepository needs CULVERT_POSTGRES_URL "
                        + "(or -Dculvert.postgres.url), a jdbc:postgresql:// URL"));
        PGSimpleDataSource ds = new PGSimpleDataSource();
        ds.setURL(url);
        setting("CULVERT_POSTGRES_USER", "culvert.postgres.user").ifPresent(ds::setUser);
        setting("CULVERT_POSTGRES_PASSWORD", "culvert.postgres.password").ifPresent(ds::setPassword);
        return ds;
    }

    private static Optional<String> setting(String env, String property) {
        String v = System.getenv(env);
        if (v == null || v.isBlank()) {
            v = System.getProperty(property);
        }
        return v == null || v.isBlank() ? Optional.empty() : Optional.of(v);
    }

    static String quote(String qualifiedName) {
        if (!QUALIFIED_NAME.matcher(qualifiedName).matches()) {
            throw new IllegalArgumentException("not a plain [schema.]table name: " + qualifiedName);
        }
        StringBuilder out = new StringBuilder();
        for (String part : qualifiedName.split("\\.")) {
            if (out.length() > 0) {
                out.append('.');
            }
            out.append('"').append(part).append('"');
        }
        return out.toString();
    }

    // ---------------------------------------------------------------- writes

    @Override
    public void createJob(PipelineJob job) {
        Objects.requireNonNull(job, "job must not be null");
        try (Connection c = dataSource.getConnection()) {
            insert(c, job, true, false, false);
        } catch (SQLException e) {
            if (UNIQUE_VIOLATION.equals(e.getSQLState())) {
                throw new IllegalStateException(
                        "createJob rejected: a job with runId=" + job.runId() + " already exists", e);
            }
            throw failure("createJob", e);
        }
    }

    @Override
    public void updateStatus(String runId, JobStatus status, Optional<Long> totalRecords) {
        Objects.requireNonNull(runId, "runId must not be null");
        Objects.requireNonNull(status, "status must not be null");
        Objects.requireNonNull(totalRecords, "totalRecords must not be null");
        transition("updateStatus", runId, allowedPriorStates(status), current -> {
            PipelineJob.Builder next = carryForward(current, status);
            if (status == JobStatus.SUCCEEDED) {
                next.recordCount(totalRecords.orElse(0L));
            }
            return new Append(next.build(), status == JobStatus.RUNNING,
                    status == JobStatus.SUCCEEDED);
        });
    }

    @Override
    public void markFailed(String runId, String errorCode, String errorMessage,
                           FailureStage failureStage, Optional<String> errorFilePath) {
        Objects.requireNonNull(runId, "runId must not be null");
        Objects.requireNonNull(errorCode, "errorCode must not be null");
        Objects.requireNonNull(errorMessage, "errorMessage must not be null");
        Objects.requireNonNull(failureStage, "failureStage must not be null");
        Objects.requireNonNull(errorFilePath, "errorFilePath must not be null");
        transition("markFailed", runId, allowedPriorStates(JobStatus.FAILED), current ->
                new Append(carryForward(current, JobStatus.FAILED)
                        .errorCode(errorCode)
                        .errorMessage(errorMessage)
                        .failureStage(failureStage)
                        .errorFilePath(errorFilePath.orElse(null))
                        .build(), false, true));
    }

    @Override
    public void markRetrying(String runId, int retryCount) {
        Objects.requireNonNull(runId, "runId must not be null");
        if (retryCount < 0) {
            throw new IllegalArgumentException("retryCount must be >= 0, got " + retryCount);
        }
        transition("markRetrying", runId, allowedPriorStates(JobStatus.RETRYING), current ->
                new Append(carryForward(current, JobStatus.RETRYING).retryCount(retryCount).build(),
                        false, false));
    }

    @Override
    public void updateCostMetrics(String runId, double estimatedCostUsd,
                                  long billedBytesScanned, long billedBytesWritten) {
        Objects.requireNonNull(runId, "runId must not be null");
        // Like the reference: on a run already terminal, the appended row never wins the
        // projection, so the new figures are in the ledger but do not read back.
        transition("updateCostMetrics", runId, EnumSet.allOf(JobStatus.class), current ->
                new Append(carryForward(current, current.status())
                        .estimatedCostUsd(estimatedCostUsd)
                        .billedBytesScanned(billedBytesScanned)
                        .billedBytesWritten(billedBytesWritten)
                        .build(), false, false));
    }

    @Override
    public int cleanupPartialLoad(String runId, String tableId) {
        Objects.requireNonNull(runId, "runId must not be null");
        Objects.requireNonNull(tableId, "tableId must not be null");
        String sql = "DELETE FROM " + quote(tableId) + " WHERE _run_id = ?";
        try (Connection c = dataSource.getConnection(); PreparedStatement ps = c.prepareStatement(sql)) {
            ps.setString(1, runId);
            return ps.executeUpdate();
        } catch (SQLException e) {
            throw failure("cleanupPartialLoad", e);
        }
    }

    private record Append(PipelineJob job, boolean stampStartedNow, boolean stampCompletedNow) {
    }

    private interface Change {
        Append apply(PipelineJob current);
    }

    /** Lock the run, check its projected state, append the change: one transaction. */
    private void transition(String op, String runId, Set<JobStatus> allowed, Change change) {
        try (Connection c = dataSource.getConnection()) {
            boolean autoCommit = c.getAutoCommit();
            int isolation = c.getTransactionIsolation();
            c.setAutoCommit(false);
            c.setTransactionIsolation(Connection.TRANSACTION_READ_COMMITTED);
            try {
                if (!lockRun(c, runId)) {
                    throw new IllegalStateException(op + " rejected: no job with runId=" + runId);
                }
                PipelineJob current = project(c, "run_id = ?", List.of(runId), "", List.of())
                        .stream().findFirst().orElseThrow(() -> new IllegalStateException(
                                op + " rejected: no job with runId=" + runId));
                if (!allowed.contains(current.status())) {
                    throw new IllegalStateException(op + " rejected: job runId=" + runId + " is "
                            + current.status() + ", expected one of " + allowed);
                }
                Append next = change.apply(current);
                insert(c, next.job(), false, next.stampStartedNow(), next.stampCompletedNow());
                c.commit();
            } catch (RuntimeException | SQLException | Error e) {
                try {
                    c.rollback();
                } catch (SQLException rollbackFailed) {
                    e.addSuppressed(rollbackFailed);
                }
                throw e;
            } finally {
                c.setTransactionIsolation(isolation);
                c.setAutoCommit(autoCommit);
            }
        } catch (SQLException e) {
            throw failure(op, e);
        }
    }

    private boolean lockRun(Connection c, String runId) throws SQLException {
        String sql = "SELECT 1 FROM " + table + " WHERE run_id = ? AND opens_run FOR UPDATE";
        try (PreparedStatement ps = c.prepareStatement(sql)) {
            ps.setString(1, runId);
            try (ResultSet rs = ps.executeQuery()) {
                return rs.next();
            }
        }
    }

    private void insert(Connection c, PipelineJob job, boolean opensRun,
                        boolean stampStartedNow, boolean stampCompletedNow) throws SQLException {
        String sql = "INSERT INTO " + table + " (" + LEDGER_COLUMNS + ") VALUES ("
                + "?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
                + (opensRun ? "clock_timestamp()" : "?") + ", clock_timestamp(), "
                + (stampStartedNow ? "clock_timestamp()" : "?") + ", "
                + (stampCompletedNow ? "clock_timestamp()" : "?") + ")";
        try (PreparedStatement ps = c.prepareStatement(sql)) {
            int i = 1;
            ps.setString(i++, job.runId());
            ps.setBoolean(i++, opensRun);
            ps.setString(i++, job.systemId());
            ps.setString(i++, job.pipelineName());
            ps.setDate(i++, Date.valueOf(job.extractDate()));
            ps.setString(i++, job.status().getValue());
            ps.setString(i++, job.jobType().name());
            setText(ps, i++, job.entityType());
            setText(ps, i++, job.sourceFile());
            setText(ps, i++, job.targetTable());
            ps.setLong(i++, job.recordCount());
            ps.setLong(i++, job.errorCount());
            ps.setInt(i++, job.retryCount());
            setText(ps, i++, job.failureStage().map(FailureStage::getValue));
            setText(ps, i++, job.errorCode());
            setText(ps, i++, job.errorMessage());
            setText(ps, i++, job.errorFilePath());
            ps.setDouble(i++, job.estimatedCostUsd());
            ps.setLong(i++, job.billedBytesScanned());
            ps.setLong(i++, job.billedBytesWritten());
            if (!opensRun) {
                setTime(ps, i++, Optional.of(job.createdAt()));
            }
            if (!stampStartedNow) {
                setTime(ps, i++, job.startedAt());
            }
            if (!stampCompletedNow) {
                setTime(ps, i++, job.completedAt());
            }
            if (ps.executeUpdate() != 1) {
                throw new IllegalStateException("appended no row for runId=" + job.runId());
            }
        }
    }

    // ---------------------------------------------------------------- reads

    @Override
    public Optional<PipelineJob> getJob(String runId) {
        Objects.requireNonNull(runId, "runId must not be null");
        return read("getJob", c -> project(c, "run_id = ?", List.of(runId), "", List.of()))
                .stream().findFirst();
    }

    @Override
    public List<PipelineJob> getPendingJobs(Optional<String> systemId) {
        Objects.requireNonNull(systemId, "systemId must not be null");
        String filter = systemId.isPresent() ? "system_id = ?" : "";
        List<Object> args = systemId.<List<Object>>map(List::of).orElse(List.of());
        return read("getPendingJobs", c -> project(c, filter, args,
                "status IN ('created','running')", List.of()));
    }

    @Override
    public List<EntityStatus> getEntityStatus(String systemId, LocalDate extractDate) {
        Objects.requireNonNull(systemId, "systemId must not be null");
        Objects.requireNonNull(extractDate, "extractDate must not be null");
        List<EntityStatus> out = new ArrayList<>();
        for (PipelineJob j : read("getEntityStatus", c -> project(c,
                "system_id = ? AND extract_date = ?", List.of(systemId, Date.valueOf(extractDate)),
                "", List.of()))) {
            out.add(new EntityStatus(j.entityType().orElse(""), j.status().getValue(), j.runId(),
                    j.recordCount(), j.errorCount(), j.startedAt(), j.completedAt()));
        }
        return out;
    }

    @Override
    public List<FailedJob> getFailedJobs(String systemId, LocalDate extractDate) {
        Objects.requireNonNull(systemId, "systemId must not be null");
        Objects.requireNonNull(extractDate, "extractDate must not be null");
        List<FailedJob> out = new ArrayList<>();
        for (PipelineJob j : read("getFailedJobs", c -> project(c,
                "system_id = ? AND extract_date = ?", List.of(systemId, Date.valueOf(extractDate)),
                "status = 'failed'", List.of()))) {
            out.add(new FailedJob(j.runId(), j.entityType().orElse(""),
                    j.failureStage().map(FailureStage::getValue).orElse(""),
                    j.errorCode().orElse(""), j.errorMessage().orElse(""), j.errorFilePath(),
                    j.completedAt().orElse(Instant.EPOCH), j.retryCount()));
        }
        return out;
    }

    @Override
    public Optional<FdpJobStatus> getFdpJobStatus(String systemId, LocalDate extractDate,
                                                  String modelName) {
        Objects.requireNonNull(systemId, "systemId must not be null");
        Objects.requireNonNull(extractDate, "extractDate must not be null");
        Objects.requireNonNull(modelName, "modelName must not be null");
        List<PipelineJob> runs = read("getFdpJobStatus", c -> project(c,
                "system_id = ? AND extract_date = ? AND job_type = ? AND pipeline_name = ?",
                List.of(systemId, Date.valueOf(extractDate), JobType.TRANSFORMATION.name(), modelName),
                "", List.of()));
        // project() returns oldest-created first; the latest run is the one reported.
        if (runs.isEmpty()) {
            return Optional.empty();
        }
        PipelineJob j = runs.get(runs.size() - 1);
        return Optional.of(new FdpJobStatus(j.runId(), j.pipelineName(), j.status().getValue(),
                j.recordCount(), j.startedAt(), j.completedAt()));
    }

    private interface Query<T> {
        T run(Connection c) throws SQLException;
    }

    private <T> T read(String op, Query<T> query) {
        try (Connection c = dataSource.getConnection()) {
            return query.run(c);
        } catch (SQLException e) {
            throw failure(op, e);
        }
    }

    /**
     * Each run's winning row. {@code immutableFilter} may name only immutable columns (it is
     * applied before ranking); {@code stateFilter} is applied to the winners.
     */
    private List<PipelineJob> project(Connection c, String immutableFilter, List<Object> immutableArgs,
                                      String stateFilter, List<Object> stateArgs) throws SQLException {
        String sql = "WITH ranked AS (SELECT *, ROW_NUMBER() OVER (PARTITION BY run_id ORDER BY "
                + "CASE WHEN " + IS_TERMINAL + " THEN 0 ELSE 1 END, "
                + "CASE WHEN " + IS_TERMINAL + " THEN updated_at END ASC, "
                + "CASE WHEN " + IS_TERMINAL + " THEN seq END ASC, "
                + "updated_at DESC, seq DESC) AS rn FROM " + table
                + (immutableFilter.isEmpty() ? "" : " WHERE " + immutableFilter)
                + ") SELECT * FROM ranked WHERE rn = 1"
                + (stateFilter.isEmpty() ? "" : " AND " + stateFilter)
                + " ORDER BY created_at, run_id";
        try (PreparedStatement ps = c.prepareStatement(sql)) {
            int i = 1;
            for (Object a : immutableArgs) {
                ps.setObject(i++, a);
            }
            for (Object a : stateArgs) {
                ps.setObject(i++, a);
            }
            List<PipelineJob> out = new ArrayList<>();
            try (ResultSet rs = ps.executeQuery()) {
                while (rs.next()) {
                    out.add(toJob(rs));
                }
            }
            return out;
        }
    }

    private static PipelineJob toJob(ResultSet rs) throws SQLException {
        PipelineJob.Builder b = PipelineJob.builder(rs.getString("run_id"), rs.getString("system_id"),
                rs.getString("pipeline_name"), rs.getDate("extract_date").toLocalDate(),
                JobStatus.valueOf(rs.getString("status").toUpperCase()));
        b.jobType(JobType.valueOf(rs.getString("job_type")));
        b.entityType(text(rs, "entity_type"));
        b.sourceFile(text(rs, "source_file"));
        b.targetTable(text(rs, "target_table"));
        b.recordCount(rs.getLong("record_count"));
        b.errorCount(rs.getLong("error_count"));
        b.retryCount(rs.getInt("retry_count"));
        String stage = rs.getString("failure_stage");
        if (stage != null) {
            b.failureStage(FailureStage.valueOf(stage.toUpperCase()));
        }
        b.errorCode(text(rs, "error_code"));
        b.errorMessage(text(rs, "error_message"));
        b.errorFilePath(text(rs, "error_file_path"));
        b.estimatedCostUsd(rs.getDouble("estimated_cost_usd"));
        b.billedBytesScanned(rs.getLong("billed_bytes_scanned"));
        b.billedBytesWritten(rs.getLong("billed_bytes_written"));
        b.createdAt(instant(rs, "created_at"));
        b.updatedAt(instant(rs, "updated_at"));
        b.startedAt(instant(rs, "started_at"));
        b.completedAt(instant(rs, "completed_at"));
        return b.build();
    }

    /** A text column, with "" read as absent, as BigQuery's {@code stringOptional} does. */
    private static String text(ResultSet rs, String column) throws SQLException {
        String v = rs.getString(column);
        return v == null || v.isEmpty() ? null : v;
    }

    private static Instant instant(ResultSet rs, String column) throws SQLException {
        OffsetDateTime t = rs.getObject(column, OffsetDateTime.class);
        return t == null ? null : t.toInstant();
    }

    // ---------------------------------------------------------------- helpers

    static Set<JobStatus> allowedPriorStates(JobStatus target) {
        switch (target) {
            case RUNNING:
                return EnumSet.of(JobStatus.CREATED, JobStatus.RETRYING);
            case SUCCEEDED:
                return EnumSet.of(JobStatus.RUNNING);
            case FAILED:
                return EnumSet.of(JobStatus.CREATED, JobStatus.RUNNING, JobStatus.RETRYING,
                        JobStatus.FAILED);
            case RETRYING:
                return EnumSet.of(JobStatus.CREATED, JobStatus.RUNNING, JobStatus.FAILED);
            case CANCELLED:
                return EnumSet.of(JobStatus.CREATED, JobStatus.RUNNING, JobStatus.RETRYING);
            case CREATED:
            default:
                throw new IllegalArgumentException(
                        "CREATED is not a transition target — a job enters it via createJob; got "
                                + target);
        }
    }

    /** Whether {@code status} is one a run cannot leave. */
    static boolean isTerminal(JobStatus status) {
        return TERMINAL_STATES.contains(status);
    }

    private static PipelineJob.Builder carryForward(PipelineJob current, JobStatus status) {
        return PipelineJob.builder(current.runId(), current.systemId(), current.pipelineName(),
                        current.extractDate(), status)
                .jobType(current.jobType())
                .entityType(current.entityType().orElse(null))
                .sourceFile(current.sourceFile().orElse(null))
                .targetTable(current.targetTable().orElse(null))
                .recordCount(current.recordCount())
                .errorCount(current.errorCount())
                .retryCount(current.retryCount())
                .failureStage(current.failureStage().orElse(null))
                .errorCode(current.errorCode().orElse(null))
                .errorMessage(current.errorMessage().orElse(null))
                .errorFilePath(current.errorFilePath().orElse(null))
                .estimatedCostUsd(current.estimatedCostUsd())
                .billedBytesScanned(current.billedBytesScanned())
                .billedBytesWritten(current.billedBytesWritten())
                .createdAt(current.createdAt())
                .startedAt(current.startedAt().orElse(null))
                .completedAt(current.completedAt().orElse(null));
    }

    private static void setText(PreparedStatement ps, int i, Optional<String> v) throws SQLException {
        if (v.isPresent()) {
            ps.setString(i, v.get());
        } else {
            ps.setNull(i, Types.VARCHAR);
        }
    }

    private static void setTime(PreparedStatement ps, int i, Optional<Instant> v) throws SQLException {
        if (v.isPresent()) {
            ps.setObject(i, OffsetDateTime.ofInstant(v.get(), ZoneOffset.UTC));
        } else {
            ps.setNull(i, Types.TIMESTAMP_WITH_TIMEZONE);
        }
    }

    private static RuntimeException failure(String op, SQLException e) {
        return new IllegalStateException("PostgreSQL " + op + " failed: " + e.getMessage(), e);
    }
}
