package com.enrichmeai.culvert.postgres;

import com.enrichmeai.culvert.contracts.StageClaim;
import com.enrichmeai.culvert.stageclaim.Claim;
import com.enrichmeai.culvert.stageclaim.ClaimResult;
import com.enrichmeai.culvert.stageclaim.StageKey;
import org.postgresql.ds.PGSimpleDataSource;

import javax.sql.DataSource;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.time.Duration;
import java.time.OffsetDateTime;
import java.util.Objects;
import java.util.Optional;

/**
 * {@link StageClaim} on PostgreSQL: the claim is a row lock held by an open transaction.
 *
 * <h2>How a claim works</h2>
 * <ol>
 *   <li>Make sure the key's row exists in {@code stage_claims} (an autocommitted
 *       {@code INSERT ... ON CONFLICT DO NOTHING}).
 *   <li>Open a READ COMMITTED transaction and lock that row with {@code SELECT ... FOR UPDATE},
 *       waiting at most {@code maxWait} ({@code lock_timeout}, or {@code NOWAIT} for zero). If the
 *       wait runs out (SQLSTATE 55P03), the result is {@link ClaimResult.Held}.
 *   <li>With the lock held, look the key up in {@code stage_completions}. A row there means the
 *       stage is done: {@link ClaimResult.Completed}. Because the transaction is READ COMMITTED,
 *       this read sees a completion that the previous holder committed while we waited.
 *   <li>Otherwise {@link ClaimResult.Acquired}: the transaction, and so the lock, stay open until
 *       {@link Claim#complete()} inserts the completion row and commits, or {@link Claim#close()}
 *       rolls back.
 * </ol>
 * <p>Both tables are insert-only. A completion's primary key means a stage is completed once.
 *
 * <p>A {@code maxWait} longer than PostgreSQL's {@code lock_timeout} range (an int of
 * milliseconds, about 24.8 days) is capped to it. Connections come from the data source with no
 * transaction open; their autocommit and isolation are put back before they are closed.
 *
 * <h2>Why transaction-scoped, with no lease or TTL (decided in #195)</h2>
 * <p>The lock lives exactly as long as the claimant's transaction. If the claimant dies, its session
 * ends: the server rolls the transaction back, the lock is released, no completion was written, and
 * the next claimant acquires the stage and runs it from its start. That is "an interrupted run
 * resumes where it stopped", at stage granularity. A lease would add a second clock that can
 * disagree with reality: one too short lets a slow but live holder lose its claim mid-stage (a
 * double start), and one too long blocks recovery for its whole length. The transaction already
 * says exactly whether the holder is alive.
 * <p>What that leaves to the deployment:
 * <ul>
 *   <li>A holder that hangs while still connected keeps its claim. Set
 *       {@code idle_in_transaction_session_timeout} (and TCP keepalives, or
 *       {@code tcp_user_timeout}) so the server ends such a session.
 *   <li>A claim holds one connection for the whole stage. Size the pool for the number of stages
 *       that run at once.
 *   <li>A stage must be safe to re-run from its start after an abandoned claim; the claim prevents
 *       two runs at once and a run after completion, not a partial run.
 * </ul>
 */
public final class PostgresStageClaim implements StageClaim {

    /** The tables {@code job_control.sql} creates. */
    public static final String DEFAULT_SCHEMA = "job_control";

    private static final String LOCK_NOT_AVAILABLE = "55P03";

    private final DataSource dataSource;
    private final String claims;
    private final String completions;

    /** Claims in {@link #DEFAULT_SCHEMA}. */
    public PostgresStageClaim(DataSource dataSource) {
        this(dataSource, DEFAULT_SCHEMA);
    }

    /**
     * @param schema the schema holding {@code stage_claims} and {@code stage_completions}
     */
    public PostgresStageClaim(DataSource dataSource, String schema) {
        this.dataSource = Objects.requireNonNull(dataSource, "dataSource must not be null");
        Objects.requireNonNull(schema, "schema must not be null");
        if (schema.contains(".")) {
            throw new IllegalArgumentException("schema must be a single name: " + schema);
        }
        this.claims = PostgresJobControlRepository.quote(schema + ".stage_claims");
        this.completions = PostgresJobControlRepository.quote(schema + ".stage_completions");
    }

    /**
     * The {@code ServiceLoader} constructor: the database from {@code CULVERT_POSTGRES_URL},
     * {@code CULVERT_POSTGRES_USER} and {@code CULVERT_POSTGRES_PASSWORD} (or the
     * {@code culvert.postgres.*} properties), as {@link PostgresJobControlRepository} reads them.
     *
     * @throws IllegalStateException if no URL is set
     */
    public PostgresStageClaim() {
        this(dataSourceFromEnvironment());
    }

    private static DataSource dataSourceFromEnvironment() {
        String url = setting("CULVERT_POSTGRES_URL", "culvert.postgres.url").orElseThrow(() ->
                new IllegalStateException("PostgresStageClaim needs CULVERT_POSTGRES_URL "
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

    @Override
    public ClaimResult tryClaim(StageKey key, String claimant, Duration maxWait) {
        Objects.requireNonNull(key, "key must not be null");
        Objects.requireNonNull(claimant, "claimant must not be null");
        Objects.requireNonNull(maxWait, "maxWait must not be null");
        if (claimant.isBlank()) {
            throw new IllegalArgumentException("claimant must not be blank");
        }
        if (maxWait.isNegative()) {
            throw new IllegalArgumentException("maxWait must not be negative, got " + maxWait);
        }

        Connection c;
        try {
            c = dataSource.getConnection();
        } catch (SQLException e) {
            throw failure("tryClaim", e);
        }
        Session session = null;
        try {
            session = new Session(c);
            ensureRow(c, key);
            session.begin();
            if (!lock(c, key, maxWait)) {
                session.end(false);
                return new ClaimResult.Held(key);
            }
            Optional<ClaimResult.Completed> done = completion(c, key);
            if (done.isPresent()) {
                session.end(false);
                return done.get();
            }
            return new ClaimResult.Acquired(new PostgresClaim(session, key, claimant));
        } catch (SQLException | RuntimeException e) {
            if (session != null) {
                session.abort(e);
            } else {
                closeQuietly(c, e);
            }
            throw e instanceof SQLException ? failure("tryClaim", (SQLException) e) : (RuntimeException) e;
        }
    }

    /** A single autocommit read of {@code stage_completions}: it takes no lock and waits on none. */
    @Override
    public Optional<ClaimResult.Completed> completion(StageKey key) {
        Objects.requireNonNull(key, "key must not be null");
        try (Connection c = dataSource.getConnection()) {
            if (!c.getAutoCommit()) {
                Optional<ClaimResult.Completed> done = completion(c, key);
                c.rollback();
                return done;
            }
            return completion(c, key);
        } catch (SQLException e) {
            throw failure("completion", e);
        }
    }

    private void ensureRow(Connection c, StageKey key) throws SQLException {
        try (PreparedStatement ps = c.prepareStatement("INSERT INTO " + claims
                + " (unit, stage, period) VALUES (?, ?, ?) ON CONFLICT DO NOTHING")) {
            bind(ps, key);
            ps.executeUpdate();
        }
    }

    /** True if the lock was taken within {@code maxWait}; false if another session held it. */
    private boolean lock(Connection c, StageKey key, Duration maxWait) throws SQLException {
        String select = "SELECT 1 FROM " + claims + " WHERE unit = ? AND stage = ? AND period = ? FOR UPDATE";
        boolean timed = !maxWait.isZero();
        if (!timed) {
            select += " NOWAIT";
        } else {
            // lock_timeout is an int of milliseconds (about 24.8 days at most): longer waits are capped.
            long ms = maxWait.compareTo(Duration.ofMillis(Integer.MAX_VALUE)) >= 0
                    ? Integer.MAX_VALUE : Math.max(1, maxWait.toMillis());
            try (Statement s = c.createStatement()) {
                s.execute("SET LOCAL lock_timeout = '" + ms + "ms'");
            }
        }
        try (PreparedStatement ps = c.prepareStatement(select)) {
            bind(ps, key);
            try (ResultSet rs = ps.executeQuery()) {
                if (!rs.next()) {
                    throw new IllegalStateException("stage_claims row for " + key + " disappeared");
                }
            }
            if (timed) {
                // The wait was for the lock only; the rest of the claim runs with the session's own timeout.
                try (Statement s = c.createStatement()) {
                    s.execute("SET LOCAL lock_timeout TO DEFAULT");
                }
            }
            return true;
        } catch (SQLException e) {
            if (LOCK_NOT_AVAILABLE.equals(e.getSQLState())) {
                return false;
            }
            throw e;
        }
    }

    private Optional<ClaimResult.Completed> completion(Connection c, StageKey key) throws SQLException {
        try (PreparedStatement ps = c.prepareStatement("SELECT completed_by, completed_at FROM "
                + completions + " WHERE unit = ? AND stage = ? AND period = ?")) {
            bind(ps, key);
            try (ResultSet rs = ps.executeQuery()) {
                if (!rs.next()) {
                    return Optional.empty();
                }
                return Optional.of(new ClaimResult.Completed(key, rs.getString(1),
                        rs.getObject(2, OffsetDateTime.class).toInstant()));
            }
        }
    }

    private static void bind(PreparedStatement ps, StageKey key) throws SQLException {
        ps.setString(1, key.unit());
        ps.setString(2, key.stage());
        ps.setString(3, key.period());
    }

    private static void closeQuietly(Connection c, Throwable cause) {
        try {
            c.close();
        } catch (SQLException e) {
            cause.addSuppressed(e);
        }
    }

    private static IllegalStateException failure(String op, SQLException e) {
        return new IllegalStateException("PostgreSQL " + op + " failed: " + e.getMessage(), e);
    }

    /**
     * One connection's transaction. It remembers the connection's autocommit and isolation so that
     * it can put them back before closing, because a pool reuses the connection.
     */
    private static final class Session {
        private final Connection c;
        private final boolean autoCommit;
        private final int isolation;

        Session(Connection c) throws SQLException {
            this.c = c;
            this.autoCommit = c.getAutoCommit();
            this.isolation = c.getTransactionIsolation();
            c.setAutoCommit(true);
        }

        void begin() throws SQLException {
            c.setAutoCommit(false);
            c.setTransactionIsolation(Connection.TRANSACTION_READ_COMMITTED);
        }

        /** Commit or roll back, restore the connection's settings, and close it. */
        void end(boolean commit) throws SQLException {
            try {
                if (commit) {
                    c.commit();
                } else {
                    c.rollback();
                }
            } finally {
                try {
                    c.setTransactionIsolation(isolation);
                    c.setAutoCommit(autoCommit);
                } finally {
                    c.close();
                }
            }
        }

        void abort(Throwable cause) {
            try {
                if (!c.getAutoCommit()) {
                    c.rollback();
                }
            } catch (SQLException e) {
                cause.addSuppressed(e);
            }
            try {
                c.setTransactionIsolation(isolation);
                c.setAutoCommit(autoCommit);
            } catch (SQLException e) {
                cause.addSuppressed(e);
            }
            closeQuietly(c, cause);
        }
    }

    /** A held claim: the open transaction holding the row lock. */
    private final class PostgresClaim implements Claim {
        private final Session session;
        private final StageKey key;
        private final String claimant;
        private boolean ended;

        PostgresClaim(Session session, StageKey key, String claimant) {
            this.session = session;
            this.key = key;
            this.claimant = claimant;
        }

        @Override
        public StageKey key() {
            return key;
        }

        @Override
        public String claimant() {
            return claimant;
        }

        @Override
        public synchronized void complete() {
            if (ended) {
                throw new IllegalStateException("claim on " + key + " already ended");
            }
            ended = true;
            try (PreparedStatement ps = session.c.prepareStatement("INSERT INTO " + completions
                    + " (unit, stage, period, completed_by, completed_at) "
                    + "VALUES (?, ?, ?, ?, clock_timestamp())")) {
                bind(ps, key);
                ps.setString(4, claimant);
                ps.executeUpdate();
            } catch (SQLException e) {
                session.abort(e);
                throw failure("complete", e);
            }
            try {
                session.end(true);
            } catch (SQLException e) {
                throw failure("complete", e);
            }
        }

        @Override
        public synchronized void close() {
            if (ended) {
                return;
            }
            ended = true;
            try {
                session.end(false);
            } catch (SQLException e) {
                // The rollback failed because the session is already gone (the server ended it,
                // or the network did). The server rolled the transaction back and released the
                // lock when the session ended, so the claim is abandoned either way: nothing to report.
            }
        }
    }
}
