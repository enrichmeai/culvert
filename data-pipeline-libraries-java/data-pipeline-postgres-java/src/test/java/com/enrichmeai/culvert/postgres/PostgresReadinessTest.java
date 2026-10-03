package com.enrichmeai.culvert.postgres;

import com.enrichmeai.culvert.autoconfig.AutoConfig;
import com.enrichmeai.culvert.readiness.AttemptState;
import com.enrichmeai.culvert.readiness.InputAttempt;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import javax.sql.DataSource;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/** What the PostgreSQL readiness adds beyond the shared contract, on a real server. */
class PostgresReadinessTest {

    private DataSource db;
    private final String tag = UUID.randomUUID().toString().substring(0, 8);

    @BeforeEach
    void setUp() {
        db = EmbeddedPostgresLedger.freshLedger();
    }

    @Test
    void aSecondDeclarationForTheSameUnitWaitsForTheFirstAndNeitherCollides() throws Exception {
        String unit = "cdp-" + tag;
        String app = "readiness-declare-" + tag;
        PostgresReadiness readiness = new PostgresReadiness(EmbeddedPostgresLedger.tagged(db, app));
        ExecutorService second = Executors.newSingleThreadExecutor();
        try (Connection holder = db.getConnection()) {
            // Hold the unit's declaration lock in an open transaction, as a first declaration would.
            holder.setAutoCommit(false);
            try (PreparedStatement lock = holder.prepareStatement("SELECT pg_advisory_xact_lock(hashtext(?))")) {
                lock.setString(1, "culvert.readiness_expected:" + unit);
                lock.executeQuery().close();
            }
            try (Statement s = holder.createStatement()) {
                s.executeUpdate("INSERT INTO job_control.readiness_expected (unit, input) VALUES ('" + unit
                        + "', 'orders')");
            }

            Future<?> declaring = second.submit(() -> readiness.declareExpected(unit, Set.of("orders", "customers")));
            EmbeddedPostgresLedger.awaitLockWait(db, app);
            assertThat(declaring).as("the second declaration waits on the first").isNotDone();

            holder.commit();
            declaring.get(10, TimeUnit.SECONDS);
        } finally {
            second.shutdownNow();
        }
        assertThat(readiness.expected(unit)).as("the later declaration replaced the earlier one")
                .containsExactlyInAnyOrder("orders", "customers");
    }

    @Test
    void theLedgerIsAppendOnlyAndKeepsEveryEvent() throws SQLException {
        PostgresReadiness readiness = new PostgresReadiness(db);
        readiness.publish(InputAttempt.of("orders-" + tag, "2026-10", "r1", AttemptState.FAILED));
        readiness.publish(InputAttempt.retry("orders-" + tag, "2026-10", "r2", AttemptState.VALIDATED, "r1"));
        try (Connection c = db.getConnection(); Statement s = c.createStatement();
             var rs = s.executeQuery("SELECT run_id, state, retry_of FROM job_control.readiness_attempts "
                     + "WHERE input = 'orders-" + tag + "' ORDER BY seq")) {
            assertThat(rs.next()).isTrue();
            assertThat(rs.getString(1) + "/" + rs.getString(2) + "/" + rs.getString(3)).isEqualTo("r1/failed/null");
            assertThat(rs.next()).isTrue();
            assertThat(rs.getString(1) + "/" + rs.getString(2) + "/" + rs.getString(3)).isEqualTo("r2/validated/r1");
            assertThat(rs.next()).isFalse();
        }
    }

    @Test
    void theTablesRejectAStateOrRetryLinkTheTypesWouldNot() {
        assertThatThrownBy(() -> EmbeddedPostgresLedger.execute(db, "INSERT INTO job_control.readiness_attempts "
                + "(input, period, run_id, state) VALUES ('x', 'p', 'r1', 'done')"))
                .hasRootCauseInstanceOf(SQLException.class);
        assertThatThrownBy(() -> EmbeddedPostgresLedger.execute(db, "INSERT INTO job_control.readiness_attempts "
                + "(input, period, run_id, state, retry_of) VALUES ('x', 'p', 'r1', 'failed', 'r1')"))
                .hasRootCauseInstanceOf(SQLException.class);
    }

    @Test
    void schemaNamesAreValidated() {
        assertThatThrownBy(() -> new PostgresReadiness(db, "a.b")).isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> new PostgresReadiness(db, "x; drop")).isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void autoConfigDiscoversItFromTheServiceRegistration() throws SQLException {
        String url;
        try (Connection c = db.getConnection()) {
            url = c.getMetaData().getURL();
        }
        System.setProperty("culvert.postgres.url", url);
        System.setProperty("culvert.postgres.user", "postgres");
        try {
            AutoConfig autoConfig = AutoConfig.discover();
            assertThat(autoConfig.inputReadiness()).containsInstanceOf(PostgresReadiness.class);
            assertThat(autoConfig.inputReadiness().orElseThrow().expected("never-" + tag)).isEmpty();
        } finally {
            System.clearProperty("culvert.postgres.url");
            System.clearProperty("culvert.postgres.user");
        }
    }

    @Test
    void theServiceLoaderConstructorNeedsAUrl() {
        assertThatThrownBy(PostgresReadiness::new).isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("CULVERT_POSTGRES_URL");
    }
}
