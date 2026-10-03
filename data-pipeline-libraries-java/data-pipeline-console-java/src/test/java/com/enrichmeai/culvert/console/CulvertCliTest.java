package com.enrichmeai.culvert.console;

import com.enrichmeai.culvert.autoconfig.AutoConfig;
import com.enrichmeai.culvert.contracts.JobControlRepository;
import com.enrichmeai.culvert.jobcontrol.EntityStatus;
import com.enrichmeai.culvert.jobcontrol.FailedJob;
import com.enrichmeai.culvert.jobcontrol.FailureStage;
import com.enrichmeai.culvert.jobcontrol.JobStatus;
import com.enrichmeai.culvert.jobcontrol.PipelineJob;
import com.enrichmeai.culvert.tester.JobControlRepositoryFixtures;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.mockito.Mockito;

import java.io.ByteArrayOutputStream;
import java.io.PrintStream;
import java.net.URL;
import java.net.URLClassLoader;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * The CLI against the data-pipeline-tester fake. Run it with:
 * {@code mvn -o -pl data-pipeline-console-java -am test -Dtest=CulvertCliTest -Dsurefire.failIfNoSpecifiedTests=false}
 * (from data-pipeline-libraries-java). Each case prints the CLI's output.
 */
class CulvertCliTest {

    private static final LocalDate DATE = LocalDate.of(2026, 10, 1);
    private static final Instant T1 = Instant.parse("2026-10-01T06:05:00Z");

    private final ByteArrayOutputStream outBytes = new ByteArrayOutputStream();
    private final ByteArrayOutputStream errBytes = new ByteArrayOutputStream();

    private int run(JobControlRepository repo, String... args) {
        CulvertCli cli = new CulvertCli(AutoConfig.discover(), () -> new ConsoleReadService(repo));
        int code = cli.run(args, new PrintStream(outBytes, true, StandardCharsets.UTF_8),
                new PrintStream(errBytes, true, StandardCharsets.UTF_8));
        System.out.println("$ culvert " + String.join(" ", args) + "   (exit " + code + ")");
        System.out.print(out());
        System.out.print(err());
        return code;
    }

    private String out() {
        return outBytes.toString(StandardCharsets.UTF_8);
    }

    private String err() {
        return errBytes.toString(StandardCharsets.UTF_8);
    }

    private static PipelineJob failedJob() {
        return PipelineJob.builder("run-1", "sys-a", "ingest-orders", DATE, JobStatus.FAILED)
                .entityType("orders").retryCount(1)
                .failureStage(FailureStage.VALIDATION).errorCode("E_SCHEMA")
                .build();
    }

    @Test
    void runsSaysItShowsActiveRunsOnlyAndWhatItCosts() {
        JobControlRepository repo = JobControlRepositoryFixtures.repoWith(
                PipelineJob.builder("run-2", "sys-a", "ingest-orders", DATE, JobStatus.RUNNING).build());

        assertThat(run(repo, "runs")).isZero();
        assertThat(out()).contains("Active runs (created or running) only, not the run history")
                .contains("run-2 running");
        assertThat(err()).contains("reads the whole job-control table");
        Mockito.verify(repo).getPendingJobs(Optional.empty());
    }

    @Test
    void runShowsOneRunAndKeepsAFailedRunFailed() {
        assertThat(run(JobControlRepositoryFixtures.repoWith(failedJob()), "run", "run-1")).isZero();
        assertThat(out()).contains("run-1 failed").contains("status: failed (final)")
                .contains("retries attempted: 1").contains("a retry runs under a new run id");
    }

    @Test
    void anUnknownRunExitsOne() {
        assertThat(run(JobControlRepositoryFixtures.emptyRepo(), "run", "nope")).isEqualTo(1);
        assertThat(err()).contains("No run with id nope");
    }

    @Test
    void entitiesAndFailuresTakeASystemAndADate() {
        JobControlRepository repo = JobControlRepositoryFixtures.emptyRepo();
        Mockito.when(repo.getEntityStatus("sys-a", DATE)).thenReturn(List.of(
                new EntityStatus("orders", "failed", "run-1", 120, 3, Optional.empty(), Optional.of(T1))));
        Mockito.when(repo.getFailedJobs("sys-a", DATE)).thenReturn(List.of(
                new FailedJob("run-1", "orders", "validation", "E_SCHEMA", "bad date",
                        Optional.of("gs://q/run-1"), T1, 1)));

        assertThat(run(repo, "entities", "--system", "sys-a", "--date", "2026-10-01")).isZero();
        assertThat(out()).contains("orders").contains("failed").contains("run-1");

        assertThat(run(repo, "failures", "--date", "2026-10-01", "--system", "sys-a")).isZero();
        assertThat(out()).contains("E_SCHEMA").contains("bad date").contains("gs://q/run-1")
                .contains("A failed run stays failed");
    }

    @Test
    void adaptersReportsUnboundContractsAndDiscoveryFailures() {
        // This module's test classpath registers no adapter, so every contract is unbound.
        assertThat(run(JobControlRepositoryFixtures.emptyRepo(), "adapters")).isZero();
        assertThat(out()).contains("JobControlRepository").contains("(unbound)")
                .contains("Warehouse").contains("Discovery failures: none");
    }

    @Test
    void adaptersShowsAProviderThatFailedToLoad(@TempDir Path dir) throws Exception {
        // A registration whose class does not exist: AutoConfig records it and binds nothing.
        Path services = dir.resolve("META-INF/services");
        Files.createDirectories(services);
        Files.writeString(services.resolve("com.enrichmeai.culvert.contracts.Warehouse"),
                "com.example.MissingWarehouse\n");
        try (URLClassLoader loader = new URLClassLoader(new URL[] {dir.toUri().toURL()},
                getClass().getClassLoader())) {
            CulvertCli cli = new CulvertCli(AutoConfig.discover(loader),
                    () -> new ConsoleReadService(JobControlRepositoryFixtures.emptyRepo()));
            assertThat(cli.run(new String[] {"adapters"}, new PrintStream(outBytes, true, StandardCharsets.UTF_8),
                    new PrintStream(errBytes, true, StandardCharsets.UTF_8))).isEqualTo(1);
        }
        System.out.print(out());
        assertThat(out()).contains("Warehouse: (unbound)")
                .contains("Discovery failures: 1")
                .contains("Warehouse: com.example.MissingWarehouse");
    }

    @Test
    void adaptersNamesABoundProvider(@TempDir Path dir) throws Exception {
        Path services = dir.resolve("META-INF/services");
        Files.createDirectories(services);
        Files.writeString(services.resolve("com.enrichmeai.culvert.contracts.GovernancePolicy"),
                TestGovernancePolicy.class.getName() + "\n");
        try (URLClassLoader loader = new URLClassLoader(new URL[] {dir.toUri().toURL()},
                getClass().getClassLoader())) {
            CulvertCli cli = new CulvertCli(AutoConfig.discover(loader),
                    () -> new ConsoleReadService(JobControlRepositoryFixtures.emptyRepo()));
            assertThat(cli.run(new String[] {"adapters"}, new PrintStream(outBytes, true, StandardCharsets.UTF_8),
                    new PrintStream(errBytes, true, StandardCharsets.UTF_8))).isZero();
        }
        System.out.print(out());
        assertThat(out()).contains("GovernancePolicy: " + TestGovernancePolicy.class.getName())
                .contains("JobControlRepository: (unbound)")
                .contains("Discovery failures: none");
    }

    @Test
    void usageErrorsExitTwo() {
        JobControlRepository repo = JobControlRepositoryFixtures.emptyRepo();
        assertThat(run(repo)).isEqualTo(2);
        assertThat(run(repo, "bogus")).isEqualTo(2);
        assertThat(run(repo, "run")).isEqualTo(2);
        assertThat(run(repo, "entities", "--system", "sys-a")).isEqualTo(2);
        assertThat(run(repo, "failures", "--system", "sys-a", "--date", "yesterday")).isEqualTo(2);
        assertThat(run(repo, "entities", "--system", "a", "--system", "b", "--date", "2026-10-01")).isEqualTo(2);
        assertThat(run(repo, "entities", "--system", "", "--date", "2026-10-01")).isEqualTo(2);
        assertThat(run(repo, "entities", "--system", "--date", "2026-10-01")).isEqualTo(2);
        assertThat(run(repo, "entities", "--system=a", "--date", "2026-10-01")).isEqualTo(2);
        assertThat(err()).contains("Usage: culvert").contains("--system is given twice")
                .contains("--system needs a value");
        Mockito.verifyNoInteractions(repo);
    }

    @Test
    void helpPrintsTheUsageAndExitsZero() {
        assertThat(run(JobControlRepositoryFixtures.emptyRepo(), "--help")).isZero();
        assertThat(out()).contains("Usage: culvert").contains("Exit codes");
    }

    @Test
    void anEmptyListIsStillSuccess() {
        JobControlRepository repo = JobControlRepositoryFixtures.emptyRepo();
        assertThat(run(repo, "entities", "--system", "sys-a", "--date", "2026-10-01")).isZero();
        assertThat(run(repo, "failures", "--system", "sys-a", "--date", "2026-10-01")).isZero();
        assertThat(out()).contains("Entities for sys-a on 2026-10-01: 0")
                .contains("Failed runs for sys-a on 2026-10-01: 0");
    }

    @Test
    void aBackendFailureIsNamedAndExitsOne() {
        JobControlRepository repo = JobControlRepositoryFixtures.emptyRepo();
        Mockito.when(repo.getPendingJobs(Optional.empty())).thenThrow(new IllegalStateException("table gone"));
        assertThat(run(repo, "runs")).isEqualTo(1);
        assertThat(err()).contains("culvert runs failed: java.lang.IllegalStateException: table gone");
    }

    @Test
    void aMissingJobControlBindingIsReportedNotThrown() {
        AutoConfig autoConfig = AutoConfig.discover();
        CulvertCli cli = new CulvertCli(autoConfig, () -> ConsoleReadService.from(autoConfig));
        int code = cli.run(new String[] {"runs"}, new PrintStream(outBytes, true, StandardCharsets.UTF_8),
                new PrintStream(errBytes, true, StandardCharsets.UTF_8));
        assertThat(code).isEqualTo(1);
        assertThat(err()).contains("No JobControlRepository is installed");
    }
}
