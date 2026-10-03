package com.enrichmeai.culvert.postgres;

import com.enrichmeai.culvert.autoconfig.AutoConfig;
import com.enrichmeai.culvert.stageclaim.Claim;
import com.enrichmeai.culvert.stageclaim.ClaimResult;
import com.enrichmeai.culvert.stageclaim.StageKey;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import javax.sql.DataSource;
import java.sql.Connection;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.time.Duration;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * What the PostgreSQL claim adds beyond the shared contract, on a real server. A waiting claimant
 * is detected through {@code pg_stat_activity} before the holder moves, never through a sleep, so
 * the order of events is fixed rather than hoped for.
 */
class PostgresStageClaimTest {

    private DataSource db;
    private PostgresStageClaim claims;
    private ExecutorService waiter;

    @BeforeEach
    void setUp() {
        db = EmbeddedPostgresLedger.freshLedger();
        claims = new PostgresStageClaim(db);
        waiter = Executors.newSingleThreadExecutor();
    }

    @AfterEach
    void tearDown() {
        waiter.shutdownNow();
    }

    private static StageKey freshKey() {
        return new StageKey("unit-" + UUID.randomUUID(), "load", "2026-10-01");
    }

    private Claim acquire(StageKey key, String claimant) {
        return ((ClaimResult.Acquired) claims.tryClaim(key, claimant, Duration.ZERO)).claim();
    }

    private int sessionsWaitingForALock() throws SQLException {
        try (Connection c = db.getConnection(); Statement s = c.createStatement();
             ResultSet rs = s.executeQuery("SELECT count(*) FROM pg_stat_activity "
                     + "WHERE wait_event_type = 'Lock' AND query LIKE '%stage_claims%FOR UPDATE%'")) {
            rs.next();
            return rs.getInt(1);
        }
    }

    /** Blocks until the server reports B waiting on the lock: then, and only then, A moves. */
    private void awaitWaiter() throws Exception {
        long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(10);
        while (sessionsWaitingForALock() == 0) {
            if (System.nanoTime() > deadline) {
                throw new AssertionError("B never started waiting for the lock");
            }
            Thread.onSpinWait();
        }
    }

    @Test
    void aWaiterWakesToCompletedWhenTheHolderCompletes() throws Exception {
        StageKey key = freshKey();
        Claim a = acquire(key, "A");
        Future<ClaimResult> b = waiter.submit(() -> claims.tryClaim(key, "B", Duration.ofSeconds(30)));

        awaitWaiter();
        assertThat(b).isNotDone();
        a.complete();

        ClaimResult result = b.get(10, TimeUnit.SECONDS);
        assertThat(result).isInstanceOf(ClaimResult.Completed.class);
        assertThat(((ClaimResult.Completed) result).completedBy()).isEqualTo("A");
    }

    @Test
    void aWaiterWakesToAcquiredWhenTheHolderAbandons() throws Exception {
        StageKey key = freshKey();
        Claim a = acquire(key, "A");
        Future<ClaimResult> b = waiter.submit(() -> claims.tryClaim(key, "B", Duration.ofSeconds(30)));

        awaitWaiter();
        a.close();

        ClaimResult result = b.get(10, TimeUnit.SECONDS);
        assertThat(result).isInstanceOf(ClaimResult.Acquired.class);
        ((ClaimResult.Acquired) result).claim().close();
    }

    @Test
    void aClaimantWhoseSessionDiesReleasesTheStage() throws Exception {
        StageKey key = freshKey();
        Claim a = acquire(key, "A");
        assertThat(claims.tryClaim(key, "B", Duration.ZERO)).isInstanceOf(ClaimResult.Held.class);

        // Kill A's session the way a crashed worker's would end: the server rolls it back.
        try (Connection c = db.getConnection(); Statement s = c.createStatement();
             ResultSet rs = s.executeQuery("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                     + "WHERE state = 'idle in transaction' AND query LIKE '%stage_completions%'")) {
            assertThat(rs.next()).as("A's session was found").isTrue();
            assertThat(rs.getBoolean(1)).isTrue();
        }

        long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(10);
        ClaimResult b;
        do {
            b = claims.tryClaim(key, "B", Duration.ofMillis(100));
        } while (b instanceof ClaimResult.Held && System.nanoTime() < deadline);
        assertThat(b).as("the dead claimant's stage is free and not done").isInstanceOf(ClaimResult.Acquired.class);
        ((ClaimResult.Acquired) b).claim().close();

        assertThatThrownBy(a::complete).as("a dead claim cannot record completion")
                .isInstanceOf(IllegalStateException.class);
        a.close(); // abandoning a dead claim does not throw
    }

    @Test
    void aCompletionIsSeenByEveryLaterInstance() {
        StageKey key = freshKey();
        try (Claim a = acquire(key, "A")) {
            a.complete();
        }
        ClaimResult again = new PostgresStageClaim(db).tryClaim(key, "B", Duration.ZERO);
        assertThat(again).isInstanceOf(ClaimResult.Completed.class);
    }

    @Test
    void theStageCannotBeCompletedTwiceAtTheDatabase() throws SQLException {
        StageKey key = freshKey();
        try (Claim a = acquire(key, "A")) {
            a.complete();
        }
        try (Connection c = db.getConnection(); Statement s = c.createStatement()) {
            assertThatThrownBy(() -> s.executeUpdate("INSERT INTO job_control.stage_completions "
                    + "(unit, stage, period, completed_by, completed_at) VALUES ('" + key.unit()
                    + "', 'load', '2026-10-01', 'X', now())"))
                    .isInstanceOf(SQLException.class)
                    .satisfies(e -> assertThat(((SQLException) e).getSQLState()).isEqualTo("23505"));
        }
    }

    @Test
    void schemaNamesAreValidated() {
        assertThatThrownBy(() -> new PostgresStageClaim(db, "a.b")).isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> new PostgresStageClaim(db, "x; drop")).isInstanceOf(IllegalArgumentException.class);
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
            assertThat(autoConfig.failures()).isEmpty();
            assertThat(autoConfig.stageClaim()).containsInstanceOf(PostgresStageClaim.class);
            StageKey key = freshKey();
            ClaimResult r = autoConfig.stageClaim().orElseThrow().tryClaim(key, "A", Duration.ZERO);
            assertThat(r).isInstanceOf(ClaimResult.Acquired.class);
            ((ClaimResult.Acquired) r).claim().close();
        } finally {
            System.clearProperty("culvert.postgres.url");
            System.clearProperty("culvert.postgres.user");
        }
    }

    @Test
    void theServiceLoaderConstructorNeedsAUrl() {
        assertThatThrownBy(PostgresStageClaim::new).isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("CULVERT_POSTGRES_URL");
    }
}
