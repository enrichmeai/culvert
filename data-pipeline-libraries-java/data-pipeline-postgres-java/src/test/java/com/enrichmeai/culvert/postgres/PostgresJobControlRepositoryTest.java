package com.enrichmeai.culvert.postgres;

import com.enrichmeai.culvert.autoconfig.AutoConfig;
import com.enrichmeai.culvert.jobcontrol.FailureStage;
import com.enrichmeai.culvert.jobcontrol.JobStatus;
import com.enrichmeai.culvert.jobcontrol.JobType;
import com.enrichmeai.culvert.jobcontrol.PipelineJob;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import javax.sql.DataSource;
import java.io.PrintWriter;
import java.util.logging.Logger;
import java.lang.reflect.Proxy;
import java.sql.Connection;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.concurrent.Callable;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/** What the PostgreSQL adapter adds beyond the shared contract, on a real server. */
class PostgresJobControlRepositoryTest {

    private static final LocalDate DATE = LocalDate.of(2026, 10, 1);

    private DataSource db;
    private PostgresJobControlRepository repo;

    @BeforeEach
    void setUp() {
        db = EmbeddedPostgresLedger.freshLedger();
        repo = new PostgresJobControlRepository(db);
    }

    private static PipelineJob job(String runId) {
        return PipelineJob.builder(runId, "sys-a", "ingest_orders", DATE, JobStatus.CREATED)
                .entityType("orders").build();
    }

    private long ledgerRows() throws SQLException {
        try (Connection c = db.getConnection(); Statement s = c.createStatement();
             ResultSet rs = s.executeQuery("SELECT count(*) FROM job_control.pipeline_jobs")) {
            rs.next();
            return rs.getLong(1);
        }
    }

    @Test
    void aSecondCreateForTheSameRunIsRejectedByTheServer() throws SQLException {
        repo.createJob(job("run-1"));
        assertThatThrownBy(() -> repo.createJob(job("run-1")))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("already exists")
                .hasRootCauseInstanceOf(SQLException.class);
        assertThat(ledgerRows()).isEqualTo(1);
    }

    @Test
    void racingTheSameTransitionLetsExactlyOneWriterWin() throws Exception {
        repo.createJob(job("run-1"));
        repo.updateStatus("run-1", JobStatus.RUNNING, Optional.empty());

        int writers = 8;
        ExecutorService pool = Executors.newFixedThreadPool(writers);
        CountDownLatch start = new CountDownLatch(1);
        List<Future<Boolean>> results = new ArrayList<>();
        for (int i = 0; i < writers; i++) {
            Callable<Boolean> succeed = () -> {
                start.await();
                try {
                    repo.updateStatus("run-1", JobStatus.SUCCEEDED, Optional.of(5L));
                    return true;
                } catch (IllegalStateException rejected) {
                    return false;
                }
            };
            results.add(pool.submit(succeed));
        }
        start.countDown();
        int won = 0;
        for (Future<Boolean> f : results) {
            won += f.get() ? 1 : 0;
        }
        pool.shutdown();

        assertThat(won).as("RUNNING -> SUCCEEDED is taken once; the rest read SUCCEEDED and are refused")
                .isEqualTo(1);
        assertThat(ledgerRows()).isEqualTo(3); // created, running, one succeeded
        assertThat(repo.getJob("run-1").orElseThrow().status()).isEqualTo(JobStatus.SUCCEEDED);
    }

    /** A DataSource that gives out connections already set to {@code isolation}. */
    private DataSource withDefaultIsolation(int isolation) {
        return new DelegatingDataSource(db) {
            @Override
            public Connection getConnection() throws SQLException {
                Connection c = db.getConnection();
                c.setTransactionIsolation(isolation);
                return c;
            }
        };
    }

    @Test
    void theRaceHasOneWinnerEvenWhenThePoolDefaultsToRepeatableRead() throws Exception {
        PostgresJobControlRepository rr = new PostgresJobControlRepository(
                withDefaultIsolation(Connection.TRANSACTION_REPEATABLE_READ));
        rr.createJob(job("run-rr"));
        rr.updateStatus("run-rr", JobStatus.RUNNING, Optional.empty());

        ExecutorService pool = Executors.newFixedThreadPool(8);
        CountDownLatch start = new CountDownLatch(1);
        List<Future<Boolean>> results = new ArrayList<>();
        for (int i = 0; i < 8; i++) {
            results.add(pool.submit(() -> {
                start.await();
                try {
                    rr.updateStatus("run-rr", JobStatus.SUCCEEDED, Optional.of(1L));
                    return true;
                } catch (IllegalStateException rejected) {
                    return false;
                }
            }));
        }
        start.countDown();
        int won = 0;
        for (Future<Boolean> f : results) {
            won += f.get() ? 1 : 0;
        }
        pool.shutdown();
        assertThat(won).isEqualTo(1);
    }

    @Test
    void aTransitionHandsTheConnectionBackAsItFoundIt() throws SQLException {
        Connection real = db.getConnection();
        real.setTransactionIsolation(Connection.TRANSACTION_SERIALIZABLE);
        // One connection that survives close(), as a pool's would.
        Connection kept = (Connection) Proxy.newProxyInstance(getClass().getClassLoader(),
                new Class<?>[] {Connection.class}, (proxy, method, args) ->
                        method.getName().equals("close") ? null : method.invoke(real, args));
        PostgresJobControlRepository single = new PostgresJobControlRepository(new DelegatingDataSource(db) {
            @Override
            public Connection getConnection() {
                return kept;
            }
        });

        single.createJob(job("run-1"));
        single.updateStatus("run-1", JobStatus.RUNNING, Optional.empty());
        assertThatThrownBy(() -> single.updateStatus("run-1", JobStatus.RUNNING, Optional.empty()))
                .isInstanceOf(IllegalStateException.class);

        assertThat(real.getAutoCommit()).isTrue();
        assertThat(real.getTransactionIsolation()).isEqualTo(Connection.TRANSACTION_SERIALIZABLE);
        single.createJob(job("run-2")); // autocommit is back on, so this is committed
        assertThat(repo.getJob("run-2")).isPresent();
        real.close();
    }

    @Test
    void anEmptyOptionalTextReadsBackAsAbsent() {
        repo.createJob(job("run-1"));
        repo.markFailed("run-1", "E", "m", FailureStage.LOAD, Optional.of(""));
        assertThat(repo.getJob("run-1").orElseThrow().errorFilePath()).isEmpty();
    }

    @Test
    void entityStatusAndFailuresReadTheProjection() {
        repo.createJob(job("run-1"));
        repo.updateStatus("run-1", JobStatus.RUNNING, Optional.empty());
        repo.markFailed("run-1", "E_SCHEMA", "bad date", FailureStage.VALIDATION, Optional.of("gs://q/1"));
        repo.createJob(PipelineJob.builder("run-2", "sys-a", "ingest_orders", DATE, JobStatus.CREATED)
                .entityType("customers").build());

        assertThat(repo.getEntityStatus("sys-a", DATE))
                .extracting(e -> e.entityType() + ":" + e.status())
                .containsExactly("orders:failed", "customers:created");
        assertThat(repo.getFailedJobs("sys-a", DATE)).singleElement().satisfies(f -> {
            assertThat(f.runId()).isEqualTo("run-1");
            assertThat(f.failureStage()).isEqualTo("validation");
            assertThat(f.errorCode()).isEqualTo("E_SCHEMA");
            assertThat(f.errorFilePath()).contains("gs://q/1");
        });
        assertThat(repo.getFailedJobs("sys-b", DATE)).isEmpty();
    }

    @Test
    void fdpStatusReportsTheLatestTransformationRunOfTheModel() {
        for (String runId : List.of("fdp-1", "fdp-2")) {
            repo.createJob(PipelineJob.builder(runId, "sys-a", "customer_360", DATE, JobStatus.CREATED)
                    .jobType(JobType.TRANSFORMATION).build());
        }
        repo.updateStatus("fdp-2", JobStatus.RUNNING, Optional.empty());

        assertThat(repo.getFdpJobStatus("sys-a", DATE, "customer_360")).hasValueSatisfying(s -> {
            assertThat(s.runId()).isEqualTo("fdp-2");
            assertThat(s.status()).isEqualTo("running");
        });
        assertThat(repo.getFdpJobStatus("sys-a", DATE, "other")).isEmpty();
    }

    @Test
    void costMetricsReadBackWhileTheRunIsOpen() {
        repo.createJob(job("run-1"));
        repo.updateCostMetrics("run-1", 0.25, 1000, 2000);
        PipelineJob j = repo.getJob("run-1").orElseThrow();
        assertThat(j.estimatedCostUsd()).isEqualTo(0.25);
        assertThat(j.billedBytesScanned()).isEqualTo(1000);
        assertThat(j.status()).isEqualTo(JobStatus.CREATED);
        assertThatThrownBy(() -> repo.updateCostMetrics("nope", 1, 1, 1))
                .isInstanceOf(IllegalStateException.class).hasMessageContaining("no job");
    }

    @Test
    void cleanupDeletesTheRunsRowsFromTheTargetTableOnly() throws SQLException {
        EmbeddedPostgresLedger.execute(db, "DROP TABLE IF EXISTS public.orders; "
                + "CREATE TABLE public.orders (id int, _run_id text); "
                + "INSERT INTO public.orders VALUES (1, 'run-1'), (2, 'run-1'), (3, 'run-2')");
        repo.createJob(job("run-1"));

        assertThat(repo.cleanupPartialLoad("run-1", "public.orders")).isEqualTo(2);
        assertThat(repo.cleanupPartialLoad("run-1", "orders")).isZero();
        assertThat(ledgerRows()).as("the ledger is never deleted from").isEqualTo(1);
    }

    @Test
    void tableNamesAreValidatedAndQuoted() {
        assertThat(PostgresJobControlRepository.quote("job_control.pipeline_jobs"))
                .isEqualTo("\"job_control\".\"pipeline_jobs\"");
        for (String bad : List.of("orders; DROP TABLE x", "a.b.c", "\"orders\"", "", "1orders")) {
            assertThatThrownBy(() -> repo.cleanupPartialLoad("run-1", bad))
                    .as(bad).isInstanceOf(IllegalArgumentException.class);
        }
        assertThatThrownBy(() -> new PostgresJobControlRepository(db, "x; y"))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void theServiceLoaderConstructorNeedsAUrl() {
        String saved = System.clearProperty("culvert.postgres.url");
        try {
            assertThatThrownBy(PostgresJobControlRepository::new)
                    .isInstanceOf(IllegalStateException.class)
                    .hasMessageContaining("CULVERT_POSTGRES_URL");
        } finally {
            if (saved != null) {
                System.setProperty("culvert.postgres.url", saved);
            }
        }
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
            assertThat(autoConfig.jobControl()).containsInstanceOf(PostgresJobControlRepository.class);
            autoConfig.jobControl().orElseThrow().createJob(job("via-autoconfig"));
            assertThat(repo.getJob("via-autoconfig")).isPresent();
        } finally {
            System.clearProperty("culvert.postgres.url");
            System.clearProperty("culvert.postgres.user");
        }
    }

    /** Forwards everything to a DataSource; tests override getConnection. */
    private static class DelegatingDataSource implements DataSource {
        private final DataSource delegate;

        DelegatingDataSource(DataSource delegate) {
            this.delegate = delegate;
        }

        @Override
        public Connection getConnection() throws SQLException {
            return delegate.getConnection();
        }

        @Override
        public Connection getConnection(String user, String password) throws SQLException {
            return delegate.getConnection(user, password);
        }

        @Override
        public PrintWriter getLogWriter() throws SQLException {
            return delegate.getLogWriter();
        }

        @Override
        public void setLogWriter(PrintWriter out) throws SQLException {
            delegate.setLogWriter(out);
        }

        @Override
        public void setLoginTimeout(int seconds) throws SQLException {
            delegate.setLoginTimeout(seconds);
        }

        @Override
        public int getLoginTimeout() throws SQLException {
            return delegate.getLoginTimeout();
        }

        @Override
        public Logger getParentLogger() {
            return Logger.getGlobal();
        }

        @Override
        public <T> T unwrap(Class<T> iface) throws SQLException {
            return delegate.unwrap(iface);
        }

        @Override
        public boolean isWrapperFor(Class<?> iface) throws SQLException {
            return delegate.isWrapperFor(iface);
        }
    }
}
