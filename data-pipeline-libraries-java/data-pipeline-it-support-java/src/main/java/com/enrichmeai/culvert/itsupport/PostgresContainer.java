package com.enrichmeai.culvert.itsupport;

import org.postgresql.ds.PGSimpleDataSource;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.utility.DockerImageName;

import javax.sql.DataSource;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;

/**
 * Testcontainers fixture for a real PostgreSQL server, built on the Testcontainers
 * {@link PostgreSQLContainer} (which supplies the readiness wait and the JDBC URL).
 *
 * <p><strong>Every connection it hands out is its own server session.</strong>
 * {@link #newConnection()} opens a fresh JDBC connection each call, and {@link #newDataSource()}
 * is an unpooled {@code PGSimpleDataSource} whose every {@code getConnection()} does the same. So a
 * test can hold a row lock on one connection and contend for it from another, deterministically:
 * what {@code StageClaim} (T2.3, #195) needs, and what a single pooled connection cannot give.
 * {@link #backendPid(Connection)} names the session, so a test can assert two are distinct.
 *
 * <h2>Usage</h2>
 * <pre>{@code
 * @Testcontainers
 * class StageClaimIT {
 *     @Container
 *     static final PostgresContainer PG = new PostgresContainer();
 *
 *     @Test
 *     void secondClaimantWaits() throws SQLException {
 *         try (Connection a = PG.newConnection(); Connection b = PG.newConnection()) {
 *             // a locks a row; b contends for it
 *         }
 *     }
 * }
 * }</pre>
 *
 * <p>Control-plane epic #188, Phase 2 (T2.2, #194).
 */
public final class PostgresContainer extends PostgreSQLContainer<PostgresContainer> {

    /** Default image: the PostgreSQL major the control plane targets. */
    public static final DockerImageName DEFAULT_IMAGE = DockerImageName.parse("postgres:16-alpine");

    /** Creates a PostgreSQL server on {@link #DEFAULT_IMAGE}. */
    public PostgresContainer() {
        this(DEFAULT_IMAGE);
    }

    /**
     * Creates a PostgreSQL server on a custom image.
     *
     * @param image a {@code postgres} image (Testcontainers checks compatibility)
     */
    public PostgresContainer(DockerImageName image) {
        super(image);
    }

    /**
     * Opens a new connection: a new server session, never shared with another caller. The caller
     * closes it. Only valid once the container is started.
     */
    public Connection newConnection() throws SQLException {
        requireRunning();
        return DriverManager.getConnection(getJdbcUrl(), getUsername(), getPassword());
    }

    /**
     * An unpooled {@link DataSource}: each {@code getConnection()} opens a new server session. Use
     * it where code under test takes a {@code DataSource} (for example
     * {@code PostgresJobControlRepository}). Only valid once the container is started.
     */
    public DataSource newDataSource() {
        requireRunning();
        PGSimpleDataSource ds = new PGSimpleDataSource();
        ds.setURL(getJdbcUrl());
        ds.setUser(getUsername());
        ds.setPassword(getPassword());
        return ds;
    }

    /** Runs {@code sql} (one or more statements, such as a DDL script) on a fresh connection. */
    public void execute(String sql) throws SQLException {
        try (Connection c = newConnection(); Statement s = c.createStatement()) {
            s.execute(sql);
        }
    }

    /** The server process id behind {@code connection}: distinct for distinct sessions. */
    public static int backendPid(Connection connection) throws SQLException {
        try (Statement s = connection.createStatement();
             ResultSet rs = s.executeQuery("SELECT pg_backend_pid()")) {
            rs.next();
            return rs.getInt(1);
        }
    }

    private void requireRunning() {
        if (!isRunning()) {
            throw new IllegalStateException("PostgresContainer is not started: start it (or use "
                    + "@Container) before asking for a connection");
        }
    }
}
