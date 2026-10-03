package com.enrichmeai.culvert.postgres;

import com.enrichmeai.culvert.contracts.InputReadiness;
import com.enrichmeai.culvert.readiness.AttemptState;
import com.enrichmeai.culvert.readiness.InputAttempt;
import com.enrichmeai.culvert.readiness.Readiness;
import com.enrichmeai.culvert.readiness.ReadinessResolver;
import org.postgresql.ds.PGSimpleDataSource;

import javax.sql.DataSource;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;
import java.util.TreeSet;

/**
 * {@link InputReadiness} on PostgreSQL (#198).
 *
 * <ul>
 *   <li><strong>The catalogue</strong> is {@code readiness_expected}: one row per (unit, input).
 *       It is configuration: {@link #declareExpected} replaces a unit's rows in one transaction,
 *       under a per-unit advisory lock, so two declarations for one unit cannot interleave.
 *   <li><strong>The ledger</strong> is {@code readiness_attempts}: insert-only, ordered by
 *       {@code seq}. Nothing updates or deletes an attempt.
 *   <li><strong>A readiness read</strong> is one statement, the catalogue {@code LEFT JOIN}ed to
 *       the period's attempts, so the expected set and the attempts come from one snapshot. The
 *       rows go to {@link ReadinessResolver}, the rule every backend shares.
 * </ul>
 *
 * <p>Both tables are this adapter's own schema, created by {@code job_control.sql}. They are not
 * wire-contract tables.
 */
public final class PostgresReadiness implements InputReadiness {

    /** The tables {@code job_control.sql} creates. */
    public static final String DEFAULT_SCHEMA = "job_control";

    private final DataSource dataSource;
    private final String expected;
    private final String attempts;

    /** Readiness in {@link #DEFAULT_SCHEMA}. */
    public PostgresReadiness(DataSource dataSource) {
        this(dataSource, DEFAULT_SCHEMA);
    }

    /**
     * @param schema the schema holding {@code readiness_expected} and {@code readiness_attempts}
     */
    public PostgresReadiness(DataSource dataSource, String schema) {
        this.dataSource = Objects.requireNonNull(dataSource, "dataSource must not be null");
        Objects.requireNonNull(schema, "schema must not be null");
        if (schema.contains(".")) {
            throw new IllegalArgumentException("schema must be a single name: " + schema);
        }
        this.expected = PostgresJobControlRepository.quote(schema + ".readiness_expected");
        this.attempts = PostgresJobControlRepository.quote(schema + ".readiness_attempts");
    }

    /**
     * The {@code ServiceLoader} constructor: the database from {@code CULVERT_POSTGRES_URL},
     * {@code CULVERT_POSTGRES_USER} and {@code CULVERT_POSTGRES_PASSWORD} (or the
     * {@code culvert.postgres.*} properties), as {@link PostgresJobControlRepository} reads them.
     *
     * @throws IllegalStateException if no URL is set
     */
    public PostgresReadiness() {
        this(dataSourceFromEnvironment());
    }

    private static DataSource dataSourceFromEnvironment() {
        String url = setting("CULVERT_POSTGRES_URL", "culvert.postgres.url").orElseThrow(() ->
                new IllegalStateException("PostgresReadiness needs CULVERT_POSTGRES_URL "
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
    public void declareExpected(String unit, Set<String> inputs) {
        requireText(unit, "unit");
        Objects.requireNonNull(inputs, "inputs must not be null");
        if (inputs.isEmpty()) {
            throw new IllegalArgumentException("unit '" + unit + "' must expect at least one input; "
                    + "a unit that needs nothing should not be gated");
        }
        inputs.forEach(i -> requireText(i, "input"));
        try (Connection c = dataSource.getConnection()) {
            boolean autoCommit = c.getAutoCommit();
            c.setAutoCommit(false);
            try {
                try (PreparedStatement lock = c.prepareStatement("SELECT pg_advisory_xact_lock(hashtext(?))")) {
                    lock.setString(1, "culvert.readiness_expected:" + unit);
                    lock.executeQuery().close();
                }
                try (PreparedStatement del = c.prepareStatement("DELETE FROM " + expected + " WHERE unit = ?")) {
                    del.setString(1, unit);
                    del.executeUpdate();
                }
                try (PreparedStatement ins = c.prepareStatement(
                        "INSERT INTO " + expected + " (unit, input) VALUES (?, ?)")) {
                    for (String input : new TreeSet<>(inputs)) {
                        ins.setString(1, unit);
                        ins.setString(2, input);
                        ins.addBatch();
                    }
                    ins.executeBatch();
                }
                c.commit();
            } catch (SQLException | RuntimeException e) {
                c.rollback();
                throw e;
            } finally {
                c.setAutoCommit(autoCommit);
            }
        } catch (SQLException e) {
            throw failure("declareExpected", e);
        }
    }

    @Override
    public Set<String> expected(String unit) {
        requireText(unit, "unit");
        return read("expected", c -> {
            try (PreparedStatement ps = c.prepareStatement(
                    "SELECT input FROM " + expected + " WHERE unit = ? ORDER BY input")) {
                ps.setString(1, unit);
                Set<String> out = new LinkedHashSet<>();
                try (ResultSet rs = ps.executeQuery()) {
                    while (rs.next()) {
                        out.add(rs.getString(1));
                    }
                }
                return Set.copyOf(out);
            }
        });
    }

    @Override
    public void publish(InputAttempt attempt) {
        Objects.requireNonNull(attempt, "attempt must not be null");
        read("publish", c -> {
            try (PreparedStatement ps = c.prepareStatement("INSERT INTO " + attempts
                    + " (input, period, run_id, state, retry_of) VALUES (?, ?, ?, ?, ?)")) {
                ps.setString(1, attempt.input());
                ps.setString(2, attempt.period());
                ps.setString(3, attempt.runId());
                ps.setString(4, attempt.state().getValue());
                ps.setString(5, attempt.retryOf().orElse(null));
                ps.executeUpdate();
                return null;
            }
        });
    }

    @Override
    public Readiness readiness(String unit, String period) {
        requireText(unit, "unit");
        requireText(period, "period");
        return read("readiness", c -> {
            // One statement, one snapshot: the expected set, anti-joined against the period's attempts.
            try (PreparedStatement ps = c.prepareStatement("SELECT e.input, a.run_id, a.state, a.retry_of FROM "
                    + expected + " e LEFT JOIN " + attempts + " a ON a.input = e.input AND a.period = ? "
                    + "WHERE e.unit = ? ORDER BY a.seq")) {
                ps.setString(1, period);
                ps.setString(2, unit);
                Set<String> want = new LinkedHashSet<>();
                List<InputAttempt> seen = new ArrayList<>();
                try (ResultSet rs = ps.executeQuery()) {
                    while (rs.next()) {
                        String input = rs.getString(1);
                        want.add(input);
                        String runId = rs.getString(2);
                        if (runId != null) {
                            seen.add(new InputAttempt(input, period, runId,
                                    AttemptState.fromValue(rs.getString(3)), Optional.ofNullable(rs.getString(4))));
                        }
                    }
                }
                return ReadinessResolver.resolve(unit, period, want, seen);
            }
        });
    }

    private interface Query<T> {
        T run(Connection c) throws SQLException;
    }

    /** One autocommit statement; on a pooled non-autocommit connection, its transaction is ended. */
    private <T> T read(String op, Query<T> query) {
        try (Connection c = dataSource.getConnection()) {
            if (c.getAutoCommit()) {
                return query.run(c);
            }
            boolean done = false;
            try {
                T result = query.run(c);
                c.commit();
                done = true;
                return result;
            } finally {
                if (!done) {
                    c.rollback();
                }
            }
        } catch (SQLException e) {
            throw failure(op, e);
        }
    }

    private static String requireText(String value, String name) {
        Objects.requireNonNull(value, name + " must not be null");
        if (value.isBlank()) {
            throw new IllegalArgumentException(name + " must not be blank");
        }
        return value;
    }

    private static IllegalStateException failure(String op, SQLException e) {
        return new IllegalStateException("PostgreSQL " + op + " failed: " + e.getMessage(), e);
    }
}
