package com.enrichmeai.culvert.e2e.controlplane;

import com.enrichmeai.culvert.postgres.PostgresJobControlRepository;
import com.enrichmeai.culvert.postgres.PostgresReadiness;
import com.enrichmeai.culvert.postgres.PostgresStageClaim;
import io.zonky.test.db.postgres.embedded.EmbeddedPostgres;

import javax.sql.DataSource;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.List;

/**
 * A real PostgreSQL 16, started once per JVM from the embedded binaries, with the
 * {@code job_control.sql} that {@code data-pipeline-postgres} ships applied through
 * {@link ControlPlaneMain#applyDdl()}, as an operator would. Each test empties every table first.
 */
final class EmbeddedControlStore {

    private static EmbeddedPostgres server;

    private EmbeddedControlStore() {
    }

    /** The database, with the DDL applied and every control-plane table empty. */
    static synchronized DataSource fresh() {
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
                String previous = System.getProperty("culvert.postgres.url");
                System.setProperty("culvert.postgres.url", url());
                System.setProperty("culvert.postgres.user", "postgres");
                try {
                    ControlPlaneMain.applyDdl();
                } finally {
                    clearSettings(previous);
                }
            }
            DataSource db = server.getPostgresDatabase();
            execute(db, "TRUNCATE job_control.pipeline_jobs, job_control.stage_claims, "
                    + "job_control.stage_completions, job_control.readiness_expected, "
                    + "job_control.readiness_attempts RESTART IDENTITY");
            return db;
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
    }

    /** The server's JDBC URL, for {@code CULVERT_POSTGRES_URL}. */
    static String url() {
        return server.getJdbcUrl("postgres", "postgres");
    }

    static ControlPlane stores(DataSource db) {
        return new ControlPlane(new PostgresJobControlRepository(db), new PostgresStageClaim(db),
                new PostgresReadiness(db));
    }

    private static void clearSettings(String previousUrl) {
        if (previousUrl == null) {
            System.clearProperty("culvert.postgres.url");
        } else {
            System.setProperty("culvert.postgres.url", previousUrl);
        }
        System.clearProperty("culvert.postgres.user");
    }

    static void execute(DataSource db, String sql) {
        try (Connection c = db.getConnection(); Statement s = c.createStatement()) {
            s.execute(sql);
        } catch (SQLException e) {
            throw new IllegalStateException(e);
        }
    }

    /** Every row of a query, each row's columns joined with {@code |}. */
    static List<String> rows(DataSource db, String sql, Object... params) {
        try (Connection c = db.getConnection(); PreparedStatement ps = c.prepareStatement(sql)) {
            for (int i = 0; i < params.length; i++) {
                ps.setObject(i + 1, params[i]);
            }
            List<String> out = new ArrayList<>();
            try (ResultSet rs = ps.executeQuery()) {
                int columns = rs.getMetaData().getColumnCount();
                while (rs.next()) {
                    StringBuilder row = new StringBuilder();
                    for (int i = 1; i <= columns; i++) {
                        row.append(i > 1 ? "|" : "").append(rs.getString(i));
                    }
                    out.add(row.toString());
                }
            }
            return out;
        } catch (SQLException e) {
            throw new IllegalStateException(e);
        }
    }
}
