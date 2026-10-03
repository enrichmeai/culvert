package com.enrichmeai.culvert.postgres;

import com.enrichmeai.culvert.jobcontrol.JobStatus;
import io.zonky.test.db.postgres.embedded.EmbeddedPostgres;

import javax.sql.DataSource;
import java.io.IOException;
import java.io.InputStream;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.SQLException;
import java.sql.Statement;

/**
 * A real PostgreSQL server for the tests, started once per JVM from the embedded binaries, with
 * the module's own {@code job_control.sql} applied. Each test empties the ledger first.
 */
final class EmbeddedPostgresLedger {

    private static EmbeddedPostgres server;

    private EmbeddedPostgresLedger() {
    }

    /** The server's database, with the shipped DDL applied and the ledger empty. */
    static synchronized DataSource freshLedger() {
        try {
            if (server == null) {
                server = EmbeddedPostgres.builder().start();
                Runtime.getRuntime().addShutdownHook(new Thread(() -> {
                    try {
                        server.close();
                    } catch (IOException ignored) {
                        // shutting down anyway
                    }
                }));
                execute(server.getPostgresDatabase(), shippedDdl());
            }
            DataSource db = server.getPostgresDatabase();
            execute(db, "TRUNCATE job_control.pipeline_jobs RESTART IDENTITY");
            return db;
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
    }

    /** The DDL the module ships, read from the classpath exactly as a user would get it. */
    static String shippedDdl() {
        try (InputStream in = PostgresJobControlRepository.class
                .getResourceAsStream("job_control.sql")) {
            if (in == null) {
                throw new IllegalStateException("job_control.sql is not on the classpath");
            }
            return new String(in.readAllBytes(), StandardCharsets.UTF_8);
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
    }

    static void execute(DataSource db, String sql) {
        try (Connection c = db.getConnection(); Statement s = c.createStatement()) {
            s.execute(sql);
        } catch (SQLException e) {
            throw new IllegalStateException(e);
        }
    }

    /**
     * Copy the run's latest row with a new status and a later timestamp, straight into the
     * ledger: around the repository's transition guard, as the contract suite requires.
     */
    static void appendRaw(DataSource db, String runId, JobStatus status) {
        String sql = "INSERT INTO job_control.pipeline_jobs (run_id, opens_run, system_id, "
                + "pipeline_name, extract_date, status, job_type, entity_type, source_file, "
                + "target_table, record_count, error_count, retry_count, failure_stage, error_code, "
                + "error_message, error_file_path, estimated_cost_usd, billed_bytes_scanned, "
                + "billed_bytes_written, created_at, updated_at, started_at, completed_at) "
                + "SELECT run_id, FALSE, system_id, pipeline_name, extract_date, ?, job_type, "
                + "entity_type, source_file, target_table, record_count, error_count, retry_count, "
                + "failure_stage, error_code, error_message, error_file_path, estimated_cost_usd, "
                + "billed_bytes_scanned, billed_bytes_written, created_at, clock_timestamp(), "
                + "started_at, completed_at FROM job_control.pipeline_jobs WHERE run_id = ? "
                + "ORDER BY seq DESC LIMIT 1";
        try (Connection c = db.getConnection(); PreparedStatement ps = c.prepareStatement(sql)) {
            ps.setString(1, status.getValue());
            ps.setString(2, runId);
            if (ps.executeUpdate() != 1) {
                throw new IllegalStateException("appendRaw found no row for " + runId);
            }
        } catch (SQLException e) {
            throw new IllegalStateException(e);
        }
    }
}
